"""prompt 内坐标标签的校验与换算。

**坐标口径（全流程统一为原图像素）**

- agent 在 prompt 里**直接写像素标签**：``<point>x y</point>`` / ``<bbox>x1 y1 x2 y2</bbox>``
- 本模块负责两件事：
  1. **校验**——标签是否有效、格式是否正确、疑似错误格式检测；
  2. **换算**——像素坐标 → 接口要求的 0~999 归一化值。
- 换算是**内部行为**：换算后的 prompt 才是真正发给接口的内容，agent 全程不需要知道归一化值。

多图场景下，标签归属由紧邻其前面的「图N / 图片N」字样决定（例如
``将图1<bbox>…</bbox>…放到图2<bbox>…</bbox>位置``）；只有一张参考图时全部归属该图。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .generate import normalize_coords

# 完整成对的坐标标签（point / bbox，名称大小写不敏感）
_PAIRED_TAG = re.compile(r"<\s*(point|bbox)\s*>(.*?)<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)

# 任意尖括号片段——用来找"没配对/写错名"的可疑标签
_ANY_TAG = re.compile(r"<[^<>\n]{0,60}>")

# 标签前的图片指示：「图1」「图片 2」「第3张」「image1」
_IMAGE_REF = re.compile(r"(?:图片|图|第|image)\s*([0-9０-９]+)")

# 允许的坐标分隔符（除了空格）
_SEPARATORS = re.compile(r"[,;，、]")

_INT = re.compile(r"^[+-]?\d+$")

@dataclass
class TagIssue:
    """一条校验结论。``error`` 会中止发送，``warning`` 只提示。"""

    level: Literal["error", "warning"]
    message: str


@dataclass
class ConvertResult:
    """换算结果。"""

    prompt: str
    issues: list[TagIssue] = field(default_factory=list)
    converted: int = 0

    @property
    def errors(self) -> list[TagIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[TagIssue]:
        return [i for i in self.issues if i.level == "warning"]


def _image_index_before(prompt: str, position: int, image_count: int) -> int | None:
    """找出标签归属的参考图序号（0 基）。

    取标签**前面**最后一次出现的「图N」字样；找不到时：只有一张图就用它，多张图则返回 None
    （归属不明，由调用方报错，避免换算到错误的尺寸上）。
    """
    best: int | None = None
    for match in _IMAGE_REF.finditer(prompt, 0, position):
        digits = match.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        index = int(digits) - 1
        if 0 <= index < image_count:
            best = index
    if best is not None:
        return best
    return 0 if image_count == 1 else None


def _looks_like_typo(name: str) -> bool:
    """判断标签名是否疑似 point/bbox 的笔误。"""
    low = name.lower().strip()
    if low in ("point", "bbox"):
        return False
    return any(key in low for key in ("point", "box")) or low in ("poin", "bbx", "bboxx", "piont")


def convert_prompt_tags(
    prompt: str,
    image_sizes: list[tuple[int, int] | None],
) -> ConvertResult:
    """校验 prompt 里的像素坐标标签，并换算成归一化值。

    :param prompt: 原始 prompt（像素标签形态）
    :param image_sizes: 参考图尺寸列表（顺序与传入的 ``--images`` 一致）；
        未知尺寸（如网络 URL）用 ``None`` 占位
    :return: :class:`ConvertResult`
    """
    result = ConvertResult(prompt=prompt)
    if not prompt:
        return result

    has_tag = bool(_PAIRED_TAG.search(prompt)) or bool(_ANY_TAG.search(prompt))
    if has_tag and not image_sizes:
        result.issues.append(TagIssue(
            "error",
            "prompt 里有坐标标签，但本次没有参考图。坐标标签只用于图生图 / 编辑场景；"
            "文生图请去掉标签，或加上 --images",
        ))
        return result

    out: list[str] = []
    residual: list[str] = []      # 只收集**未被成对标签覆盖**的文本，避免误报自己刚换算出的标签
    cursor = 0

    for match in _PAIRED_TAG.finditer(prompt):
        segment = prompt[cursor:match.start()]
        residual.append(segment)
        out.append(segment)          # 标签之间的原文必须保留，否则 prompt 会被改坏
        name = match.group(1).lower()
        raw = match.group(2)
        needed = 2 if name == "point" else 4
        span_text = prompt[match.start():match.end()]

        index = _image_index_before(prompt, match.start(), len(image_sizes))
        if index is None:
            result.issues.append(TagIssue(
                "error",
                f"标签 {span_text} 无法判断属于哪张参考图（本次有 {len(image_sizes)} 张）。"
                f"请在其前面写明「图1 / 图2」等归属，例如：将图1{span_text}…",
            ))
            out.append(span_text)
            cursor = match.end()
            continue

        size = image_sizes[index]
        if size is None:
            result.issues.append(TagIssue(
                "error",
                f"标签 {span_text} 对应的参考图（第 {index + 1} 张）是网络 URL，读不到尺寸，"
                f"无法据此换算坐标。请改用本地图片路径（工具需要读取图片尺寸）",
            ))
            out.append(span_text)
            cursor = match.end()
            continue

        # ── 格式校验 ──
        body = raw.strip()
        if _SEPARATORS.search(body):
            result.issues.append(TagIssue(
                "warning",
                f"标签 {span_text} 用了逗号等分隔符，已按空格兼容处理（推荐写法："
                f"<{name}>" + " ".join(["x"] * needed) + f"</{name}>）",
            ))
            body = _SEPARATORS.sub(" ", body)
        tokens = body.split()

        if len(tokens) != needed:
            hint = ""
            if name == "point" and len(tokens) == 4:
                hint = "（4 个值看起来是框选，请改用 <bbox>x1 y1 x2 y2</bbox>）"
            elif name == "bbox" and len(tokens) == 2:
                hint = "（2 个值看起来是点选，请改用 <point>x y</point>）"
            elif len(tokens) == 3:
                hint = "（<point> 需要 2 个值、<bbox> 需要 4 个值）"
            result.issues.append(TagIssue(
                "error",
                f"标签 {span_text} 的坐标个数不对：<{name}> 需要 {needed} 个值，"
                f"实际给了 {len(tokens)} 个{hint}",
            ))
            out.append(span_text)
            cursor = match.end()
            continue

        if not all(_INT.match(t) for t in tokens):
            bad = next(t for t in tokens if not _INT.match(t))
            result.issues.append(TagIssue(
                "error",
                f"标签 {span_text} 含非整数坐标「{bad}」。坐标必须是整数（不接受小数、单位或百分号）",
            ))
            out.append(span_text)
            cursor = match.end()
            continue

        values = [int(t) for t in tokens]
        width, height = size

        # ── 范围校验 ──
        dims = [width, height] if needed == 2 else [width, height, width, height]
        over = [(v, d) for v, d in zip(values, dims) if v < 0 or v > d - 1]
        if over:
            v, d = over[0]
            result.issues.append(TagIssue(
                "error",
                f"标签 {span_text} 的坐标 {v} 超出图片范围（该方向 {d}px）。"
                f"坐标必须是**原图像素**：左上角 (0,0)，右下角为图片宽高",
            ))
            out.append(span_text)
            cursor = match.end()
            continue

        # ── 疑似错误格式检测 ──
        if needed == 4 and (values[0] > values[2] or values[1] > values[3]):
            result.issues.append(TagIssue(
                "warning", f"标签 {span_text} 的框是反的（左上角大于右下角），已自动纠正顺序",
            ))
            values = [min(values[0], values[2]), min(values[1], values[3]),
                      max(values[0], values[2]), max(values[1], values[3])]
        if needed == 4 and (values[0] == values[2] or values[1] == values[3]):
            result.issues.append(TagIssue(
                "warning", f"标签 {span_text} 的框宽或高为 0，模型可能无法定位区域",
            ))
        # ── 换算 ──
        nums = normalize_coords(width, height, *values)
        tag = "point" if needed == 2 else "bbox"
        out.append(f"<{tag}>{' '.join(str(n) for n in nums)}</{tag}>")
        result.converted += 1
        cursor = match.end()

    residual.append(prompt[cursor:])
    out.append(prompt[cursor:])
    result.prompt = "".join(out)

    # ── 配对之外的可疑片段（只在残留文本里找）──
    seen: set[str] = set()
    for leftover in _ANY_TAG.finditer("".join(residual)):
        snippet = leftover.group(0)
        name_seen = snippet.strip("<>").strip().lstrip("/").split()[0] if snippet.strip("<>").strip() else snippet
        if name_seen in seen:       # 同一处笔误（开/闭标签各出现一次）只报一次
            continue
        seen.add(name_seen)
        inner = snippet.strip("<>").strip()
        name = inner.split()[0] if inner.split() else inner
        if _looks_like_typo(name):
            result.issues.append(TagIssue(
                "warning",
                f"prompt 里有疑似坐标标签的片段 {snippet}——名称写错了？"
                f"正确写法：<point>x y</point> / <bbox>x1 y1 x2 y2</bbox>",
            ))
        elif inner and (any(ch.isdigit() for ch in inner) or name.lower() in ("point", "bbox")):
            result.issues.append(TagIssue(
                "warning",
                f"prompt 里有未闭合或格式可疑的坐标片段 {snippet}——"
                f"正确写法：<point>x y</point> / <bbox>x1 y1 x2 y2</bbox>",
            ))

    return result
