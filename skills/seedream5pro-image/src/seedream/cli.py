"""
Seedream 5.0 Pro 图像生成命令行工具

统一的 CLI 入口，提供 generate、session、webui 三个子命令组。

用法:
  seedream generate -p "一只猫" --size 2K
  seedream session summary <path>
  seedream webui --port 8000
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Annotated, Literal

import typer
import uvicorn

from seedream.config import (
    ALPHA_LESS_FORMATS,
    API_KEY,
    DEFAULT_OUTPUT_DIR,
    MAX_REF_IMAGES,
    SIZE_TIERS,
)
from seedream.generate import _resolve_image_path, probe_image_size, single_generate
from seedream.tags import ConvertResult, convert_prompt_tags
from seedream.session import (
    add_edit_session_output,
    data_url_summary,
    format_coords,
    init_generate_session,
    load_session,
    save_session,
    update_generate_session,
)
from seedream.webui import create_app, init_session_global

app = typer.Typer(add_completion=False, no_args_is_help=True)

# ── size 参数校验 ─────────────────────────────────────────────────────────────

_SIZE_PATTERN: re.Pattern[str] = re.compile(r"^(1K|1\.5K|2K|auto|\d+x\d+)$")
_MIN_PIXELS: int = 921600   # 1280x720
_MAX_PIXELS: int = 4624220  # 2048x2048x1.1025


def _validate_size(size: str, *, layer_decomposition: bool = False) -> str:
    """
    校验 --size 参数合法性。

    支持格式: "1K" / "1.5K" / "2K" / "宽x高"（如 "2048x1024"）；
    "auto" 仅图层拆分场景可用。
    自定义像素需满足总像素 [921600, 4624220] 且宽高比 [1/16, 16]。

    :param size: 用户输入的 size 字符串
    :param layer_decomposition: 是否开启图层拆分
    :return: 校验通过的 size 字符串
    :raises typer.Exit: 校验失败时退出
    """
    if not _SIZE_PATTERN.match(size):
        typer.secho(
            f"错误: 无效的分辨率格式 '{size}'，支持 1K / 1.5K / 2K / 宽x高（如 2048x1024）",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    if size == "auto":
        if not layer_decomposition:
            typer.secho(
                "错误: 分辨率 'auto' 仅图层拆分场景（--layer-decomposition）可用",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(1)
        return size

    if size in SIZE_TIERS:
        return size

    if layer_decomposition:
        typer.secho(
            "错误: 图层拆分仅支持档位 1K / 1.5K / 2K / auto，不支持自定义宽x高",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    # 自定义像素格式（正则已保证格式为 数字x数字，split 必然为 2 部分）
    w_str, h_str = size.split("x")
    w, h = int(w_str), int(h_str)
    total = w * h
    if total < _MIN_PIXELS or total > _MAX_PIXELS:
        typer.secho(
            f"错误: 总像素 {total} 不在有效范围 [{_MIN_PIXELS}, {_MAX_PIXELS}]",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    ratio = w / h
    if ratio < 1 / 16 or ratio > 16:
        typer.secho(
            f"错误: 宽高比 {ratio:.3f} 不在有效范围 [1/16, 16]",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    return size


def _validate_mode_inputs(
    *,
    layer_decomposition: bool,
    background: str,
    output_format: str,
    image_refs: list[str],
) -> None:
    """
    校验图层拆分 / 透明背景模式对输入图与输出格式的约束。

    - 图层拆分：必须且仅能输入 1 张图片
    - 透明背景：仅图生图、仅 1 张带透明通道的图，输出必须为 png

    :raises typer.Exit: 校验失败时退出
    """
    count = len(image_refs)

    if layer_decomposition and count != 1:
        typer.secho(
            f"错误: 图层拆分仅支持 1 张输入图（当前 {count} 张）",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    if background == "transparent":
        if count != 1:
            typer.secho(
                f"错误: 透明背景仅支持图生图且只允许 1 张带透明通道的输入图（当前 {count} 张）",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(1)
        if output_format == "jpeg":
            typer.secho(
                "错误: 透明背景模式下输出必须为 png，--output-format jpeg 会触发 API 报错",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(1)
        for ref in image_refs:
            if ref.startswith(("http://", "https://", "data:image/")):
                continue
            if os.path.splitext(ref)[1].lower() in ALPHA_LESS_FORMATS:
                typer.secho(
                    f"错误: 透明背景不支持无 alpha 通道的图片: {ref}（请改用 png / webp）",
                    fg=typer.colors.RED, err=True,
                )
                raise typer.Exit(1)


# ── generate 子命令 ──────────────────────────────────────────────────────────


def _coords_to_pixels(coords: list[int], width: int, height: int) -> list[int]:
    """把标注里存的 0~999 值换算成**原图像素**，供对外显示。

    对外一律只暴露像素口径；这个换算只为了让 `session summary` 输出与其他命令一致。

    :param coords: 0~999 坐标（2 个＝点选，4 个＝框选）
    :param width: 所属图片宽
    :param height: 所属图片高
    :return: 原图像素坐标
    """
    dims = ([width, height] * ((len(coords) + 1) // 2))[:len(coords)]
    return [max(0, min(d - 1, round(c / 1000 * d))) for c, d in zip(coords, dims)]


def _apply_prompt_tags(conv: ConvertResult, task: dict) -> None:
    """把 prompt 内坐标标签的校验结论落到任务上。

    - 有 error：把问题逐条打出来并中止（不带着坏标签去请求接口）
    - 有 warning：提示但继续
    - 换算成功：提示一句，并把换算后的 prompt 交给后续流程（原始 prompt 留在 prompt_raw 里备查）

    :param conv: :func:`convert_prompt_tags` 的结果
    :param task: 生成任务字典（原地修改 prompt / prompt_raw）
    :raises typer.Exit: 存在 error 时退出
    """
    for issue in conv.errors:
        typer.secho(f"错误: {issue.message}", fg=typer.colors.RED, err=True)
    if conv.errors:
        raise typer.Exit(1)

    for issue in conv.warnings:
        typer.secho(f"提示: {issue.message}", fg=typer.colors.YELLOW, err=True)

    if conv.converted:
        typer.secho(
            f"  已校验并换算 {conv.converted} 个像素坐标标签（坐标格式由本命令自动处理，无需自己算）",
            fg=typer.colors.GREEN,
        )
        task["prompt_raw"] = task.get("prompt", "")
        task["prompt"] = conv.prompt


def _generate_from_session(
    session_path: str,
    size: str,
    output_format: str,
    watermark: bool,
    optimize: str,
    timeout: int,
    layer_decomposition: bool,
    background: str,
) -> dict:
    """从 session.json 执行图像生成。

    :return: single_generate 的结果字典
    """
    if not os.path.exists(session_path):
        typer.secho(f"错误: session 文件不存在: {session_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        with open(session_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)
    except json.JSONDecodeError as e:
        typer.secho(f"错误: session 文件解析失败: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if "prompt" not in session_data and not layer_decomposition:
        typer.secho("错误: session 文件中缺少 prompt 字段", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    data_urls = [
        img["dataUrl"]
        for img in session_data.get("images", [])
        if img.get("dataUrl")
    ]
    resolved_images = list(data_urls)

    _validate_mode_inputs(
        layer_decomposition=layer_decomposition,
        background=background,
        output_format=output_format,
        image_refs=resolved_images,
    )

    session_path_obj = Path(session_path).resolve()
    session_dir = session_path_obj.parent
    output_dir = str(session_dir / "output")

    typer.echo("  Seedream 5.0 Pro 图像生成（session 模式）")
    typer.echo(f"  Session 文件: {session_path}")
    prompt_text = session_data.get("prompt", "")
    typer.echo(f"  Prompt: {prompt_text[:80]}{'...' if len(prompt_text) > 80 else ''}")
    if resolved_images:
        typer.echo(f"  参考图: {len(resolved_images)} 张")
    typer.echo(f"  输出目录: {output_dir}")
    typer.echo("")

    task: dict = {
        "prompt": prompt_text,
        "size": size,
        "output_format": output_format,
        "watermark": watermark,
    }
    task["optimize_prompt_options"] = {"mode": optimize}
    # 校验 + 换算 session prompt 里的像素坐标标签（尺寸取自 session 记录的原图尺寸）
    session_images = [img for img in session_data.get("images", []) if img.get("dataUrl")]
    sizes = [
        (img.get("naturalWidth"), img.get("naturalHeight"))
        if img.get("naturalWidth") and img.get("naturalHeight") else None
        for img in session_images
    ]
    _apply_prompt_tags(convert_prompt_tags(prompt_text, sizes), task)
    if layer_decomposition:
        task["layer_decomposition"] = True
    if background != "opaque":
        task["background"] = background
    if resolved_images:
        task["image"] = resolved_images if len(resolved_images) > 1 else resolved_images[0]

    result = single_generate(task, timeout=timeout, output_dir=output_dir)
    add_edit_session_output(session_path, result)
    return result


def _generate_from_prompt(
    prompt: str | None,
    images: list[str] | None,
    size: str,
    output_format: str,
    watermark: bool,
    optimize: str,
    timeout: int,
    layer_decomposition: bool,
    background: str,
) -> tuple[dict, str]:
    """从 prompt 执行图像生成。

    :return: (result, output_dir) 元组
    """
    task: dict = {
        "prompt": prompt or "",
        "size": size,
        "output_format": output_format,
        "watermark": watermark,
    }
    task["optimize_prompt_options"] = {"mode": optimize}
    if layer_decomposition:
        task["layer_decomposition"] = True
    if background != "opaque":
        task["background"] = background

    if images:
        if len(images) > MAX_REF_IMAGES:
            typer.secho(f"错误: 最多支持 {MAX_REF_IMAGES} 张参考图", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        resolved = []
        for path in images:
            try:
                resolved.append(_resolve_image_path(path))
            except (FileNotFoundError, ValueError) as e:
                typer.secho(f"错误: {e}", fg=typer.colors.RED, err=True)
                raise typer.Exit(1)

        _validate_mode_inputs(
            layer_decomposition=layer_decomposition,
            background=background,
            output_format=output_format,
            image_refs=images,
        )

        task["image"] = resolved if len(resolved) > 1 else resolved[0]
        # 校验 + 换算 prompt 里的像素坐标标签（URL 类参考图读不到尺寸，换算会明确报错）
        sizes = [
            None if p.startswith(("http://", "https://", "data:image/")) else probe_image_size(p)
            for p in images
        ]
        if len(sizes) == 1 and sizes[0]:
            task["input_size"] = list(sizes[0])   # 供图层拆分把底图坐标换算回原图像素
        _apply_prompt_tags(convert_prompt_tags(prompt or "", sizes), task)
    else:
        _validate_mode_inputs(
            layer_decomposition=layer_decomposition,
            background=background,
            output_format=output_format,
            image_refs=[],
        )

    session_data, session_path = init_generate_session(task)
    gen_session_id = session_data["session_id"]
    output_dir = str(Path(DEFAULT_OUTPUT_DIR) / "generate" / gen_session_id / "output")

    typer.echo("  Seedream 5.0 Pro 图像生成")
    typer.echo(f"  会话 ID: {gen_session_id}")
    typer.echo(f"  Session 文件: {session_path}")
    if prompt:
        typer.echo(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    typer.echo(f"  Size: {size}")
    typer.echo(f"  输出目录: {output_dir}")
    typer.echo(f"  格式: {output_format}")
    if images:
        typer.echo(f"  参考图: {len(images)} 张")
    if watermark:
        typer.echo("  水印: 开启")
    if layer_decomposition:
        typer.echo("  模式: 图层拆分")
    if background != "opaque":
        typer.echo("  背景: 透明通道")
    typer.echo(f"  优化模式: {optimize}")
    typer.echo("")

    update_generate_session(session_path, "running", {"error": None})
    result = single_generate(task, timeout=timeout, output_dir=output_dir)

    if result["status"] == "success":
        update_generate_session(session_path, "success", result)
    else:
        update_generate_session(session_path, "error", result)

    return result, output_dir


def _print_result(result: dict) -> None:
    """输出生成结果到终端。"""
    if result["status"] == "success":
        typer.secho("  生成成功!", fg=typer.colors.GREEN)
        size_kb = os.path.getsize(result["image_path"]) / 1024 if os.path.exists(result["image_path"]) else 0
        if result.get("layers"):
            base = result["layers"][0]
            typer.echo(f"  底图: {base['path']}")
            layers = result["layers"][1:]
            typer.echo(f"  图层: {len(layers)} 个")
            for rec in layers:
                px = rec.get("bbox_pixel")
                box_str = f" bbox(原图像素)={px}" if px else ""
                typer.echo(f"    - L{rec['z_index']} {rec.get('name') or ''}{box_str}")
                if rec.get("prompt_fragment"):
                    typer.echo(f"        可直接粘进 prompt: {rec['prompt_fragment']}")
                if rec.get("bbox_note"):
                    typer.echo(f"        注意: {rec['bbox_note']}")
            if any(rec.get("prompt_fragment") for rec in layers):
                typer.echo("")
                typer.echo("  上面的标签是**原图像素**，直接粘进 prompt 即可；")
                typer.echo("  seedream generate 会校验坐标标签并自动转成接口需要的格式（无需自己算）：")
                typer.echo('    seedream generate --images <原图> -p "把图1<bbox>…</bbox>区域改为…，其他部分不变"')
        else:
            typer.echo(f"  图片: {result['image_path']} ({size_kb:.0f} KB)")
        typer.echo(f"  元数据: {result['metadata_path']}")
        if len(result.get("all_images", [])) > 1 and not result.get("layers"):
            typer.echo(f"  共 {len(result['all_images'])} 张图片")
    else:
        typer.secho(f"  生成失败: {result['error']}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def generate(
    prompt: Annotated[str | None, typer.Option("--prompt", "-p", help="提示词 / 编辑指令（与 --session 互斥）")] = None,
    session: Annotated[str | None, typer.Option("--session", "-S", help="从 session.json 文件读取 prompt 和图片路径（与 --prompt 互斥）")] = None,
    images: Annotated[list[str] | None, typer.Option("--images", help="参考图（URL 或本地路径，可多次指定，最多 10 张）")] = None,
    size: Annotated[str, typer.Option("--size", "-s", help="分辨率: 1K / 1.5K / 2K / 宽x高（图层拆分另支持 auto，默认 2K）")] = "2K",
    output_format: Annotated[Literal["png", "jpeg"], typer.Option("--output-format", help="输出格式（图层拆分只作用于底图，图层恒为 png）")] = "png",
    watermark: Annotated[bool, typer.Option("--watermark", help="启用水印（默认关闭）")] = False,
    optimize: Annotated[Literal["standard", "fast"], typer.Option("--optimize", help="提示词优化模式（默认 standard）")] = "standard",
    layer_decomposition: Annotated[bool, typer.Option("--layer-decomposition", help="图层拆分：把单张图拆成 1 底图 + 最多 16 个透明图层（仅支持 1 张输入图）")] = False,
    background: Annotated[Literal["opaque", "transparent"], typer.Option("--background", help="背景模式（transparent 仅图生图且输入需带透明通道，输出恒为 png）")] = "opaque",
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="API 超时秒数（默认 300）")] = 300,
) -> None:
    """
    Seedream 5.0 Pro 图像生成 - 文生图 / 图生图 / 交互编辑 / 图层拆分，自动保存到本地。

    参考图通过 --images 多次指定，例如：

      seedream generate -p "..." --images url1 --images url2

    图层拆分示例（prompt 可省略，模型自动识别主要元素）：

      seedream generate --layer-decomposition --images ./poster.png --size 2K

    输出目录结构:
      .seedream/generate/<session_id>/output/   (普通模式)
      .seedream/edit/<session_id>/output/        (session 模式)
    """
    if not API_KEY:
        typer.secho("错误: 请设置 ARK_API_KEY 环境变量", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if prompt and session:
        typer.secho("错误: --prompt 和 --session 不能同时使用", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not prompt and not session:
        # 图层拆分场景下 prompt 可选：不传时模型自动识别主要元素
        if not (layer_decomposition and images):
            typer.secho(
                "错误: 请提供 --prompt 或 --session（图层拆分场景可只提供 --images）",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(1)

    # 校验 size 参数
    validated_size = _validate_size(size, layer_decomposition=layer_decomposition)

    if session:
        result = _generate_from_session(
            session, validated_size, output_format, watermark, optimize, timeout,
            layer_decomposition, background,
        )
    else:
        result, _ = _generate_from_prompt(
            prompt, images, validated_size, output_format, watermark, optimize, timeout,
            layer_decomposition, background,
        )

    _print_result(result)


# ── mark 子命令 ──────────────────────────────────────────────────────────────


def _parse_coords(raw: str, count: int, kind: str) -> tuple[list[int], str]:
    """解析坐标参数，支持内联标签。

    形如 ``200,180`` 或 ``200,180:手部``（标签用半角/全角冒号分隔）。

    :return: (坐标列表, 标签) 元组
    """
    body, _, label = raw.replace("：", ":").partition(":")
    parts = [p.strip() for p in body.replace("，", ",").split(",") if p.strip() != ""]
    if len(parts) != count:
        typer.secho(
            f"错误: {kind} 需要 {count} 个数字（当前 {len(parts)} 个）: {raw}",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)
    try:
        return [int(p) for p in parts], label.strip()
    except ValueError:
        typer.secho(f"错误: {kind} 含非法数字: {raw}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def mark(
    image: Annotated[str, typer.Option("--image", "-i", help="原图路径（URL 不支持，先下载到本地）")],
    point: Annotated[list[str] | None, typer.Option("--point", help="点选坐标 x,y（像素，可多次指定；可写 x,y:标签）")] = None,
    box: Annotated[list[str] | None, typer.Option("--box", help="框选坐标 x1,y1,x2,y2（像素，可多次指定；可写 x1,y1,x2,y2:标签）")] = None,
    grid: Annotated[bool, typer.Option("--grid/--no-grid", help="预览图是否叠加坐标网格（默认开启）")] = True,
    plain: Annotated[bool, typer.Option("--plain", help="提交模式：输出原图尺寸的纯标记图，可直接当 --images 传给模型")] = False,
    output: Annotated[str | None, typer.Option("--out", "-o", help="输出路径（默认 .seedream/mark/<id>.jpg；后缀决定格式，.png 为无损）")] = None,
    max_edge: Annotated[int | None, typer.Option("--max-edge", help="输出最长边上限（默认自动：按原始尺寸渲染，产物达 2MB 预览上限时自动降档；0=强制原始尺寸且不降档）")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="以 JSON 输出结果，便于程序化处理")] = False,
) -> None:
    """
    在图片上画标记并输出坐标标签，供 agent 交互式编辑前核对位置。

    坐标一律用**图片像素**（用 --grid 网格读数即可）；标签可直接粘进 prompt，
    其余由 seedream generate 自动处理。

    典型用法：

      # 1) 先看网格，读出要编辑区域的像素坐标
      seedream mark --image photo.png

      # 2) 画框确认位置对不对（给有视觉的模型自己看；标签用冒号内联）
      seedream mark --image photo.png --box 820,520,1180,860:手部

      # 3) 需要把标记图本身作为模型输入时（对应官方“任意标记”形式）
      seedream mark --image photo.png --box 820,520,1180,860 --plain -o marked.png

    分辨率默认自动：按原始尺寸出图，只有在产物达到 2MB 预览上限时才自动降档，
    因此不需要自己算缩放比。要强制原始尺寸（哪怕文件更大）加 --max-edge 0。

    坐标默认按像素解析（`--point x,y` / `--box x1,y1,x2,y2`），可用冒号跟一个可读标签
    （`--box 120,180,640,760:手部`）。标记编号顺序为「点选在前、框选在后」。
    """
    try:
        from seedream.mark import build_marks, render_preview
    except ImportError as e:  # Pillow 缺失
        typer.secho(
            f"错误: 缺少依赖 Pillow（pip install pillow / uv tool install --force .）: {e}",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    parsed_points = [_parse_coords(raw, 2, "点选坐标 --point") for raw in (point or [])]
    parsed_boxes = [_parse_coords(raw, 4, "框选坐标 --box") for raw in (box or [])]
    points = [coords for coords, _ in parsed_points]
    boxes = [coords for coords, _ in parsed_boxes]
    point_labels = [label for _, label in parsed_points]
    box_labels = [label for _, label in parsed_boxes]

    if not points and not boxes and plain:
        typer.secho(
            "错误: --plain 需要至少一个 --point 或 --box（纯网格图请去掉 --plain）",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    # 先探测图片尺寸，用于校验像素坐标是否越界
    try:
        from PIL import Image

        with Image.open(image) as probe:
            image_size = probe.size
    except FileNotFoundError:
        typer.secho(f"错误: 原图不存在: {image}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except OSError as e:
        typer.secho(f"错误: 无法读取图片（格式不支持？）: {image} ({e})", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        marks = build_marks(points, boxes, image_size,
                            point_labels=point_labels, box_labels=box_labels)
    except ValueError as e:
        typer.secho(f"错误: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        result = render_preview(image, marks, grid=grid, output_path=output, plain=plain,
                                max_edge=max_edge)
    except (FileNotFoundError, ValueError) as e:
        typer.secho(f"错误: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if as_json:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    mode = "提交模式（无网格/无文字，可直接作为 --images）" if plain else "预览模式（给模型核对坐标用）"
    typer.secho("  标记图已生成", fg=typer.colors.GREEN)
    typer.echo(f"  模式: {mode}")
    typer.echo(f"  图片: {result['preview_path']}")
    typer.echo(f"  原图尺寸: {result['image_size'][0]}x{result['image_size'][1]}"
               f"  输出: {result['output_size'][0]}x{result['output_size'][1]}"
               + (f"（缩放 {result['scale']:.2f}x）" if result['scale'] < 1 else ""))
    if result["grid"]:
        typer.echo("  网格: 开启（刻度数字为像素坐标，位于图片外留白区）")
    for warning in result.get("warnings", []):
        typer.secho(f"  提示: {warning}", fg=typer.colors.YELLOW, err=True)
    for item in result["marks"]:
        pixel = " ".join(str(v) for v in item["pixel"])
        kind = "点选" if item["kind"] == "point" else "框选"
        # 只显示像素口径，避免同一份数据出现两种写法
        typer.echo(f"  #{item['index']} {kind} [{item['color']}] 像素({pixel})"
                   + (f" {item['label']}" if item["label"] else ""))
    if result["fragments"]:
        typer.echo("")
        typer.echo("  可直接写进 prompt 的坐标标签：")
        typer.echo(f"    {' '.join(result['fragments'])}")


# ── session 子命令组 ────────────────────────────────────────────────────────

session_app = typer.Typer(add_completion=False, help="Session 读写工具")
app.add_typer(session_app, name="session")


@session_app.command()
def summary(
    session_path: Annotated[str, typer.Argument(help="session.json 文件路径")],
) -> None:
    """
    输出 session 结构化摘要。

    包含 session_id、状态机状态、图片列表及尺寸、标注列表、prompt（截断 80 字符）。
    """
    data = load_session(session_path)

    session_id = data.get("session_id", "")
    typer.echo(f"Session: {session_id[:6]}")

    sm = data.get("state_machine", {})
    current_state = sm.get("current_state", "unknown")
    typer.echo(f"State: {current_state}")

    images = data.get("images", [])
    typer.echo(f"Images: {len(images)} 张")
    for img in images:
        label = img.get("inputLabel", "?")
        name = img.get("name", "?")
        w = img.get("naturalWidth", "?")
        h = img.get("naturalHeight", "?")
        b64_info = data_url_summary(img.get("dataUrl", ""))
        typer.echo(f"  - {label}: {name} ({w}x{h}) {b64_info}")

    annotations = data.get("annotations", [])
    typer.echo(f"Annotations: {len(annotations)} 个")
    for ann in annotations:
        ann_id = ann.get("id", "?")
        ann_type = ann.get("type", "?")
        img_label = ann.get("image_label", "?")
        coords = ann.get("normalized_coords", [])
        owner = next((i for i in images if i.get("inputLabel") == img_label), None)
        if coords and owner and owner.get("naturalWidth") and owner.get("naturalHeight"):
            coords = _coords_to_pixels(coords, owner["naturalWidth"], owner["naturalHeight"])
        coords_str = format_coords(coords)
        typer.echo(f"  - #{ann_id} {ann_type} {img_label}(像素): {coords_str}")

    prompt = data.get("prompt", "")
    typer.echo(f"Prompt: {prompt}")

    user_intent = data.get("user_intent", "")
    if user_intent:
        typer.echo(f"User Intent: {user_intent}")


@session_app.command(name="set-prompt")
def set_prompt(
    session_path: Annotated[str, typer.Argument(help="session.json 文件路径")],
    prompt: Annotated[str, typer.Option("--prompt", "-p", help="新的 prompt 内容")],
) -> None:
    """更新 session.json 中的 prompt 字段并写回文件。"""
    data = load_session(session_path)
    data["prompt"] = prompt
    save_session(session_path, data)


@session_app.command(name="list-images")
def list_images(
    session_path: Annotated[str, typer.Argument(help="session.json 文件路径")],
) -> None:
    """
    列出所有图片的信息（名称、尺寸、dataUrl 摘要）。

    图片以 base64 格式嵌入 session.json 中，不再有独立文件路径。
    """
    data = load_session(session_path)
    images = data.get("images", [])
    if not images:
        typer.echo("（无图片）")
        return
    for img in images:
        label = img.get("inputLabel", "?")
        name = img.get("name", "?")
        w = img.get("naturalWidth", "?")
        h = img.get("naturalHeight", "?")
        b64_info = data_url_summary(img.get("dataUrl", ""))
        typer.echo(f"{label}: {name} ({w}x{h}) {b64_info}")


# ── webui 子命令 ─────────────────────────────────────────────────────────────


@app.command()
def webui(
    port: Annotated[int, typer.Option("--port", "-p", help="端口号（默认 8000）")] = 8000,
    host: Annotated[str, typer.Option("--host", help="绑定的主机地址（默认 127.0.0.1；设为 0.0.0.0 可远程访问）")] = "127.0.0.1",
    preload: Annotated[list[str] | None, typer.Option("--preload", help="预加载图片路径（可多次指定）")] = None,
) -> None:
    """
    Seedream 5.0 Pro 交互编辑 WebUI - 图片上传、点选/框选标注、编辑意图保存

    默认仅监听本机回环地址（127.0.0.1）以保证安全。如需从局域网访问，
    显式传入 --host 0.0.0.0。
    """
    preload_paths = preload or []

    # 确保输出目录存在
    Path(DEFAULT_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    typer.echo("  Seedream 5.0 Pro 交互编辑 WebUI")
    typer.echo("  ─────────────────────────────────────")
    session_info = init_session_global(preload_paths)
    session_id = session_info.get("id", "")
    typer.echo(f"  会话 ID: {session_id}")
    typer.echo(f"  Session 文件: {session_info.get('path', '')}")
    if preload_paths:
        typer.echo(f"  预加载图片: {len(preload_paths)} 张")
    typer.echo("  ─────────────────────────────────────")

    web_app = create_app()
    typer.echo(f"  服务地址: http://{host}:{port}")
    if host in ("0.0.0.0", "::"):
        typer.echo(f"  远程访问: http://<your-ip>:{port}")
    typer.echo("  按 Ctrl+C 停止服务")
    typer.echo("")

    uvicorn.run(web_app, host=host, port=port, log_level="info")