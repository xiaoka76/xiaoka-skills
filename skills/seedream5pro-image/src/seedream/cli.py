"""
Seedream 5.0 Pro 图像生成命令行工具

四个生成子命令按「意图」划分，参数集合即该场景必需的信息：

  seedream draw   "<提示词>"                        文生图
  seedream edit   "<编辑指令>" --images <图...>      图生图 / 交互编辑
  seedream split  <图>                              图层拆分
  seedream cutout <图>                              透明背景素材
  seedream mark   <图> --box ...                    标记预览与坐标标签
  seedream ls / show / replay                       任务记录（可复用）

每次生成都会在数据根目录（``$SEEDREAM_HOME`` 或 ``./.seedream``）落地一条完整记录：
提示词、参考图副本、参数、产物 —— 因此任何一张图都能追回"它是怎么做出来的"。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Annotated, Literal

import typer

from seedream.config import (
    ALPHA_LESS_FORMATS,
    API_KEY,
    MAX_REF_IMAGES,
    SIZE_TIERS,
    resolve_home,
)
from seedream.generate import (
    check_layer_decomposition_limits,
    probe_image_size,
    resolve_image_path,
    single_generate,
)
from seedream.run import (
    RUN_KINDS,
    append_index,
    create_run,
    format_size,
    list_legacy_runs,
    load_run,
    read_index,
    record_input,
    resolve_run,
    save_run,
)
from seedream.tags import ConvertResult, convert_prompt_tags

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Seedream 5.0 Pro 图像生成（自动保存完整生成过程，可复用/可复现）",
)

# ── 参数校验 ──────────────────────────────────────────────────────────────────

_SIZE_PATTERN: re.Pattern[str] = re.compile(r"^(1K|1\.5K|2K|auto|\d+x\d+)$")
_MIN_PIXELS: int = 921600   # 1280x720
_MAX_PIXELS: int = 4624220  # 2048x2048x1.1025


def _validate_size(size: str, *, allow_auto: bool = False, allow_custom: bool = True) -> str:
    """
    校验 --size 参数。

    :param size: 用户输入，支持 ``1K`` / ``1.5K`` / ``2K`` / ``auto`` / ``宽x高``
    :param allow_auto: 是否允许 ``auto``（仅图层拆分场景）
    :param allow_custom: 是否允许自定义 ``宽x高``（图层拆分不支持）
    :return: 校验通过的 size
    :raises typer.Exit: 校验失败
    """
    if not _SIZE_PATTERN.match(size):
        typer.secho(
            f"错误: 无效的分辨率 '{size}'，支持 1K / 1.5K / 2K"
            + (" / auto / 宽x高（如 2048x1024）" if allow_custom else " / auto"),
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    if size == "auto":
        if not allow_auto:
            typer.secho(
                "错误: 分辨率 'auto' 只有图层拆分（seedream split）支持",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(1)
        return size

    if size in SIZE_TIERS:
        return size

    if not allow_custom:
        typer.secho(
            "错误: 图层拆分只支持 1K / 1.5K / 2K / auto，不支持自定义宽x高",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

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


def _apply_prompt_tags(conv: ConvertResult, task: dict) -> None:
    """
    把 prompt 内坐标标签的校验结论落到任务上。

    - 有 error：逐条打印并中止（不带着坏标签去发请求）
    - 有 warning：提示但继续
    - 换算成功：记下原始提示词，把换算后的提示词交给后续流程

    :param conv: :func:`convert_prompt_tags` 的结果
    :param task: 生成任务字典（原地修改 prompt / prompt_received）
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
        task["prompt_received"] = task.get("prompt", "")
        task["prompt"] = conv.prompt


# ── 生成主干（四个子命令共用）────────────────────────────────────────────────


def _validate_inputs(
    images: list[str],
    *,
    background: str,
    layer_decomposition: bool,
) -> None:
    """
    在动手之前拦下「这个意图不成立」的输入组合（不发请求、不建任务目录）。

    - 图层拆分：必须且只能 1 张输入图
    - 透明背景：只能 1 张输入图，且必须带 alpha 通道（jpg/jpeg 天然没有）

    :raises typer.Exit: 校验失败
    """
    if layer_decomposition and len(images) != 1:
        typer.secho(
            f"错误: 图层拆分只支持 1 张输入图（当前 {len(images)} 张）",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(1)

    if background == "transparent":
        if len(images) != 1:
            typer.secho(
                f"错误: 透明背景只支持 1 张输入图（当前 {len(images)} 张）",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(1)
        for ref in images:
            if ref.startswith(("http://", "https://")):
                continue
            if Path(ref).suffix.lower() in ALPHA_LESS_FORMATS:
                typer.secho(
                    f"错误: 透明背景需要带 alpha 通道的输入图，{Path(ref).name} 没有（请改用 png / webp）",
                    fg=typer.colors.RED, err=True,
                )
                raise typer.Exit(1)


def _execute(
    *,
    kind: str,
    prompt: str | None,
    images: list[str] | None,
    size: str,
    output_format: str,
    watermark: bool,
    optimize: str,
    timeout: int,
    layer_decomposition: bool = False,
    background: str = "opaque",
    replayed_from: str | None = None,
) -> dict:
    """
    所有生成子命令的执行主干：建任务记录 → 落参考图 → 发请求 → 归档。

    :param kind: 意图（``draw``/``edit``/``split``/``cutout``），即子命令名
    :param prompt: 提示词，**必须是原始像素标签形态**（图层拆分场景可省略）
    :param images: 参考图（本地路径、data URI 或 http(s) URL）
    :param size: 分辨率档位或自定义宽x高
    :param output_format: ``png`` / ``jpeg``
    :param watermark: 是否加水印
    :param optimize: 提示词优化模式 ``standard`` / ``fast``
    :param timeout: API 超时秒数
    :param layer_decomposition: 图层拆分开关
    :param background: ``opaque`` / ``transparent``
    :param replayed_from: 复现来源的 run id
    :return: 生成结果字典（含 run_id / run_dir / outputs）
    :raises typer.Exit: 参考图缺失或不可读
    """
    if not API_KEY:
        typer.secho("错误: 请设置 ARK_API_KEY 环境变量", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    images = images or []
    if len(images) > MAX_REF_IMAGES:
        typer.secho(f"错误: 最多支持 {MAX_REF_IMAGES} 张参考图", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    _validate_inputs(images, background=background, layer_decomposition=layer_decomposition)

    # ① 参考图校验与解析 —— 放在建目录之前：坏输入（超限/格式不支持）不该留下任务目录
    resolved: list[str] = []
    sizes: list[tuple[int, int] | None] = []
    for ref in images:
        try:
            resolved.append(resolve_image_path(ref))
            # 图层拆分比普通图生图更严（格式仅 png/jpeg、总像素 ≥512x512）：本地先拦，
            # 否则要等接口报错才知道。URL / data URI 读不到本地尺寸，跳过交给接口判断。
            if layer_decomposition and not ref.startswith(("http://", "https://", "data:image/")):
                check_layer_decomposition_limits(ref)
        except (FileNotFoundError, ValueError) as e:
            typer.secho(f"错误: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        sizes.append(None if ref.startswith(("http://", "https://")) else probe_image_size(ref))

    # ② 组装请求
    task: dict = {
        "prompt": prompt or "",
        "size": size,
        "output_format": output_format,
        "watermark": watermark,
        "optimize_prompt_options": {"mode": optimize},
    }
    if layer_decomposition:
        task["layer_decomposition"] = True
    if background != "opaque":
        task["background"] = background
    if resolved:
        task["image"] = resolved if len(resolved) > 1 else resolved[0]

    # ③ 坐标标签校验 + 换算
    # 只有这一个入口：无论首次生成还是 replay，喂进来的都是**原始像素提示词**，
    # 换算后另存为 prompt_sent（仅审计）。这样「0~999 值再次被当像素」的路径根本不存在。
    _apply_prompt_tags(convert_prompt_tags(task["prompt"], sizes), task)
    if len(sizes) == 1 and sizes[0]:
        # 供图层拆分把底图坐标换算回原图像素
        task["input_size"] = list(sizes[0])

    # ④ 建任务目录，并把参考图落盘记录 —— 此后即使生成失败，输入也已被保存、依旧可复用
    run_id, run_directory = create_run()
    created_at = _now()
    inputs: list[dict] = []
    for ref in images:
        try:
            inputs.append(record_input(run_directory, ref))
        except FileNotFoundError as e:
            typer.secho(f"错误: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    params = {
        "size": size,
        "output_format": output_format,
        "watermark": watermark,
        "optimize": optimize,
        "layer_decomposition": layer_decomposition,
        "background": background,
    }
    # 两个提示词，口径必须分开（否则 agent 拿到换算后的值再粘一次 = 静默二次换算）：
    #   prompt      —— CLI 接收的**原始**提示词（含像素标签）→ 复用 / 粘贴用这个
    #   prompt_sent —— 实际发给接口的（已换算）、**仅供审计**，任何时候都不要当输入
    prompt_received = task.get("prompt_received") or task.get("prompt", "")
    data: dict = {
        "run_id": run_id,
        "kind": kind,
        "created_at": created_at,
        "finished_at": None,
        "status": "running",
        "error": None,
        "prompt": prompt_received,
        "prompt_sent": task.get("prompt", ""),
        "params": params,
        "inputs": inputs,
        "outputs": [],
    }
    if replayed_from:
        data["replayed_from"] = replayed_from
    save_run(run_directory, data)

    _print_header(kind, run_id, run_directory, task, inputs, params)

    # ⑤ 发请求
    outputs_dir = str(run_directory / "outputs")
    result = single_generate(task, outputs_dir, timeout=timeout)

    # ⑥ 归档
    data["finished_at"] = _now()
    data["status"] = result.get("status", "error")
    data["error"] = result.get("error")
    records = result.get("records") or []
    data["outputs"] = [
        {
            "index": i + 1,
            "path": rec.get("path"),
            "size": rec.get("size"),
            "output_format": rec.get("output_format"),
            "z_index": rec.get("z_index"),
            "name": rec.get("name"),
            "description": rec.get("description"),
            # 图层坐标分两套口径，用途不同、不要混用：
            #   bbox_base  —— 底图坐标系（还原 / 重组图层用这个，配上 bbox_base_size）
            #   bbox_pixel —— 原输入图坐标系（写进 prompt 用这个）
            "bbox_base": rec.get("bbox_base"),
            "bbox_base_size": rec.get("bbox_base_size"),
            "bbox_pixel": rec.get("bbox_pixel"),
            "prompt_fragment": rec.get("prompt_fragment"),
            "bbox_note": rec.get("bbox_note"),
        }
        for i, rec in enumerate(records)
    ]
    save_run(run_directory, data)
    append_index(data)

    result["run_id"] = run_id
    result["run_dir"] = str(run_directory)
    result["data"] = data
    return result


def _now() -> str:
    """当前 ISO 时间戳。"""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _print_header(
    kind: str,
    run_id: str,
    run_directory: Path,
    task: dict,
    inputs: list[dict],
    params: dict,
) -> None:
    """打印任务头（所有生成子命令输出一致，便于 agent 稳定解析）。"""
    typer.echo(f"  Seedream 5.0 Pro · {kind}")
    typer.echo(f"  任务: {run_id}")
    typer.echo(f"  目录: {run_directory}")
    # 打印人看的那一份：有像素标签时用原始版（换算后的仅供审计）
    shown_prompt = task.get("prompt_received") or task.get("prompt") or ""
    if shown_prompt:
        typer.echo(f"  提示词: {shown_prompt[:100]}{'...' if len(shown_prompt) > 100 else ''}")
    typer.echo(f"  参数: size={params['size']} format={params['output_format']}"
               + (" 图层拆分=开" if params["layer_decomposition"] else "")
               + (" 背景=透明" if params["background"] == "transparent" else ""))
    if inputs:
        typer.echo(f"  参考图: {len(inputs)} 张")
    typer.echo("")


def _print_result(result: dict) -> None:
    """打印生成结果，并在失败时以非零码退出。"""
    data = result.get("data", {})
    if result.get("status") != "success":
        typer.secho(f"  生成失败: {result.get('error')}", fg=typer.colors.RED, err=True)
        typer.secho(f"  记录已保存（输入可复用）: {result.get('run_dir')}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(1)

    outputs = data.get("outputs", [])
    layers = [o for o in outputs if o.get("z_index") is not None]
    if layers:
        base = next((o for o in layers if o["z_index"] == 0), layers[0])
        typer.secho("  生成成功!", fg=typer.colors.GREEN)
        typer.echo(f"  底图: {base['path']}")
        rest = [o for o in layers if o["z_index"] != 0]
        typer.echo(f"  图层: {len(rest)} 个")
        for rec in rest:
            px = rec.get("bbox_pixel")
            box_str = f" bbox(原图像素)={' '.join(str(v) for v in px)}" if px else ""
            typer.echo(f"    - L{rec['z_index']} {rec.get('name') or ''}{box_str}")
            if rec.get("prompt_fragment"):
                typer.echo(f"        可直接粘进 prompt: {rec['prompt_fragment']}")
            if rec.get("bbox_note"):
                typer.echo(f"        注意: {rec['bbox_note']}")
        typer.echo("")
        typer.echo("  上面的标签是**原图像素**，直接粘进 prompt 即可（seedream edit 会自动换算）：")
        typer.echo('    seedream edit "把图1<bbox>…</bbox>区域改为…，其他部分不变" --images <原图>')
    else:
        typer.secho("  生成成功!", fg=typer.colors.GREEN)
        for rec in outputs:
            size = f" ({format_size(os.path.getsize(rec['path']))})" if rec.get("path") and os.path.exists(rec["path"]) else ""
            typer.echo(f"  图片: {rec['path']}{size}")

    typer.echo(f"  记录: {os.path.join(result['run_dir'], 'run.json')}")
    typer.echo("")
    typer.echo(f"  复用: seedream show {result['run_id']}  ·  复现: seedream replay {result['run_id']}")


# ── 生成子命令 ────────────────────────────────────────────────────────────────

_SizeOpt = Annotated[str, typer.Option("--size", "-s", help="分辨率: 1K / 1.5K / 2K / 宽x高")]
# 图层拆分不支持自定义宽x高，帮助文案要分开写，否则 --help 会承诺一个用不了的能力
_SplitSizeOpt = Annotated[str, typer.Option("--size", "-s", help="分辨率: 1K / 1.5K / 2K / auto（不支持自定义宽x高）")]
_FormatOpt = Annotated[Literal["png", "jpeg"], typer.Option("--format", help="输出格式")]
_WatermarkOpt = Annotated[bool, typer.Option("--watermark", help="启用水印（默认关闭）")]
_OptimizeOpt = Annotated[Literal["standard", "fast"], typer.Option("--optimize", help="提示词优化模式")]
_TimeoutOpt = Annotated[int, typer.Option("--timeout", "-t", help="API 超时秒数")]


@app.command()
def draw(
    prompt: Annotated[str, typer.Argument(help="提示词（用连贯自然语言描述画面）")],
    size: _SizeOpt = "2K",
    output_format: _FormatOpt = "png",
    watermark: _WatermarkOpt = False,
    optimize: _OptimizeOpt = "standard",
    timeout: _TimeoutOpt = 300,
) -> None:
    """
    文生图 —— 只给提示词，从零生成一张图。

    示例：

      seedream draw "一只戴贝雷帽的橘猫坐在窗台上，午后逆光，胶片质感"
    """
    result = _execute(
        kind="draw",
        prompt=prompt,
        images=None,
        size=_validate_size(size),
        output_format=output_format,
        watermark=watermark,
        optimize=optimize,
        timeout=timeout,
    )
    _print_result(result)


@app.command()
def edit(
    prompt: Annotated[str, typer.Argument(help="编辑指令（用「图1/图2」指代参考图；可内嵌 <bbox>…</bbox> 像素坐标标签）")],
    images: Annotated[list[str], typer.Option("--images", help="参考图（本地路径或 URL，可多次指定，最多 10 张）")],
    size: _SizeOpt = "2K",
    output_format: _FormatOpt = "png",
    watermark: _WatermarkOpt = False,
    optimize: _OptimizeOpt = "standard",
    timeout: _TimeoutOpt = 300,
) -> None:
    """
    图生图 / 交互编辑 —— 给一张或多张参考图加编辑指令。

    局部改动建议先用 ``seedream mark`` 读出像素坐标，再把标签粘进指令。
    显式声明要保持不变的部分，效果更稳。

    示例：

      seedream edit "把图1的水杯换成白瓷马克杯，保持手部姿势与画面其他部分不变" --images photo.png

      seedream edit "把图1<bbox>820 520 1180 860</bbox>区域换成白瓷马克杯" --images photo.png

      seedream edit "将图1的人物放到图2的庭院场景中，光影自然融合" --images a.png --images b.png
    """
    result = _execute(
        kind="edit",
        prompt=prompt,
        images=list(images),
        size=_validate_size(size),
        output_format=output_format,
        watermark=watermark,
        optimize=optimize,
        timeout=timeout,
    )
    _print_result(result)


@app.command()
def split(
    image: Annotated[str, typer.Argument(help="要拆分的图片（限 1 张）")],
    prompt: Annotated[str | None, typer.Option("--prompt", "-p", help="可选：指定拆分意图，不传则自动识别主要元素")] = None,
    size: _SplitSizeOpt = "auto",
    output_format: _FormatOpt = "png",
    watermark: _WatermarkOpt = False,
    optimize: _OptimizeOpt = "standard",
    timeout: _TimeoutOpt = 300,
) -> None:
    """
    图层拆分 —— 把一张图拆成 1 张底图 + 最多 16 个透明图层。

    每个图层带名称、描述和 bounding_box；命令会顺便给出**原图像素**的
    ``<bbox>`` 标签，可粘进 ``seedream edit`` 精修某个图层。

    每次请求预扣 17 IPM，比普通生成贵。

    示例：

      seedream split poster.png

      seedream split poster.png --size 2K -p "只拆分前景物体与文字"
    """
    result = _execute(
        kind="split",
        prompt=prompt,
        images=[image],
        size=_validate_size(size, allow_auto=True, allow_custom=False),
        output_format=output_format,
        watermark=watermark,
        optimize=optimize,
        timeout=timeout,
        layer_decomposition=True,
    )
    _print_result(result)


@app.command()
def cutout(
    image: Annotated[str, typer.Argument(help="要抠出主体的图片（限 1 张，需含透明通道，如 png）")],
    prompt: Annotated[str, typer.Option("--prompt", "-p", help="可选：提取要求")] = "保留主体，清理边缘，输出干净的透明背景素材图，柔和侧光",
    size: _SizeOpt = "2K",
    watermark: _WatermarkOpt = False,
    optimize: _OptimizeOpt = "standard",
    timeout: _TimeoutOpt = 300,
) -> None:
    """
    透明背景素材 —— 从图片中抠出主体，输出带 alpha 通道的 PNG。

    输入必须是带透明通道的格式（png / webp）；jpg 没有 alpha 通道，会被本地拦下。

    示例：

      seedream cutout product.png
    """
    result = _execute(
        kind="cutout",
        prompt=prompt,
        images=[image],
        size=_validate_size(size),
        output_format="png",  # 透明背景必须是 png，不给选项以免误用
        watermark=watermark,
        optimize=optimize,
        timeout=timeout,
        background="transparent",
    )
    _print_result(result)


# ── mark 子命令 ──────────────────────────────────────────────────────────────


def _parse_coords(raw: str, count: int, kind: str) -> tuple[list[int], str]:
    """
    解析坐标参数，支持内联标签（``200,180`` 或 ``200,180:手部``）。

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
    image: Annotated[str, typer.Argument(help="原图路径（不支持 URL，先下载到本地）")],
    point: Annotated[list[str] | None, typer.Option("--point", help="点选坐标 x,y（像素，可多次；可写 x,y:标签）")] = None,
    box: Annotated[list[str] | None, typer.Option("--box", help="框选坐标 x1,y1,x2,y2（像素，可多次；可写 x1,y1,x2,y2:标签）")] = None,
    grid: Annotated[bool, typer.Option("--grid/--no-grid", help="预览图是否叠加坐标网格（默认开启）")] = True,
    plain: Annotated[bool, typer.Option("--plain", help="提交模式：输出原图尺寸的纯标记图，可直接当参考图传给模型")] = False,
    output: Annotated[str | None, typer.Option("--out", "-o", help="输出路径（默认 <数据根>/mark/<id>.jpg；后缀决定格式，.png 无损）")] = None,
    max_edge: Annotated[int | None, typer.Option("--max-edge", help="输出最长边上限（默认自动，达 2MB 预览上限时自动降档；0=强制原始尺寸且不降档）")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="以 JSON 输出结果，便于程序化处理")] = False,
) -> None:
    """
    在图片上画标记并输出坐标标签，供编辑前核对位置。

    坐标一律用**图片像素**（用 --grid 网格读数即可）；标签可直接粘进 prompt，
    其余由 seedream edit 自动处理。

    典型用法：

      # 1) 先看网格，读出要编辑区域的像素坐标
      seedream mark photo.png

      # 2) 画框确认位置对不对（标签用冒号内联）
      seedream mark photo.png --box 820,520,1180,860:手部

      # 3) 需要把标记图本身作为模型输入时（对应官方"任意标记"形式）
      seedream mark photo.png --box 820,520,1180,860 --plain -o marked.png

    分辨率默认自动：按原始尺寸出图，只有在产物达到 2MB 预览上限时才自动降档，
    因此不需要自己算缩放比。要强制原始尺寸（哪怕文件更大）加 --max-edge 0。

    标记编号顺序为「点选在前、框选在后」。
    """
    try:
        from seedream.mark import build_marks, render_preview
    except ImportError as e:  # Pillow 缺失
        typer.secho(
            f"错误: 缺少依赖 Pillow（pip install pillow）: {e}",
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

    mode = "提交模式（无网格/无文字，可直接作为参考图）" if plain else "预览模式（核对坐标用）"
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
        typer.echo(f"  #{item['index']} {kind} [{item['color']}] 像素({pixel})"
                   + (f" {item['label']}" if item["label"] else ""))
    if result["fragments"]:
        typer.echo("")
        typer.echo("  可直接写进 prompt 的坐标标签：")
        typer.echo(f"    {' '.join(result['fragments'])}")


# ── 任务记录子命令 ────────────────────────────────────────────────────────────


@app.command(name="ls")
def list_runs(
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多显示条数")] = 20,
    all_runs: Annotated[bool, typer.Option("--all", help="同时列出 v2 遗留目录（只读，不迁移）")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="以 JSON 输出")] = False,
) -> None:
    """
    列出历史生成任务（最新在前）。

    每条记录都包含提示词、参考图与产物 —— 想复用某张图时先在这里找。

    示例：

      seedream ls                 # 最近 20 条
      seedream ls -n 5 --json     # 程序化取最近 5 条
    """
    entries = read_index(limit=limit)
    legacy = list_legacy_runs() if all_runs else []

    if as_json:
        typer.echo(json.dumps({"runs": entries, "legacy": legacy}, ensure_ascii=False, indent=2))
        return

    if not entries and not legacy:
        typer.echo(f"（还没有任何生成任务）数据根目录: {resolve_home()}")
        return

    typer.echo(f"数据根目录: {resolve_home()}")
    typer.echo("")
    for entry in entries:
        prompt = (entry.get("prompt") or "").replace("\n", " ")[:40]
        typer.echo(
            f"  {entry['run_id']}  {entry['kind']:<6} {entry.get('status', '?'):<7}"
            f" 输入{entry.get('inputs', 0)} 输出{entry.get('outputs', 0)}"
            f"  {prompt}"
        )
    if legacy:
        typer.echo("")
        typer.secho(f"  v2 遗留目录 {len(legacy)} 个（只读列出，不被新命令使用）:", fg=typer.colors.YELLOW)
        for entry in legacy[:limit]:
            typer.echo(f"    {entry['run_id']}  {entry['kind']}  {entry.get('status', '?')}")


@app.command()
def show(
    ref: Annotated[str, typer.Argument(help="任务 id 或 'last'（默认最近一次）")] = "last",
    as_json: Annotated[bool, typer.Option("--json", help="以 JSON 输出完整记录")] = False,
) -> None:
    """
    查看一次生成任务的完整记录：提示词、参数、参考图、产物。

    示例：

      seedream show              # 最近一次
      seedream show last
      seedream show 20261008-143022-a1b2
      seedream show --json       # 交给程序处理
    """
    try:
        run_id, directory = resolve_run(ref)
    except FileNotFoundError as e:
        typer.secho(f"错误: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        data = load_run(directory)
    except (OSError, json.JSONDecodeError) as e:
        typer.secho(f"错误: 无法读取记录 {directory}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    typer.echo(f"任务: {data.get('run_id', run_id)} ({data.get('kind', '?')})")
    typer.echo(f"状态: {data.get('status', '?')}    时间: {data.get('created_at', '?')}")
    if data.get("replayed_from"):
        typer.echo(f"复现自: {data['replayed_from']}")
    # 主字段一律是**原始像素提示词**（可直接复用/粘贴）；换算后的那份只作审计，单独标注
    typer.echo(f"提示词(原图像素，可直接复用): {data.get('prompt') or '(空)'}")
    sent = data.get("prompt_sent") or ""
    if sent and sent != (data.get("prompt") or ""):
        typer.secho(f"实际请求(已换算，仅供审计，勿再粘贴): {sent}", fg=typer.colors.YELLOW)
    params = data.get("params", {})
    typer.echo("参数: " + "  ".join(f"{k}={v}" for k, v in params.items()))
    if data.get("error"):
        typer.secho(f"错误: {data['error']}", fg=typer.colors.RED)

    inputs = data.get("inputs", [])
    typer.echo(f"参考图 ({len(inputs)}):")
    for i, item in enumerate(inputs, 1):
        if item.get("path"):
            typer.echo(
                f"  #{i} {item.get('label') or ''}"
                f"  sha256:{str(item.get('sha256'))[:12]}  -> {item['path']}"
            )
        else:
            typer.echo(f"  #{i} {item.get('source')}（URL，未落盘）")

    outputs = data.get("outputs", [])
    typer.echo(f"产物 ({len(outputs)}):")
    for item in outputs:
        layer = ""
        if item.get("z_index") is not None:
            layer = f" [z_index={item['z_index']}]"
            if item.get("name"):
                layer += f" {item['name']}"
        size = ""
        path = item.get("path")
        if path and os.path.exists(path):
            size = f"（{format_size(os.path.getsize(path))}）"
        typer.echo(f"  #{item.get('index')}{layer}: {path} {size}")
        if item.get("prompt_fragment"):
            typer.echo(f"      可粘进 prompt: {item['prompt_fragment']}")
    typer.echo("")
    typer.echo(f"目录: {directory}")
    if outputs:
        typer.echo(f"复现: seedream replay {data.get('run_id', run_id)}")


@app.command()
def replay(
    ref: Annotated[str, typer.Argument(help="任务 id 或 'last'（默认最近一次）")] = "last",
    run: Annotated[bool, typer.Option("--run", help="真的执行（默认只做预演，不消耗额度）")] = False,
    timeout: _TimeoutOpt = 300,
) -> None:
    """
    复现一次生成任务 —— 用原任务的提示词、参考图与参数重新生成一次。

    **默认只预演**（打印将要发送的内容，不消耗额度），确认无误后加 ``--run`` 真跑。
    复现出的结果会记为一条**新任务**，并标注来源。

    示例：

      seedream replay                # 预演最近一次
      seedream replay --run          # 真跑
      seedream replay 20261008-143022-a1b2 --run
    """
    try:
        source_id, directory = resolve_run(ref)
    except FileNotFoundError as e:
        typer.secho(f"错误: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        data = load_run(directory)
    except (OSError, json.JSONDecodeError) as e:
        typer.secho(f"错误: 无法读取记录 {directory}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    params = data.get("params", {})
    # 复现喂的是**原始像素提示词**（run.json.prompt），重新走一遍校验换算；
    # 绝不使用 prompt_sent —— 那已经是换算后的值，再换算一次就是静默错位。
    prompt = data.get("prompt") or ""
    # 参考图优先用任务目录里的副本（自包含，原图移位也能复现），缺失时退回原始来源
    images: list[str] = []
    for item in data.get("inputs", []):
        if item.get("path") and Path(item["path"]).exists():
            images.append(item["path"])
        elif item.get("source") and not str(item["source"]).startswith("data:"):
            images.append(item["source"])

    typer.echo(f"  复现来源: {data.get('run_id', source_id)} ({data.get('kind', '?')})")
    typer.echo(f"  提示词: {prompt or '(空)'}")
    typer.echo(f"  参数: size={params.get('size')} format={params.get('output_format')}"
               + (" 图层拆分=开" if params.get("layer_decomposition") else "")
               + (" 背景=透明" if params.get("background") == "transparent" else ""))
    typer.echo(f"  参考图: {len(images)} 张")
    for i, p in enumerate(images, 1):
        typer.echo(f"    #{i} {p}")

    if not images and not prompt:
        typer.secho("错误: 该任务既没有提示词也没有参考图，无法复现", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not run:
        typer.echo("")
        typer.secho("  预演结束（未调用 API）。确认无误后加 --run 真跑。", fg=typer.colors.YELLOW)
        return

    typer.echo("")
    result = _execute(
        kind=data.get("kind") if data.get("kind") in RUN_KINDS else "draw",
        prompt=prompt or None,
        images=images,
        size=params.get("size", "2K"),
        output_format=params.get("output_format", "png"),
        watermark=bool(params.get("watermark", False)),
        optimize=params.get("optimize", "standard"),
        timeout=timeout,
        layer_decomposition=bool(params.get("layer_decomposition", False)),
        background=params.get("background", "opaque"),
        replayed_from=data.get("run_id", source_id),
    )
    _print_result(result)
