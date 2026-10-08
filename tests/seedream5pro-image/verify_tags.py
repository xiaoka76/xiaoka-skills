"""标签引擎验收：prompt 内像素坐标标签的校验与换算（纯函数，不发请求）。

坐标口径是这套技能最容易错的地方，所以这层守卫最密：
agent 只写**原图像素**，转换由 CLI 在发请求前完成，且对外输出里不应出现归一化值。

运行：  python3 tests/seedream5pro-image/verify_tags.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2] / "skills/seedream5pro-image"
sys.path.insert(0, str(REPO / "src"))

from seedream.mark import _grid_ticks                      # noqa: E402
from seedream.tags import convert_prompt_tags              # noqa: E402

W, H = 1664, 2496
PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail and not cond else ""))


def conv(prompt: str, sizes):
    return convert_prompt_tags(prompt, sizes)


print("1) 基本换算（像素 → 接口需要的 0~999）")
r = conv("把图1<point>832 1248</point>换成皇冠", [(W, H)])
check("点选换算成功", r.converted == 1 and not r.errors, str([i.message for i in r.issues]))
check("换算结果 = 500 500", "<point>500 500</point>" in r.prompt, r.prompt)
r = conv("把图1<bbox>166 250 832 1248</bbox>区域换掉", [(W, H)])
check("框选换算成功", r.converted == 1 and "<bbox>100 100 500 500</bbox>" in r.prompt, r.prompt)
r = conv("先把图1<point>10 10</point>改成A，再把图1<bbox>20 20 30 30</bbox>改成B", [(W, H)])
check("一个 prompt 多个标签都换算", r.converted == 2, str(r.converted))
check("标签之间的原文保留（prompt 不被改坏）",
      "先把图1" in r.prompt and "改成A，再把图1" in r.prompt and "改成B" in r.prompt, r.prompt)

print("\n2) 边界口径：网格标什么，校验就得接受什么")
xs, ys = _grid_ticks(W, H)
check("网格右/下边界刻度 = 图片宽高", xs[-1] == W and ys[-1] == H, f"{xs[-1]}, {ys[-1]}")
r = conv(f"把图1<bbox>0 0 {W} {H}</bbox>换掉", [(W, H)])
check("按网格读出的边界值被接受（不再报越界）", not r.errors and r.converted == 1,
      str([i.message[:60] for i in r.errors]))
check("边界值 clamp 到 999", "<bbox>0 0 999 999</bbox>" in r.prompt, r.prompt)
r = conv(f"把图1<point>{W} {H}</point>换掉", [(W, H)])
check("点选边界值同样被接受", not r.errors and "<point>999 999</point>" in r.prompt, r.prompt)
r = conv(f"把图1<point>{W + 1} 100</point>换掉", [(W, H)])
check("真正越界（宽+1）仍报错", len(r.errors) == 1 and "超出图片范围" in r.errors[0].message)
r = conv("把图1<point>-5 100</point>换掉", [(W, H)])
check("负值报错", len(r.errors) == 1)
r = conv(f"把图1<bbox>{W} {H} {W} {H}</bbox>换掉", [(W, H)])
check("退化框（clamp 后宽高为 0）给出提示而非崩溃", not r.errors and any("宽" in i.message for i in r.warnings),
      str([i.message[:40] for i in r.issues]))

print("\n3) 形态与格式校验")
r = conv("把图1<bbox>10 20 30</bbox>换掉", [(W, H)])
check("bbox 给 3 个值 → 报错并说明需要几个", len(r.errors) == 1 and "需要 4 个值" in r.errors[0].message)
r = conv("把图1<point>1 2 3 4</point>换掉", [(W, H)])
check("point 给 4 个值 → 报错并提示改用 bbox", len(r.errors) == 1 and "bbox" in r.errors[0].message)
r = conv("把图1<bbox>1.5 20 30 40</bbox>换掉", [(W, H)])
check("小数 → 报错", len(r.errors) == 1 and "非整数" in r.errors[0].message)
r = conv("把图1<bbox>10%,20,30,40</bbox>换掉", [(W, H)])
check("百分号 → 报错", len(r.errors) == 1)
r = conv("把图1<bbox>10,20,30,40</bbox>换掉", [(W, H)])
check("逗号分隔 → 兼容并提示", not r.errors and r.converted == 1 and len(r.warnings) == 1)
r = conv("把图1<bbox>832 1248 166 250</bbox>换掉", [(W, H)])
check("框写反 → 自动纠正并提示",
      not r.errors and "<bbox>100 100 500 500</bbox>" in r.prompt and len(r.warnings) == 1, r.prompt)
r = conv("把图1<bbox>100 100 100 500</bbox>换掉", [(W, H)])
check("框宽为 0 → 提示", any("宽或高为 0" in i.message for i in r.warnings))

print("\n4) 普通尖括号放行（文生图不该被误杀）")
for text in ("生成一张海报，标题用<重点>突出，背景纯色", "画一个<div>风格的UI界面",
             "画一个<3爱心>图案", "文字<>说明", "做一个 <b>加粗</b> 的风格",
             "画一个<checkbox>组件", "用<mybox>包起来", "一个<pointing>箭头",
             "版本号<3>说明", "评分<1.5>分"):
    r = conv(text, [])
    check(f"draw 不报错: {text[:18]}", not r.errors and r.converted == 0,
          str([i.message[:50] for i in r.errors]))

print("\n5) 真坐标形态仍要被拦（无参考图时）")
for text in ("<bbox>1 2 3 4</bbox>", "<boox>1 2 3 4</boox>", "<120 180 640 760>",
             "<bbox>100 200 300 400 换成别的"):
    r = conv(text, [])
    check(f"无参考图仍拦截: {text[:24]}", len(r.errors) == 1,
          str([i.message[:50] for i in r.issues]))

print("\n6) 提示文案（不冤枉正常写法）")
r = conv("把图1<bbox>100 200 300 400 换成别的", [(W, H)])
check("未闭合 → 警告含「未闭合」", any("未闭合" in i.message for i in r.warnings))
r = conv("把图1<boox> 改一下", [(W, H)])
check("近似名字 → 中性提示且给出正确写法",
      any("正确写法" in i.message for i in r.warnings)
      and not any("写错" in i.message for i in r.warnings),
      str([i.message[:40] for i in r.warnings]))
r = conv("把图1<checkbox>打勾", [(W, H)])
check("含 box 字样的普通标签不发误导性指控", not any("写错" in i.message for i in r.warnings))

print("\n7) 多图归属")
r = conv("将图1<bbox>0 0 100 100</bbox>的主体放到图2<bbox>0 0 100 100</bbox>位置", [(1000, 1000), (500, 500)])
check("按「图N」各自换算（图1 用 1000 换算 → 100；图2 用 500 换算 → 200）",
      r.converted == 2 and "将图1<bbox>0 0 100 100</bbox>的主体放到图2<bbox>0 0 200 200</bbox>位置" == r.prompt,
      r.prompt)
r = conv("把<bbox>0 0 100 100</bbox>换掉", [(1000, 1000), (500, 500)])
check("多图未标归属 → 报错", len(r.errors) == 1 and "属于哪张参考图" in r.errors[0].message)
r = conv("把<bbox>0 0 100 100</bbox>换掉", [(1000, 1000)])
check("单图可省略归属", not r.errors and r.converted == 1)
r = conv("把图1<bbox>0 0 100 100</bbox>换掉", [None])
check("参考图尺寸未知（网络 URL）→ 报错并提示改本地路径",
      len(r.errors) == 1 and "本地图片路径" in r.errors[0].message,
      str([i.message[:60] for i in r.issues]))

print("\n8) 换算产物不会被二次误判")
r = conv("把图1<bbox>100 100 500 500</bbox>换成别的", [(W, H)])
check("换算出的新标签不再产生可疑片段警告",
      not any("<bbox>" in i.message and "可疑" in i.message for i in r.warnings),
      str([i.message[:40] for i in r.warnings]))

print("\n9) 对外文案不含「归一化」")
msgs = []
for text in ("<bbox>1 2 3 4 5 6</bbox>", "<point>1 2 3</point>", "把图1<bbox>99999 1 2 3</bbox>换掉",
             "把图1<bbox>1.5 2 3 4</bbox>换掉", "把图1<boox>换掉"):
    for i in conv(text, [(W, H)] if "图1" in text else []).issues:
        msgs.append(i.message)
check("所有校验文案都不含「归一化」", not any("归一化" in m for m in msgs), str(msgs[:2]))

print(f"\n{'=' * 58}\nPASS {len(PASS)} / FAIL {len(FAIL)}  （共 {len(PASS) + len(FAIL)} 项）")
if FAIL:
    print("失败项:")
    for f in FAIL:
        print("  -", f)
sys.exit(1 if FAIL else 0)
