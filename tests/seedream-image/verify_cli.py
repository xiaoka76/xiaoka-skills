"""CLI 集成验收：四个生成子命令 + 生成记录 + 参数校验（本地 mock API，不花额度）。

用真实的 CLI 子进程跑，只在 HTTP 边界上换成本地 mock —— 因此参数校验、落盘、
run.json 组装、错误路径都是真代码在跑。**绝不调用真实接口。**

运行：  python3 tests/seedream-image/verify_cli.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2] / "skills/seedream-image"
WORK = Path(__file__).resolve().parent / "work_cli"
HOME = WORK / "home"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail and not cond else ""))


def png_bytes(size=(64, 64), color=(200, 90, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)

REF = WORK / "ref.png"                      # 通用参考图（小，够图生图用）
REF2 = WORK / "ref2.png"
REF_JPG = WORK / "ref.jpg"
REF_SMALL = WORK / "small.png"              # 低于图层拆分下限
REF_WEBP = WORK / "ref.webp"                # 图层拆分不支持的格式
REF_LD = WORK / "ld_ok.png"                 # 满足图层拆分（≥512×512）
REF.write_bytes(png_bytes())
REF2.write_bytes(png_bytes(size=(80, 60), color=(20, 140, 90)))
Image.open(REF).save(REF_JPG, format="JPEG")
REF_SMALL.write_bytes(png_bytes(size=(64, 40)))
Image.open(REF).save(REF_WEBP, format="WEBP")
REF_LD.write_bytes(png_bytes(size=(640, 512)))
HUGE_PX = WORK / "huge_px.png"          # 4800 万像素，超单张上限
HUGE_RATIO = WORK / "huge_ratio.png"    # 宽高比 166，超范围
Image.new("RGB", (8000, 6000), (30, 30, 60)).save(HUGE_PX)
Image.new("RGB", (20000, 120), (30, 30, 60)).save(HUGE_RATIO)

# ── mock API ──────────────────────────────────────────────────────────────────

CAPTURED: list[dict] = []
FAIL_MODE = {"on": False}
BASE_SIZE_MODE = {"mode": "normal"}          # normal | bad | missing
RESPONSE_MODE = {"mode": "b64"}              # b64 | url


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, payload: bytes, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self._send(png_bytes(size=(48, 32), color=(9, 9, 9)), "image/png")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
        CAPTURED.append(body)
        if FAIL_MODE["on"]:
            self._send(json.dumps({"error": {"code": "TestError", "message": "故意失败"}}).encode(), code=400)
            return
        b64 = base64.b64encode(png_bytes()).decode()
        if RESPONSE_MODE["mode"] == "url":
            self._send(json.dumps({"data": [{"url": f"http://127.0.0.1:{self.server.server_port}/i.png",
                                             "size": "48x32", "output_format": "png"}]}).encode())
            return
        if body.get("layer_decomposition"):
            base = {"b64_json": b64, "output_format": "png", "z_index": 0}
            size = {"normal": "1664x2496", "bad": "2K", "missing": None}[BASE_SIZE_MODE["mode"]]
            if size:
                base["size"] = size
            data = [base, {"b64_json": b64, "size": "1399x1758", "output_format": "png", "z_index": 1,
                           "name": "枫叶", "description": "左下角前景枫叶",
                           "bounding_box": {"absolute": [0, 2110, 218, 2383], "normalized": [0, 845, 130, 954]}}]
        else:
            data = [{"b64_json": b64, "size": "1664x2496",
                     "output_format": body.get("output_format", "png")}]
        self._send(json.dumps({"data": data}).encode())


server = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{server.server_port}/api/v3"


def cli(*args, expect_ok=True):
    env = dict(os.environ)
    env.update({"PYTHONPATH": str(REPO / "src"), "ARK_API_KEY": "test-key",
                "ARK_BASE_URL": URL, "SEEDREAM_HOME": str(HOME)})
    env.pop("MODEL_IMAGE_API_KEY", None)
    env.pop("MODEL_AGENT_API_KEY", None)
    p = subprocess.run([sys.executable, "-m", "seedream", *args],
                       capture_output=True, text=True, env=env, cwd=str(WORK), timeout=180)
    if expect_ok and p.returncode != 0:
        print(f"    !! 退出码 {p.returncode}: {' '.join(args)}\n    {p.stderr[-400:]}")
    return p


def last_body() -> dict:
    return CAPTURED[-1]


def runs_dir() -> Path:
    return HOME / "runs"


def index_lines() -> list[dict]:
    f = HOME / "index.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []


def latest() -> dict:
    return json.loads(cli("show", "--json").stdout)


print("1) 四个生成子命令：请求体 + run.json + 产物")
p = cli("draw", "一只戴贝雷帽的橘猫坐在窗台上，午后逆光", "--size", "1.5K")
check("draw 成功", p.returncode == 0)
b = last_body()
check("请求体 model/size/response_format 正确",
      b["model"] == "doubao-seedream-5-0-pro-260628" and b["size"] == "1.5K" and b["response_format"] == "b64_json")
check("文生图请求体不含 image", "image" not in b)
r = latest()
check("run.json: kind/draw + status/success + inputs 空", r["kind"] == "draw" and r["status"] == "success" and r["inputs"] == [])
check("产物落在 outputs/ 且真实存在", "/outputs/" in r["outputs"][0]["path"] and Path(r["outputs"][0]["path"]).is_file())
check("draw 默认下发 output_format=jpeg", b.get("output_format") == "jpeg")
check("draw 默认产物后缀 .jpg（生成后无需手动转格式）", r["outputs"][0]["path"].endswith(".jpg"),
      r["outputs"][0]["path"])

p = cli("edit", "把图1的水杯换成白瓷马克杯，保持手部姿势与画面其他部分不变", "--images", str(REF))
check("edit 成功", p.returncode == 0)
check("请求体含 image（data URL）", str(last_body().get("image", "")).startswith("data:image/png;base64,"))
r = latest()
inp = r["inputs"][0]
check("输入记录了 sha256（64 位）", len(inp.get("sha256") or "") == 64)
check("输入记录了尺寸", (inp.get("width"), inp.get("height")) == (64, 64))
check("输入图副本已落盘到 inputs/", Path(inp["path"]).is_file() and "/inputs/" in inp["path"])
check("edit 默认下发 output_format=jpeg", last_body().get("output_format") == "jpeg")
check("edit 默认产物后缀 .jpg", r["outputs"][0]["path"].endswith(".jpg"), r["outputs"][0]["path"])

p = cli("edit", "将图1的人物放到图2的庭院场景中，光影自然融合", "--images", str(REF), "--images", str(REF2))
check("多图 edit 成功", p.returncode == 0)
check("请求体 image 是长度 2 的数组", isinstance(last_body().get("image"), list) and len(last_body()["image"]) == 2)
check("run.json 记录 2 张输入", len(latest()["inputs"]) == 2)

p = cli("split", str(REF_LD))
check("split 成功", p.returncode == 0)
b = last_body()
check("请求体 layer_decomposition=true 且 size 默认 auto",
      b.get("layer_decomposition") is True and b.get("size") == "auto")
check("split 默认下发 output_format=png（底图仍 png，别被 draw/edit 的 jpeg 带跑）",
      b.get("output_format") == "png", str(b.get("output_format")))
check("无 -p 时不发送 prompt 字段", "prompt" not in b)
r = latest()
layer = [o for o in r["outputs"] if o["z_index"] == 1][0]
check("图层带 name/description", layer["name"] == "枫叶" and bool(layer["description"]))
check("图层保留底图坐标系 bbox_base + bbox_base_size（还原/重组用）",
      bool(layer["bbox_base"]) and layer["bbox_base_size"] == "1664x2496")
check("图层给出原图像素 bbox_pixel + 可粘标签（写 prompt 用）",
      bool(layer["bbox_pixel"]) and "<bbox>" in layer["prompt_fragment"])

p = cli("cutout", str(REF))
check("cutout 成功", p.returncode == 0)
b = last_body()
check("请求体 background=transparent 且 output_format=png",
      b.get("background") == "transparent" and b.get("output_format") == "png")

print("\n2) 生成记录与复用")
TOTAL = len(index_lines())
check("索引条数 == 跑过的任务数", TOTAL == 5, f"实际 {TOTAL}")
p = cli("ls", "--json")
ids = [e["run_id"] for e in json.loads(p.stdout)["runs"]]
check("ls --json 可解析且最新在前", len(ids) == 5)
check("ls --limit 生效", len(json.loads(cli("ls", "-n", "2", "--json").stdout)["runs"]) == 2)
check("run_id 形态 = 时间戳 + 6 位十六进制",
      all(len(i.split("-")[-1]) == 6 for i in ids), str(ids[:2]))

p = cli("show", r["run_id"])
check("show 主字段标注「原图像素，可直接复用」", "提示词(原图像素，可直接复用)" in p.stdout)
check("show 显示输入 sha256", "sha256:" in p.stdout)

# 带标签的 edit：两个提示词口径
cli("edit", "把图1<bbox>10 10 50 50</bbox>区域换成蓝色方块", "--images", str(REF))
r = latest()
check("【核心】run.json.prompt 是原始像素提示词", "<bbox>10 10 50 50</bbox>" in r["prompt"], r["prompt"])
check("【核心】run.json.prompt_sent 是换算后的实际请求",
      "<bbox>156 156 781 781</bbox>" in r["prompt_sent"], r["prompt_sent"])
check("不再有 prompt_raw 字段", "prompt_raw" not in r)
sent_first = last_body()["prompt"]
tagged_id = r["run_id"]
p = cli("show", tagged_id)
check("show 把换算版单独标注「勿再粘贴」", "勿再粘贴" in p.stdout and "仅供审计" in p.stdout)
check("索引文件里只有像素值（不含换算值）", "156 156" not in (HOME / "index.jsonl").read_text(encoding="utf-8"))

p = cli("replay", tagged_id, "--run")
check("replay --run 成功", p.returncode == 0)
check("【核心】复现请求体带 image（不退化成文生图）", "image" in last_body())
check("【核心】复现 prompt 与首次逐字一致（无二次换算）", last_body()["prompt"] == sent_first)
check("复现记录标注 replayed_from", latest().get("replayed_from") == tagged_id)

before = len(CAPTURED)
p = cli("replay")                      # 默认预演
check("replay 默认不调用 API", len(CAPTURED) == before and "未调用 API" in p.stdout)

print("\n3) 幽灵条目：外部删目录后 ls 不留残影")
cli("draw", "幽灵测试")
ghost = latest()["run_id"]
shutil.rmtree(runs_dir() / ghost)
ids = [e["run_id"] for e in json.loads(cli("ls", "--json").stdout)["runs"]]
check("【核心】目录被删后 ls 不再列出", ghost not in ids)
check("索引文件仍保留原始行（append-only）", ghost in (HOME / "index.jsonl").read_text(encoding="utf-8"))
check("show 幽灵条目明确报错（不静默）", cli("show", ghost, expect_ok=False).returncode != 0)
check("last 回退到还在的最新任务", latest()["run_id"] != ghost)

print("\n4) 失败路径：输入照样保存、记录照样入索引")
FAIL_MODE["on"] = True
cli("edit", "把背景换成海边", "--images", str(REF), expect_ok=False)
FAIL_MODE["on"] = False
r = latest()
check("失败记录 status=error 且有 error 文案", r["status"] == "error" and bool(r["error"]))
check("失败记录仍保存输入副本（可复用）", Path(r["inputs"][0]["path"]).is_file())
check("失败记录也进索引", index_lines()[-1]["run_id"] == r["run_id"])

print("\n5) 参数校验（本地拦下，不发请求）")
before = len(CAPTURED)
check("split 拒绝自定义宽x高",
      "不支持自定义" in cli("split", str(REF_LD), "--size", "2048x1024", expect_ok=False).stderr)
check("draw 拒绝 auto", cli("draw", "测试", "--size", "auto", expect_ok=False).returncode != 0)
check("cutout 拒绝无 alpha 的 jpg",
      "透明背景" in cli("cutout", str(REF_JPG), expect_ok=False).stderr)
check("非法分辨率被拒", cli("split", str(REF_LD), "--size", "3K", expect_ok=False).returncode != 0)
check("draw 的提示词含坐标标签但无参考图 → 报错",
      "坐标标签" in cli("draw", "把图1<bbox>1 2 3 4</bbox>换掉", expect_ok=False).stderr)
check("edit 缺少 --images 被拒", cli("edit", "改一下", expect_ok=False).returncode != 0)
check("以上校验都没有发出请求", len(CAPTURED) == before)

print("\n6) 图层拆分本地预检（专属限制：格式 + 512×512 下限）")
before = len(CAPTURED)
n_before = len(list(runs_dir().iterdir()))
p = cli("split", str(REF_SMALL), expect_ok=False)
check("【核心】小图被本地拦下（不等接口报错）",
      p.returncode != 0 and "总像素 ≥ 262144" in p.stderr, p.stderr[-160:])
check("给出可执行的放大建议", "建议先等比放大到" in p.stderr)
check("明确不自动改图", "不会自动改图" in p.stderr)
check("非 png/jpeg 被拦", "仅支持 png / jpeg" in cli("split", str(REF_WEBP), expect_ok=False).stderr)
check("【核心】被拦下时不创建任务目录", len(list(runs_dir().iterdir())) == n_before)
check("被拦下时不发请求", len(CAPTURED) == before)
check("达标图放行", cli("split", str(REF_LD)).returncode == 0)
check("同一张小图走 edit 不受该限制（图生图无此下限）",
      cli("edit", "把图1改一下", "--images", str(REF_SMALL)).returncode == 0)

print("\n7) 接口只回 url 时的回退下载")
RESPONSE_MODE["mode"] = "url"
p = cli("draw", "一只橘猫")
check("【核心】url 回退可用（不因签名改动报 TypeError）", p.returncode == 0, p.stderr[-200:])
r = latest()
check("url 模式下产物落盘且内容非空",
      r["status"] == "success" and os.path.getsize(r["outputs"][0]["path"]) > 0)
check("url 回退在 edit 路径同样可用",
      cli("edit", "把图1换色", "--images", str(REF)).returncode == 0)
RESPONSE_MODE["mode"] = "b64"

print("\n8) data URI 作为参考图")
uri = "data:image/png;base64," + base64.b64encode(REF.read_bytes()).decode()
p = cli("edit", "把背景换成海边", "--images", uri)
check("data URI 输入可用", p.returncode == 0, p.stderr[-200:])
inp = latest()["inputs"][0]
check("data URI 也落盘并记录 sha256",
      Path(inp["path"]).is_file() and len(inp["sha256"]) == 64)
p = cli("edit", "把图1<bbox>10 10 50 50</bbox>换成暖色调", "--images", uri)
check("【核心】data URI 的尺寸能解出来，坐标标签照常换算（不再误报「网络 URL」）",
      p.returncode == 0 and "网络 URL" not in p.stderr, p.stderr[-300:])
check("data URI 的换算结果确实下发给了接口（原像素标签已被换算）",
      "<bbox>10 10 50 50</bbox>" not in str(last_body().get("prompt")),
      str(last_body().get("prompt")))

print("\n9) 图层拆分底图尺寸异常时降级（不把成功判成失败）")
BASE_SIZE_MODE["mode"] = "bad"
p = cli("split", str(REF_LD))
check("【核心】底图 size 非「宽x高」时整体仍算成功",
      p.returncode == 0 and latest()["status"] == "success", p.stderr[-200:])
layer = [o for o in latest()["outputs"] if o["z_index"] == 1][0]
check("降级为 bbox_note 且不发可疑标签",
      bool(layer["bbox_note"]) and not layer["bbox_pixel"], str(layer)[:120])
check("降级时仍保留 bbox_base 原值", bool(layer["bbox_base"]))
BASE_SIZE_MODE["mode"] = "missing"
cli("split", str(REF_LD))
layer = [o for o in latest()["outputs"] if o["z_index"] == 1][0]
check("底图缺 size 时给出说明而非静默留空", bool(layer["bbox_note"]), str(layer)[:120])
BASE_SIZE_MODE["mode"] = "normal"

print("\n10) run_id 同秒不撞车")
before_ids = {e["run_id"] for e in index_lines()}
for _ in range(4):
    cli("draw", "同秒撞 id 测试")
new_ids = [i for i in {e["run_id"] for e in index_lines()} if i not in before_ids]
check("同秒连跑 4 次得到 4 个不同 id", len(new_ids) == 4, str(sorted(new_ids)))
check("每个 id 都有自己的目录", all((runs_dir() / i / "run.json").is_file() for i in new_ids))

print("\n11) 帮助文案与实际能力一致")
check("split 的 --size 帮助不承诺自定义宽x高",
      "不支持自定义宽x高" in cli("split", "--help").stdout)
check("cutout 不提供 --format（恒为 png，用「不给选项」代替「给了再报错」）",
      "--format" not in cli("cutout", "--help").stdout)
check("edit 的 --images 标记为必填", "required" in cli("edit", "--help").stdout)

print("\n12) 参考图超限本地预检（图生图路径，给可执行建议、不自动改图）")
before = len(CAPTURED)
p = cli("edit", "改一下", "--images", str(HUGE_PX), expect_ok=False)
out = p.stderr
check("单张总像素超限被本地拦下", p.returncode != 0 and "总像素超限" in out, out[-200:])
check("给出可执行的等比缩放建议", "建议先等比缩放到" in out)
check("明确声明不会自动改图", "不会自动改图" in out)
p = cli("edit", "改一下", "--images", str(HUGE_RATIO), expect_ok=False)
check("宽高比超限被本地拦下", p.returncode != 0 and "宽高比" in p.stderr, p.stderr[-160:])
check("超限图没有发出请求", len(CAPTURED) == before)

print("\n13) 默认格式可被 --format 覆盖（新跑 2 个任务）")
before = len(CAPTURED)
cli("draw", "一只戴贝雷帽的橘猫坐在窗台上", "--format", "png")
r = latest()
check("draw --format png：请求体与落盘后缀都是 png",
      last_body().get("output_format") == "png" and r["outputs"][0]["path"].endswith(".png"),
      f"{last_body().get('output_format')} / {r['outputs'][0]['path']}")
cli("edit", "把图1的水杯换成白瓷马克杯", "--images", str(REF), "--format", "jpeg")
r = latest()
check("edit --format jpeg：请求体 jpeg、落盘 .jpg（显式传等价于默认）",
      last_body().get("output_format") == "jpeg" and r["outputs"][0]["path"].endswith(".jpg"))
check("两次覆盖都真的发出了请求", len(CAPTURED) == before + 2)

print(f"\n{'=' * 58}\nPASS {len(PASS)} / FAIL {len(FAIL)}  （共 {len(PASS) + len(FAIL)} 项）")
if FAIL:
    print("失败项:")
    for f in FAIL:
        print("  -", f)
sys.exit(1 if FAIL else 0)
