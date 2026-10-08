"""
Seedream 5.0 Pro - 标记预览（agent 交互式编辑辅助）

把 agent 想在图上编辑的位置画成可见标记，并输出可直接写进 prompt 的归一化
坐标标签（``<point>`` / ``<bbox>``），让 agent 能"先看一眼再提交"。

坐标约定（重要）：

- 命令行输入的坐标默认是**图片像素坐标**——agent 从 ``--grid`` 网格上直接读数。
- **归一化（0~999）在本模块内部完成**。模型只认归一化坐标（官方交互编辑指南：
  "前端将操作位置转换为归一化坐标（范围 0~999）"），所以转换必须由工具侧承担，
  不能让 agent 手算。
- 归一化值**不出现在本模块的任何对外输出里**（v3.0 起连 ``--norm`` 输入口也已移除）：
  坐标只有「原图像素」一种形态。

渲染分三层，顺序不可调换：

1. 半透明填充（框选区域底色）
2. 描边（十字准星 / 矩形边框）
3. 标签块（必须最上层，否则会被前面两层的填充覆盖）

注意：PIL 在 RGBA 图层上的绘制是"置位"而非"混合"，同一层里后画的半透明填充会把
先画好的描边整片擦掉（``ImageDraw.Draw(layer, "RGBA")`` 也救不了——该混合模式只对
RGB 目标生效）。因此填充与描边必须分属不同图层。
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import PREVIEW_MAX_BYTES, resolve_home

# 标记配色：高对比、彼此可区分，10 色循环
PALETTE: list[str] = [
    "#ff5c8a", "#7c5cff", "#00a7e1", "#00b894", "#ff9f1c",
    "#e84393", "#2d9cdb", "#9b5de5", "#f15bb5", "#43aa8b",
]

# 拉丁字体：数字刻度用，字形更紧凑清晰
LATIN_FONTS: list[str] = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

# 中日韩字体：标签里出现中文时必须换用，否则会渲染成"豆腐块"
CJK_FONTS: list[str] = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]

# 网格刻度：每 10% 一条线（0/100% 是图片边界，不画也不标）
GRID_STEPS: int = 10

# 留白只保留**上方**（放横坐标刻度）与**左侧**（放纵坐标刻度）两侧；
# 右侧与下方不放任何东西，直接省掉——画布越小，视觉模型读图消耗的 token 越少。
MARGIN_MIN: int = 34

# 刻度字号相对显示尺寸的比例（与留白解耦，避免循环依赖）
TICK_FONT_RATIO: float = 0.0135

# 标签块与标记之间的间距、以及标签之间的避让间距
CHIP_GAP: int = 6
CHIP_PAD_X: int = 8
CHIP_PAD_Y: int = 5


@dataclass
class Mark:
    """一个待绘制标记，坐标一律是原图像素。"""

    kind: str                      # "point" | "bbox"
    px: list[int]                  # 原图像素坐标（point: [x,y]；bbox: [x1,y1,x2,y2]）
    label: str = ""
    color: tuple[int, int, int] = (255, 255, 255)

    def fragment(self) -> str:
        """可直接粘进 prompt 的坐标标签片段。

        **写的是原图像素**（与全流程口径一致）；归一化由 `seedream generate` 在发送前
        校验并换算，agent 不需要知道归一化值。
        """
        coords = " ".join(str(v) for v in self.px)
        tag = "point" if self.kind == "point" else "bbox"
        return f"<{tag}>{coords}</{tag}>"


# ── 基础工具 ──────────────────────────────────────────────────────────────────


def _first_existing(paths: list[str]) -> str | None:
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def _load_font(
    size: int,
    cjk: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """加载可缩放字体。

    :param size: 字号
    :param cjk: 文本含中文等非拉丁字符时置 True——优先用中日韩字体，否则会渲染成方块
    """
    candidates = CJK_FONTS + LATIN_FONTS if cjk else LATIN_FONTS + CJK_FONTS
    path = _first_existing(candidates)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def _needs_cjk(*texts: str) -> bool:
    """判断文本是否含非 ASCII 字符（需要中文/多语言字体）。"""
    return any(not ch.isascii() for text in texts for ch in text)


def _cjk_available() -> bool:
    return _first_existing(CJK_FONTS) is not None


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


class _ChipPlacer:
    """标签块排布器：候选位择优 + 已放置矩形避让，保证不被遮挡、不出画布。"""

    def __init__(self, bounds: tuple[int, int, int, int]) -> None:
        self.left, self.top, self.right, self.bottom = bounds
        self.placed: list[tuple[int, int, int, int]] = []

    def _fits(self, rect: tuple[int, int, int, int]) -> bool:
        x1, y1, x2, y2 = rect
        if x1 < self.left or y1 < self.top or x2 > self.right or y2 > self.bottom:
            return False
        for px1, py1, px2, py2 in self.placed:
            if x1 < px2 + CHIP_GAP and px1 - CHIP_GAP < x2 and y1 < py2 + CHIP_GAP and py1 - CHIP_GAP < y2:
                return False
        return True

    def place(
        self,
        anchor: tuple[int, int, int, int],
        chip_w: int,
        chip_h: int,
        gap: int,
    ) -> tuple[int, int]:
        """按优先级挑选标签位置，返回标签左上角坐标。"""
        ax1, ay1, ax2, ay2 = anchor
        candidates = [
            (ax1, ay1 - gap - chip_h),              # 1 上方左对齐（首选：不压住标记区域）
            (ax1, ay2 + gap),                       # 2 下方左对齐
            (ax2 - chip_w, ay1 - gap - chip_h),     # 3 上方右对齐
            (ax1 + gap, ay1 + gap),                 # 4 标记内部左上
            (ax2 + gap, ay1),                       # 5 右侧
            (ax2 - chip_w, ay2 + gap),              # 6 下方右对齐
            (ax1, ay2 + gap * 2 + chip_h),          # 7 再往下一行（堆叠避让）
            (ax2 + gap, ay2 - chip_h),              # 8 右侧靠下
        ]
        fallback: tuple[int, int] | None = None
        for cx, cy in candidates:
            cx = _clamp(cx, self.left, max(self.left, self.right - chip_w))
            cy = _clamp(cy, self.top, max(self.top, self.bottom - chip_h))
            rect = (cx, cy, cx + chip_w, cy + chip_h)
            if self._fits(rect):
                self.placed.append(rect)
                return cx, cy
            if fallback is None:
                fallback = (cx, cy)

        # 所有候选都被占了：退化到最后一个候选位，并记录（允许重叠但仍在画布内）
        assert fallback is not None
        cx, cy = fallback
        self.placed.append((cx, cy, cx + chip_w, cy + chip_h))
        return cx, cy


# ── 渲染 ──────────────────────────────────────────────────────────────────────


def _text_width(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, text: str) -> int:
    """测量文本宽度（优先用字体自带度量，退化时按字宽估算）。"""
    try:
        return round(font.getlength(text))
    except (AttributeError, TypeError):
        return round(len(text) * getattr(font, "size", 12) * 0.62)


def _grid_ticks(width: int, height: int) -> tuple[list[int], list[int]]:
    """返回需要标注刻度的横纵坐标（**原图像素**）。

    除了 10%~90% 的内部刻度，还包含边界值：``x = width``（画布右上角）与
    ``y = height``（画布左下角），以及 ``y = 0``。这样 agent 能读到完整的坐标范围。

    ``x = 0`` 不标注：它与左侧纵轴刻度的位置重叠（左上角放不下两个数字）。
    """
    xs = [round(width * i / GRID_STEPS) for i in range(1, GRID_STEPS)] + [width]
    ys = [0] + [round(height * i / GRID_STEPS) for i in range(1, GRID_STEPS)] + [height]
    return xs, ys


def _draw_grid(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    scale: float = 1.0,
    x_ticks: list[int] | None = None,
    y_ticks: list[int] | None = None,
) -> None:
    """在图片区域叠加坐标网格，刻度数字一律画在**图片外的留白区**。

    对齐规则（保证数字既不会压住画面、也不会被裁掉）：

    - **上方刻度（横坐标）**：右对齐于所在竖线（文本整体落在竖线左侧）、贴留白底部（靠下）。
    - **左侧刻度（纵坐标）**：右对齐于图片左边界、文本位于所在横线上方。

    刻度值按**原图像素**标注（``scale`` 为输出缩放比），这样即使预览图被缩小，
    agent 读到的数字依然是可以直接传给 ``--box`` 的原图坐标。
    """
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    line_color = (255, 255, 255, 105)
    line_w = max(1, width // 1400)
    pad = max(4, round(font.size * 0.35))
    ink = (255, 255, 255, 235)

    # 只画上边与左边两条边界线（对应 x=0 / y=0，也是刻度的基准边）。
    # 右边与下边不再单独描线：画布已经贴到图片边缘，再画只会被裁掉一半。
    edge = (255, 255, 255, 160)
    d.line([(left, top), (right - 1, top)], fill=edge, width=line_w)
    d.line([(left, top), (left, bottom - 1)], fill=edge, width=line_w)

    # 内部网格线（0%/100% 边界线由上面两条承担）
    for i in range(1, GRID_STEPS):
        x = left + round(width * i / GRID_STEPS)
        y = top + round(height * i / GRID_STEPS)
        d.line([(x, top), (x, bottom)], fill=line_color, width=line_w)
        d.line([(left, y), (right, y)], fill=line_color, width=line_w)

    # 上方留白：横坐标刻度（右对齐于竖线、靠下贴合图片顶边）
    ty = max(0, top - pad - font.size)
    for value in (x_ticks or []):
        x = left + round(value * scale)   # 原图像素 → 显示坐标
        label = str(value)
        tw = _text_width(font, label)
        tx = _clamp(round(x - pad - tw), 0, canvas.width - tw - 1)
        d.text((tx, ty), label, font=font, fill=ink)

    # 左侧留白：纵坐标刻度（右对齐于图片左边界、位于横线上方）
    for value in (y_ticks or []):
        y = top + round(value * scale)    # 原图像素 → 显示坐标
        label = str(value)
        tw = _text_width(font, label)
        tx = _clamp(round(left - pad - tw), 0, canvas.width - tw - 1)
        d.text((tx, _clamp(round(y - pad - font.size), 0, canvas.height - font.size - 1)),
               label, font=font, fill=ink)

    canvas.alpha_composite(layer)


def _draw_fills(canvas: Image.Image, marks: list[Mark]) -> None:
    """第 1 层：框选区域的半透明底色（单独一层，避免覆盖描边）。"""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for mark in marks:
        if mark.kind == "bbox":
            x1, y1, x2, y2 = mark.px
            d.rectangle([x1, y1, x2, y2], fill=mark.color + (40,))
    canvas.alpha_composite(layer)


def _draw_strokes(canvas: Image.Image, marks: list[Mark], unit: int) -> None:
    """第 2 层：十字准星与矩形边框（白色光晕打底，明暗背景都看得见）。"""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw = max(3, unit)
    halo = lw + max(2, unit // 2)
    halo_color = (255, 255, 255, 235)

    for mark in marks:
        if mark.kind == "point":
            x, y = mark.px
            r = max(14, unit * 4)
            for color, w in ((halo_color, halo), (mark.color + (255,), lw)):
                d.ellipse([x - r, y - r, x + r, y + r], outline=color, width=w)
                d.line([(x - r * 1.8, y), (x + r * 1.8, y)], fill=color, width=w)
                d.line([(x, y - r * 1.8), (x, y + r * 1.8)], fill=color, width=w)
        else:
            x1, y1, x2, y2 = mark.px
            d.rectangle([x1, y1, x2, y2], outline=halo_color, width=halo)
            d.rectangle([x1, y1, x2, y2], outline=mark.color + (255,), width=lw)

    canvas.alpha_composite(layer)


def _draw_chips(
    canvas: Image.Image,
    marks: list[Mark],
    placer: _ChipPlacer,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    unit: int,
) -> None:
    """第 3 层：标签块。必须最后画，否则会被填充/描边盖住。"""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gap = max(CHIP_GAP, unit * 2)
    for index, mark in enumerate(marks, start=1):
        text = f"#{index} {mark.fragment()}"
        if mark.label:
            text += f" {mark.label}"
        text_w = round(d.textlength(text, font=font))
        text_h = font.size
        chip_w, chip_h = text_w + CHIP_PAD_X * 2, text_h + CHIP_PAD_Y * 2
        if mark.kind == "point":
            x, y = mark.px
            r = max(14, unit * 4)
            anchor = (x - r, y - r, x + r, y + r)
        else:
            anchor = tuple(mark.px)  # type: ignore[assignment]
        cx, cy = placer.place(anchor, chip_w, chip_h, gap)
        d.rectangle([cx, cy, cx + chip_w, cy + chip_h], fill=mark.color + (235,))
        d.text((cx + CHIP_PAD_X, cy + CHIP_PAD_Y - font.size // 6), text, font=font,
               fill=(255, 255, 255, 255))
    canvas.alpha_composite(layer)


# ── 对外入口 ──────────────────────────────────────────────────────────────────


def build_marks(
    points: list[list[int]],
    boxes: list[list[int]],
    image_size: tuple[int, int],
    point_labels: list[str] | None = None,
    box_labels: list[str] | None = None,
) -> list[Mark]:
    """把命令行给的坐标整理成 Mark 列表（**坐标一律是原图像素**）。

    标签按**组内顺序**与其所属标记绑定（点选一组、框选一组），因此命令行里
    ``--point 200,180:手部`` 这种内联写法永远不会张冠李戴。

    标记编号顺序：**点选在前、框选在后**。

    :param points: 点选坐标列表，每项 ``[x, y]``（原图像素）
    :param boxes: 框选坐标列表，每项 ``[x1, y1, x2, y2]``（原图像素）
    :param image_size: 原图 ``(宽, 高)``
    :param point_labels: 与 ``points`` 一一对应的标签
    :param box_labels: 与 ``boxes`` 一一对应的标签
    :return: Mark 列表
    :raises ValueError: 坐标数量不对或超出范围
    """
    width, height = image_size
    marks: list[Mark] = []

    for coords in points:
        if len(coords) != 2:
            raise ValueError(f"点选坐标需要 2 个值（x,y），收到 {len(coords)} 个: {coords}")
        x, y = coords
        if not (0 <= x <= width - 1 and 0 <= y <= height - 1):
            raise ValueError(f"点选坐标超出图片范围 {width}x{height}: ({x}, {y})")
        marks.append(Mark("point", [x, y]))

    for coords in boxes:
        if len(coords) != 4:
            raise ValueError(f"框选坐标需要 4 个值（x1,y1,x2,y2），收到 {len(coords)} 个: {coords}")
        if not (0 <= coords[0] <= width - 1 and 0 <= coords[1] <= height - 1
                and 0 <= coords[2] <= width - 1 and 0 <= coords[3] <= height - 1):
            raise ValueError(f"框选坐标超出图片范围 {width}x{height}: {coords}")
        x1, y1, x2, y2 = coords
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        marks.append(Mark("bbox", [x1, y1, x2, y2]))

    for index, mark in enumerate(marks):
        mark.color = _hex_to_rgb(PALETTE[index % len(PALETTE)])

    # 标签分组合并（点选组 + 框选组），避免跨组错位；长度不足时补空串，保证对齐
    plabels = list(point_labels or []) + [""] * (len(points) - len(point_labels or []))
    blabels = list(box_labels or []) + [""] * (len(boxes) - len(box_labels or []))
    for mark, text in zip(marks, plabels + blabels):
        if text:
            mark.label = text

    return marks


def _layout(
    width: int,
    height: int,
    max_edge: int,
    use_grid: bool,
) -> tuple[float, int, int, int, ImageFont.FreeTypeFont | ImageFont.ImageFont | None]:
    """求解输出布局：``(缩放比, 左留白, 上留白, 刻度字号, 刻度字体)``。

    留白只留在**上方**与**左侧**（放刻度数字用），右侧与下方不留——
    那两块本来就没有内容，留着只是白占画布、徒增视觉模型的 token 消耗。

    两个约束同时满足：

    1. **留白要放得下刻度数字**：左留白 ≥ 最宽纵轴数字（如 4 位数的 ``1664``），
       上留白 ≥ 一行刻度字号——否则数字会压进画面。
    2. **最终画布最长边不超过 ``max_edge``**（留白随缩放变化，所以迭代收敛）。

    刻度字号按图片尺寸决定、与留白解耦，避免"字号→留白→字号"的循环依赖。
    """
    if not use_grid:
        scale = min(1.0, max_edge / max(width, height)) if max_edge > 0 else 1.0
        return scale, 0, 0, 0, None

    scale = min(1.0, max_edge / max(width, height)) if max_edge > 0 else 1.0

    def solve(
        scale_value: float,
    ) -> tuple[int, int, int, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
        """按给定缩放比推导 (左留白, 上留白, 字号, 字体)。"""
        disp_w = max(1, round(width * scale_value))
        disp_h = max(1, round(height * scale_value))
        base = max(disp_w, disp_h)
        size = max(12, round(base * TICK_FONT_RATIO))
        fnt = _load_font(size)
        pd = max(4, round(size * 0.35))
        widest_y = _text_width(fnt, str(disp_h))      # 纵轴最宽刻度
        m_left = max(MARGIN_MIN, widest_y + pd * 2, size + pd * 2)
        m_top = max(MARGIN_MIN, size + pd * 2)
        return m_left, m_top, size, fnt

    m_left = m_top = MARGIN_MIN
    font_size, font = 0, None
    for _ in range(10):
        m_left, m_top, font_size, font = solve(scale)
        if max_edge <= 0:
            break
        disp_w = max(1, round(width * scale))
        disp_h = max(1, round(height * scale))
        if max(disp_w + m_left, disp_h + m_top) <= max_edge:
            break
        scale *= max_edge / max(disp_w + m_left, disp_h + m_top)

    # 兜底：确保绝不越界（极端窄长图）
    if max_edge > 0:
        while scale > 0.05:
            disp_w = max(1, round(width * scale))
            disp_h = max(1, round(height * scale))
            m_left, m_top, font_size, font = solve(scale)
            if max(disp_w + m_left, disp_h + m_top) <= max_edge:
                break
            scale *= 0.97

    return scale, m_left, m_top, font_size, font


def render_preview(
    image_path: str,
    marks: list[Mark],
    grid: bool = True,
    output_path: str | None = None,
    plain: bool = False,
    max_edge: int | None = None,
    target_bytes: int | None = None,
) -> dict:
    """渲染带标记的预览图。

    两种用途，输出形态不同：

    - **预览模式（默认）**：加留白 + 坐标网格 + 带坐标文字的标签块，给 agent 核对坐标用。
    - **提交模式（``plain=True``）**：保持原图宽高比、不加留白/网格/文字，只画彩色标记。
      这张图可以直接当 ``--images`` 传给模型（对应官方"任意标记 + 自然语言"的形式）。

    分辨率默认**自动**：按原尺寸渲染，若产物达到 ``target_bytes``（默认 2MB，平台内联
    预览上限）则自动降档重渲染，直到刚好压进限制内——不需要用户先算好缩放比。
    缩放**不影响坐标正确性**：网格刻度始终按**原图像素**标注，归一化坐标也按原图尺寸换算。

    :param image_path: 原图路径
    :param marks: Mark 列表（可为空——只看网格估坐标也是常见用法）
    :param grid: 预览模式下是否叠加坐标网格（默认开启）
    :param output_path: 输出路径，默认写入 ``.seedream/mark/<uid>.jpg``
    :param plain: 提交模式，输出纯标记图（无网格、无文字）
    :param max_edge: 输出最长边上限（像素）。``None`` = 自动（不限分辨率，超体积才降档）；
        ``0`` = 完全按原始尺寸、连自动降档也关掉；正整数 = 先按该上限渲染，仍超体积再降档
    :param target_bytes: 产物体积上限，默认 2MB
    :return: 结果字典，含 preview_path / output_bytes / auto_scaled / marks / fragments
    :raises FileNotFoundError: 原图不存在
    :raises ValueError: Pillow 无法识别图片格式
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"原图不存在: {image_path}")

    try:
        source = Image.open(image_path)
        source.load()
    except OSError as e:
        raise ValueError(f"无法读取图片（Pillow 不支持该格式？）: {image_path} ({e})") from e

    width, height = source.size
    use_grid = grid and not plain
    limit_bytes = PREVIEW_MAX_BYTES if target_bytes is None else target_bytes
    cap = 0 if max_edge is None else max_edge      # 0 = 不缩放
    auto_fit = max_edge != 0                       # 显式传 --max-edge 0 才关掉自动降档

    warnings: list[str] = []

    # 标签含非拉丁字符（如中文）时必须用中日韩字体，否则渲染成"豆腐块"。
    # 这取决于文案、与缩放无关，所以先定下来；不直接改调用方的 marks。
    render_marks = [Mark(m.kind, list(m.px), m.label, m.color) for m in marks]
    chip_texts = [f"#{i} {m.fragment()} {m.label}".strip()
                  for i, m in enumerate(render_marks, start=1)]
    use_cjk_font = _needs_cjk(*chip_texts)
    if use_cjk_font and not _cjk_available():
        warnings.append("系统缺少中日韩字体，标签中的非 ASCII 字符已移除（不影响坐标）")
        for mark in render_marks:
            mark.label = "".join(ch for ch in mark.label if ch.isascii())
        use_cjk_font = _needs_cjk(
            *[f"#{i} {m.fragment()} {m.label}" for i, m in enumerate(render_marks, 1)])

    if output_path is None:
        output_dir = resolve_home() / "mark"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"{uuid.uuid4().hex[:12]}.jpg")
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    suffix = Path(output_path).suffix.lower()

    def compose(cap_px: int) -> dict:
        """按给定最长边上限渲染一张画布（``cap_px=0`` 表示不缩放）。"""
        scale, m_left, m_top, _fs, tick_font = _layout(width, height, cap_px, use_grid)
        disp_w, disp_h = max(1, round(width * scale)), max(1, round(height * scale))
        img = source.resize((disp_w, disp_h), Image.LANCZOS) if scale < 1.0 else source
        canvas = Image.new("RGBA", (disp_w + m_left, disp_h + m_top), (14, 16, 26, 255))
        canvas.alpha_composite(img.convert("RGBA"), (m_left, m_top))
        box = (m_left, m_top, m_left + disp_w, m_top + disp_h)

        # 标记的绘制坐标 = 原图像素坐标 × scale；归一化坐标不受缩放影响
        drawn: list[Mark] = []
        for mark in render_marks:
            px = [round(v * scale) for v in mark.px]
            if mark.kind == "bbox":
                px[2] = max(px[0] + 1, px[2])
                px[3] = max(px[1] + 1, px[3])
            drawn.append(Mark(mark.kind, px, mark.label, mark.color))

        unit = max(2, round(max(disp_w, disp_h) / 900))
        chip_font = _load_font(max(14, round(max(disp_w, disp_h) / 78)), cjk=use_cjk_font)
        x_ticks, y_ticks = _grid_ticks(width, height) if use_grid else ([], [])
        if use_grid and tick_font:
            _draw_grid(canvas, box, tick_font, scale, x_ticks, y_ticks)
        if drawn:
            _draw_fills(canvas, drawn)
            _draw_strokes(canvas, drawn, unit)
            if not plain:
                _draw_chips(canvas, drawn, _ChipPlacer(box), chip_font, unit)
        return {
            "canvas": canvas, "scale": scale, "margin_left": m_left, "margin_top": m_top,
            "disp_w": disp_w, "disp_h": disp_h, "x_ticks": x_ticks, "y_ticks": y_ticks,
        }

    def save(canvas: Image.Image) -> None:
        rgb = canvas.convert("RGB")
        if suffix in (".jpg", ".jpeg", ".webp"):
            rgb.save(output_path, quality=92)
        else:
            rgb.save(output_path, optimize=True)

    state = compose(cap)
    save(state["canvas"])
    auto_scaled = False

    # 自动降档：产物达到体积上限就按"像素数≈文件大小"的比例缩一档重渲染，直到压进限制内
    if auto_fit and limit_bytes > 0:
        for _ in range(8):
            current = os.path.getsize(output_path)
            if current < limit_bytes:
                break
            factor = max(0.55, min(0.95, (limit_bytes / current) ** 0.5 * 0.97))
            longest = max(state["disp_w"], state["disp_h"])
            new_cap = max(320, round(longest * factor))
            if new_cap >= longest:
                break
            state = compose(new_cap)
            save(state["canvas"])
            auto_scaled = True

    output_bytes = os.path.getsize(output_path)
    if auto_scaled:
        warnings.append(
            f"产物超过 {limit_bytes / 1024 / 1024:.0f}MB 预览上限，已自动降到 "
            f"{state['disp_w']}x{state['disp_h']}（{output_bytes / 1024:.0f}KB）；"
            f"要强制原始尺寸请加 --max-edge 0"
        )

    return {
        "status": "success",
        "preview_path": os.path.abspath(output_path),
        "image_path": os.path.abspath(image_path),
        "image_size": [width, height],
        "output_size": list(state["canvas"].size),
        "output_bytes": output_bytes,
        "scale": round(state["scale"], 4),
        "auto_scaled": auto_scaled,
        "grid": use_grid,
        "plain": plain,
        "margin_left": state["margin_left"],
        "margin_top": state["margin_top"],
        "cjk_font": use_cjk_font,
        "warnings": warnings,
        # 只输出像素口径；归一化数值仅作为成品标签出现在 fragments 里（口径统一）
        "tick_labels": {"x": state["x_ticks"], "y": state["y_ticks"]},
        "marks": [
            {
                "index": index,
                "kind": mark.kind,
                "color": "#%02x%02x%02x" % mark.color,
                "pixel": mark.px,
                "label": mark.label,
            }
            for index, mark in enumerate(render_marks, start=1)
        ],
        "fragments": [mark.fragment() for mark in render_marks],
    }
