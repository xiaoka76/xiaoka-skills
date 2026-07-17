"""
Seedream 5.0 Pro 图像生成命令行工具

统一的 CLI 入口，提供 generate、session、webui 三个子命令组。

用法:
  seedream generate -p "一只猫" --size 2K
  seedream session summary <path>
  seedream webui --port 8090
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Literal

import typer
import uvicorn
from dotenv import load_dotenv

from seedream.config import API_KEY, DEFAULT_OUTPUT_DIR, MAX_REF_IMAGES
from seedream.generate import _resolve_image_path, single_generate
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

# 加载 .env 文件
load_dotenv()

app = typer.Typer(add_completion=False, no_args_is_help=True)


# ── generate 子命令 ──────────────────────────────────────────────────────────


@app.command()
def generate(
    prompt: Annotated[str | None, typer.Option("--prompt", "-p", help="提示词 / 编辑指令（与 --session 互斥）")] = None,
    session: Annotated[str | None, typer.Option("--session", "-S", help="从 session.json 文件读取 prompt 和图片路径（与 --prompt 互斥）")] = None,
    images: Annotated[list[str] | None, typer.Option("--images", help="参考图（URL 或本地路径，可多次指定，最多 10 张）")] = None,
    size: Annotated[str, typer.Option("--size", "-s", help="分辨率: 1K / 2K / 宽x高（默认 2K）")] = "2K",
    output_format: Annotated[Literal["png", "jpeg"], typer.Option("--output-format", help="输出格式")] = "png",
    watermark: Annotated[bool, typer.Option("--watermark", help="启用水印（默认关闭）")] = False,
    optimize: Annotated[Literal["standard", "fast"], typer.Option("--optimize", help="提示词优化模式（默认 standard）")] = "standard",
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="API 超时秒数（默认 300）")] = 300,
) -> None:
    """
    Seedream 5.0 Pro 图像生成 - 文生图 / 图生图 / 交互编辑，自动保存到本地。

    参考图通过 --images 多次指定，例如：

      seedream generate -p "..." --images url1 --images url2

    输出目录结构:
      .seedream/generate/<session_id>/output/   (普通模式)
      .seedream/edit/<session_id>/output/        (session 模式)
    """
    if not API_KEY:
        typer.secho("错误: 请设置 ARK_API_KEY 环境变量", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # 互斥校验：--prompt 和 --session 不能同时使用
    if prompt and session:
        typer.secho("错误: --prompt 和 --session 不能同时使用", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not prompt and not session:
        typer.secho("错误: 请提供 --prompt 或 --session", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if session:
        # ── session 模式 ──────────────────────────────────────────────────────
        if not os.path.exists(session):
            typer.secho(f"错误: session 文件不存在: {session}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        try:
            with open(session, "r", encoding="utf-8") as f:
                session_data = json.load(f)
        except json.JSONDecodeError as e:
            typer.secho(f"错误: session 文件解析失败: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        if "prompt" not in session_data:
            typer.secho("错误: session 文件中缺少 prompt 字段", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        # 解析参考图（从 session 中读取 dataUrl，可直接传给 API）
        data_urls = [
            img["dataUrl"]
            for img in session_data.get("images", [])
            if img.get("dataUrl")
        ]
        resolved_images = list(data_urls)

        # 输出到 edit session 的 output/ 目录
        session_path_obj = Path(session).resolve()
        session_dir = session_path_obj.parent
        output_dir = str(session_dir / "output")

        typer.echo("  Seedream 5.0 Pro 图像生成（session 模式）")
        typer.echo(f"  Session 文件: {session}")
        prompt_text = session_data["prompt"]
        typer.echo(f"  Prompt: {prompt_text[:80]}{'...' if len(prompt_text) > 80 else ''}")
        if resolved_images:
            typer.echo(f"  参考图: {len(resolved_images)} 张")
        typer.echo(f"  输出目录: {output_dir}")
        typer.echo("")

        task: dict = {
            "prompt": session_data["prompt"],
            "size": size,
            "output_format": output_format,
            "watermark": watermark,
        }
        task["optimize_prompt_options"] = {"mode": optimize}
        if resolved_images:
            task["image"] = resolved_images if len(resolved_images) > 1 else resolved_images[0]

        result = single_generate(task, timeout=timeout, output_dir=output_dir)

        # 更新 edit session 的输出记录
        add_edit_session_output(session, result)
    else:
        # ── prompt 模式 ───────────────────────────────────────────────────────
        task: dict = {
            "prompt": prompt,
            "size": size,
            "output_format": output_format,
            "watermark": watermark,
        }
        task["optimize_prompt_options"] = {"mode": optimize}

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

            task["image"] = resolved if len(resolved) > 1 else resolved[0]

        # 创建生成会话
        session_data, session_path = init_generate_session(task)
        gen_session_id = session_data["session_id"]
        output_dir = str(Path(DEFAULT_OUTPUT_DIR) / "generate" / gen_session_id / "output")

        typer.echo("  Seedream 5.0 Pro 图像生成")
        typer.echo(f"  会话 ID: {gen_session_id}")
        typer.echo(f"  Session 文件: {session_path}")
        typer.echo(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        typer.echo(f"  Size: {size}")
        typer.echo(f"  输出目录: {output_dir}")
        typer.echo(f"  格式: {output_format}")
        if images:
            typer.echo(f"  参考图: {len(images)} 张")
        if watermark:
            typer.echo("  水印: 开启")
        typer.echo(f"  优化模式: {optimize}")
        typer.echo("")

        # 更新 session 状态为 running
        update_generate_session(session_path, "running", {"error": None})

        result = single_generate(task, timeout=timeout, output_dir=output_dir)

        # 更新 session 状态
        if result["status"] == "success":
            update_generate_session(session_path, "success", result)
        else:
            update_generate_session(session_path, "error", result)

    # ── 输出结果 ──────────────────────────────────────────────────────────────
    if result["status"] == "success":
        typer.secho("  生成成功!", fg=typer.colors.GREEN)
        size_kb = os.path.getsize(result["image_path"]) / 1024 if os.path.exists(result["image_path"]) else 0
        typer.echo(f"  图片: {result['image_path']} ({size_kb:.0f} KB)")
        typer.echo(f"  元数据: {result['metadata_path']}")
        if len(result.get("all_images", [])) > 1:
            typer.echo(f"  共 {len(result['all_images'])} 张图片")
    else:
        typer.secho(f"  生成失败: {result['error']}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


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
        coords_str = format_coords(coords)
        typer.echo(f"  - #{ann_id} {ann_type} {img_label}: {coords_str}")

    prompt = data.get("prompt", "")
    if len(prompt) > 80:
        typer.echo(f"Prompt: {prompt[:80]}...")
    else:
        typer.echo(f"Prompt: {prompt}")


@session_app.command(name="get-prompt")
def get_prompt(
    session_path: Annotated[str, typer.Argument(help="session.json 文件路径")],
) -> None:
    """输出 prompt 字段内容（纯文本，无额外格式）。"""
    data = load_session(session_path)
    prompt = data.get("prompt", "")
    typer.echo(prompt, nl=False)


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
    port: Annotated[int, typer.Option("--port", "-p", help="端口号（默认 8090）")] = 8090,
    preload: Annotated[list[str] | None, typer.Option("--preload", help="预加载图片路径（可多次指定）")] = None,
) -> None:
    """
    Seedream 5.0 Pro 交互编辑 WebUI - 图片上传、点选/框选标注、编辑意图保存
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
    typer.echo(f"  服务地址: http://localhost:{port}")
    typer.echo(f"  远程访问: http://<your-ip>:{port}")
    typer.echo("  按 Ctrl+C 停止服务")
    typer.echo("")

    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")