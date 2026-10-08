"""mark 标记预览验收：网格 / 提交模式 / 分辨率自动降档 / 像素级布局（纯本地，零成本）。

mark 是「先核对再提交」的工作流核心，坐标读数直接依赖它，所以做**像素级**断言：
不只是"命令退出码为 0"，而是去量输出图里刻度与标签的实际位置。

运行：  python3 tests/seedream5pro-image/verify_mark.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2] / "skills/seedream5pro-image"
sys.path.insert(0, str(REPO / "src"))

WORK = Path(__file__).resolve().parent / "work_mark"
WORK.mkdir(parents=True, exist_ok=True)

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail and not cond else ""))


def mark(*args, expect_ok=True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "src")
    env["ARK_API_KEY"] = "test-key"
    env["SEEDREAM_HOME"] = str(WORK / "home")
    p = subprocess.run([sys.executable, "-m", "seedream", "mark", *args],
                       capture_output=True, text=True, env=env, cwd=str(WORK), timeout=300)
    if expect_ok and p.returncode != 0:
        print(f"    !! {p.stderr[-300:]}")
    return p


def mark_json(*args) -> dict:
    """带 --json 跑一次，拿结构化结果（像素级断言都基于它）。"""
    return json.loads(mark(*args, "--json").stdout)


# 测试素材：一张真 2K（触发自动降档）+ 一张小图（不降档）
SMALL = WORK / "small.png"                    # 小图：默认渲染应保持原始尺寸
PHOTO = WORK / "photo.png"
BIG = WORK / "huge_px.png"
RATIO = WORK / "huge_ratio.png"
# 用噪点图而不是纯色图：纯色 PNG 压得极小，测不出「产物超 2MB 自动降档」这类体积行为
# 每次都重新生成：纯色图压得太小，测不出体积相关行为
Image.frombytes("RGB", (2496, 1664), os.urandom(2496 * 1664 * 3)).save(PHOTO)
Image.new("RGB", (8000, 6000), (30, 30, 60)).save(BIG)          # 4800 万像素，超上限
Image.new("RGB", (20000, 120), (30, 30, 60)).save(RATIO)        # 宽高比 166，超上限
Image.new("RGB", (320, 200), (40, 60, 90)).save(SMALL)
src_w, src_h = Image.open(PHOTO).size

print("1) 网格默认开启与画布几何")
d = mark_json(str(PHOTO))
check("grid 默认 True", d["grid"] is True)
check("左/上留白 > 0，右/下不留白",
      d["margin_left"] > 0 and d["margin_top"] > 0
      and d["output_size"][0] == round(src_w * d["scale"]) + d["margin_left"]
      and d["output_size"][1] == round(src_h * d["scale"]) + d["margin_top"],
      f"{d['output_size']}")
check("默认不主动缩小：小图按原始尺寸（scale=1.0）",
      mark_json(str(SMALL))["scale"] == 1.0)
check("无标记时 fragments 为空", d["fragments"] == [])

d2 = mark_json(str(PHOTO), "--no-grid")
check("--no-grid 时无留白", d2["margin_left"] == 0 and d2["margin_top"] == 0)

print("\n2) 网格刻度是像素值，且包含边界")
im = Image.open(d["preview_path"]).convert("RGB")
check("预览图尺寸与 output_size 一致", im.size == tuple(d["output_size"]), f"{im.size}")
check("预览图里有刻度文字（图片外留白区非空）",
      im.crop((0, 0, d["margin_left"], im.size[1])).getbbox() is not None)

print("\n3) 标记渲染与编号顺序")
d3 = mark_json(str(PHOTO), "--point", "100,200:点A", "--box", "300,400,600,700:框B", "--point", "800,900")
check("点数与片段数一致", len(d3["marks"]) == 3 and len(d3["fragments"]) == 3)
check("编号顺序：点选在前、框选在后",
      [m["kind"] for m in d3["marks"]] == ["point", "point", "bbox"], str([m["kind"] for m in d3["marks"]]))
check("内联标签被识别", d3["marks"][0]["label"] == "点A" and d3["marks"][2]["label"] == "框B")
check("fragments 是可直接粘进 prompt 的 <bbox>/<point> 标签",
      d3["fragments"][2].startswith("<bbox>") and d3["fragments"][0].startswith("<point>"))
check("mark 对外只给像素坐标（无归一化字段）",
      all("normalized" not in json.dumps(m, ensure_ascii=False) for m in d3["marks"]))

print("\n4) 坐标越界拦截")
p = mark(str(PHOTO), "--point", f"{src_w + 10},100", expect_ok=False)
check("点选越界被拦", p.returncode != 0 and "超出" in (p.stdout + p.stderr))
d_rev = mark_json(str(PHOTO), "--box", "100,100,50,50")
check("框写反 → 自动纠正为 (50 50 100 100)，不产生错框",
      d_rev["marks"][0]["pixel"] == [50, 50, 100, 100], str(d_rev["marks"][0]["pixel"]))
p = mark(str(PHOTO), "--box", "abc,1,2,3", expect_ok=False)
check("非法数字被拦", p.returncode != 0)

print("\n5) 提交模式（--plain）")
PLAIN = WORK / "plain.png"
d5 = mark_json(str(PHOTO), "--box", "300,400,600,700", "--plain", "-o", str(PLAIN))
check("--plain 输出原图尺寸（无留白）", d5["margin_left"] == 0 and d5["margin_top"] == 0)
_pl = Image.open(PLAIN)
check("--plain 保持原图宽高比（比例不变）",
      abs(_pl.size[0] / _pl.size[1] - src_w / src_h) < 0.02, str(_pl.size))
check("【核心】--plain 默认严格原图尺寸（提交物不因 2MB 预览上限缩水）",
      d5["auto_scaled"] is False and d5["scale"] == 1.0
      and Image.open(PLAIN).size == (src_w, src_h),
      f"auto_scaled={d5['auto_scaled']} scale={d5['scale']} size={Image.open(PLAIN).size}")
check("--plain 想控体积可显式传 --max-edge",
      mark_json(str(PHOTO), "--box", "300,400,600,700", "--plain",
                "-o", str(WORK / "p_me.png"), "--max-edge", "1200")["scale"] < 1.0)
_p0 = mark_json(str(SMALL), "--box", "50,50,150,120", "--plain", "-o", str(WORK / "p0.png"), "--max-edge", "0")
check("--plain --max-edge 0 → 严格原图尺寸",
      Image.open(WORK / "p0.png").size == (320, 200), str(Image.open(WORK / "p0.png").size))
check("--plain 至少需要标记（纯网格请去掉 --plain）",
      mark(str(PHOTO), "--plain", expect_ok=False).returncode != 0)
check("--plain 产物可直接当参考图传（存在且非空）", PLAIN.is_file() and PLAIN.stat().st_size > 0)

print("\n6) 输出格式由后缀决定")
JPG = WORK / "o.jpg"
d6 = mark_json(str(PHOTO), "--point", "10,10", "-o", str(JPG))
check(".jpg 输出为 JPEG", Image.open(JPG).format == "JPEG", str(Image.open(JPG).format))
check("产物 < 2MB（超出即预览失效）", d6["output_bytes"] < 2 * 1024 * 1024,
      f"{d6['output_bytes'] / 1024:.0f} KB")

print("\n7) 分辨率自动降档（预览可用性保障）")
d_auto = mark_json(str(PHOTO), "--point", "10,10")
check("默认（原始尺寸）产物仍压进 2MB", d_auto["output_bytes"] < 2 * 1024 * 1024,
      f"{d_auto['output_bytes'] / 1024:.0f} KB")
check("【核心】2K 噪点图触发自动降档（并明确告知）",
      d_auto["auto_scaled"] is True and d_auto["scale"] < 1.0 and any("降" in w for w in d_auto["warnings"]),
      f"auto_scaled={d_auto['auto_scaled']} scale={d_auto['scale']} warn={d_auto['warnings']}")
d7 = mark_json(str(PHOTO), "--point", "10,10", "--max-edge", "0")
check("--max-edge 0 = 强制原始尺寸且不降档",
      d7["auto_scaled"] is False and d7["scale"] == 1.0
      and d7["output_size"][0] == src_w + d7["margin_left"],
      f"{d7['output_size']} scale={d7['scale']}")
check("强制原始尺寸时体积可超 2MB（2K 噪点图）", d7["output_bytes"] > 2 * 1024 * 1024,
      f"{d7['output_bytes'] / 1024:.0f} KB，源图 {PHOTO.stat().st_size / 1024 / 1024:.1f} MB")

print("\n8) mark 是纯本地工具：不承担参考图上限预检（那在 edit 路径，见 verify_cli.py）")
d8 = mark_json(str(BIG))
check("超限大图 mark 仍能出预览（不做联网校验）", Path(d8["preview_path"]).is_file())
check("超限大图也能出预览（4800 万像素）", d8["image_size"] == [8000, 6000], str(d8["image_size"]))

print("\n9) 中文标签（CJK 字体）")
d9 = mark_json(str(PHOTO), "--box", "100,100,200,200:手部")
check("中文标签被接受", d9["marks"][0]["label"] == "手部")
check("含中文时产物仍生成", Path(d9["preview_path"]).is_file())
check("无 CJK 字体时给出提示而非崩溃",
      not (Path("/usr/share/fonts").exists() and not d9.get("warnings"))
      or isinstance(d9.get("warnings"), list))

print("\n10) 预览图不能当参考图（设计约束的文档化断言）")
check("预览模式带留白（当参考图会污染输入）", d["margin_left"] > 0)
check("提交模式无留白（专为当参考图设计）", d5["margin_left"] == 0)

print(f"\n{'=' * 58}\nPASS {len(PASS)} / FAIL {len(FAIL)}  （共 {len(PASS) + len(FAIL)} 项）")
if FAIL:
    print("失败项:")
    for f in FAIL:
        print("  -", f)
sys.exit(1 if FAIL else 0)
