"""
Seedream 5.0 Pro 交互编辑 WebUI 后端（FastAPI 独立模块）。

提供基于 Canvas 的交互编辑前端，支持图片上传、点选/框选标注、编辑意图保存。

Session 采用状态机设计，图片以 base64 格式直接嵌入 session.json。

用法:
  seedream webui
  seedream webui --port 8090 --preload path/to/img1.png
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from seedream.config import DEFAULT_OUTPUT_DIR
from seedream.session import (
    STATE_CREATED,
    STATE_EDITING,
    STATE_SAVED,
    init_session,
    transition_state,
)

# ── 路径配置 ──────────────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = 8090


# ── Session 状态 ──────────────────────────────────────────────────────────────

_session: dict[str, Any] = {}


def _timestamp() -> str:
    """获取当前时间戳字符串"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def init_session_global(preload_paths: list[str] | None = None) -> dict[str, Any]:
    """
    初始化全局 session 状态，返回 {'id', 'dir', 'path', 'data'}。

    :param preload_paths: 预加载图片路径列表
    :return: 包含 session 信息的字典
    """
    paths = preload_paths or []
    session_data, session_path = init_session(paths)

    _session.update({
        "id": session_data["session_id"],
        "dir": str(session_path.parent.resolve()),
        "path": str(session_path.resolve()),
        "data": session_data,
    })

    return _session


def _write_session() -> None:
    """将内存中的 session data 写回 session.json 文件"""
    session_path = _session.get("path", "")
    if not session_path:
        return
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump(_session["data"], f, ensure_ascii=False, indent=2)


# ── 请求模型 ──────────────────────────────────────────────────────────────────


class SaveImage(BaseModel):
    """保存接口中的图片条目"""

    inputLabel: str = "?"
    name: str = ""
    dataUrl: str
    naturalWidth: int = 0
    naturalHeight: int = 0


class SaveRequest(BaseModel):
    """保存接口的请求体"""

    prompt: str = ""
    user_intent: str = ""
    intent_html: str = ""
    images: list[SaveImage] = []


def _error(message: str, code: int = 400) -> JSONResponse:
    """构造 JSON 错误响应，保持与前端约定的 {"error": "..."} 格式。"""
    return JSONResponse({"error": message}, status_code=code)


# ── FastAPI 应用 ──────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """
    构建 FastAPI 应用并注册所有路由。

    API 路由优先注册，最后挂载静态文件目录作为兜底，前端资源仍从根路径加载。
    """
    app = FastAPI(
        title="Seedream 5.0 Pro 交互编辑 WebUI",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        """健康检查端点"""
        return {
            "ok": True,
            "session_id": _session.get("id", ""),
            "session_path": _session.get("path", ""),
        }

    @app.get("/api/session-info")
    def session_info() -> dict[str, Any]:
        """返回 session 信息，包括图片（含 dataUrl）和已保存的 prompt/intent"""
        data = _session.get("data", {})
        images = data.get("images", [])
        return {
            "session_id": data.get("session_id", ""),
            "status": data.get("state_machine", {}).get("current_state", "unknown"),
            "images": images,
            "prompt": data.get("prompt", ""),
            "user_intent": data.get("user_intent", ""),
            "intent_html": data.get("intent_html", ""),
        }

    @app.post("/api/upload")
    async def upload(files: list[UploadFile] = File(...)) -> JSONResponse:
        """
        上传图片处理。

        接收 multipart/form-data 格式的图片文件，转换为 base64 后直接嵌入 session.json。
        """
        session_data = _session.get("data", {})
        if not session_data:
            return _error("session 未初始化", 500)

        existing_count = len(session_data.get("images", []))
        saved_images: list[dict[str, Any]] = []
        for idx, upload_file in enumerate(files):
            body_data = await upload_file.read()
            if not body_data:
                continue
            filename = upload_file.filename or f"image-{idx}.png"
            mime = upload_file.content_type or mimetypes.guess_type(filename)[0] or "image/png"
            b64 = base64.b64encode(body_data).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            saved_images.append({
                "inputLabel": f"图{existing_count + len(saved_images) + 1}",
                "name": filename,
                "dataUrl": data_url,
                "naturalWidth": 0,
                "naturalHeight": 0,
            })

        if not saved_images:
            return _error("未找到有效图片")

        images = session_data.setdefault("images", [])
        images.extend(saved_images)

        try:
            transition_state(session_data, STATE_EDITING, f"uploaded {len(saved_images)} image(s)")
        except ValueError:
            pass  # 已经处于 editing 状态则忽略

        _write_session()

        return JSONResponse({"ok": True, "images": saved_images})

    @app.post("/api/save")
    def save(payload: SaveRequest) -> JSONResponse:
        """
        保存会话数据。

        图片的 dataUrl 直接嵌入 session.json，不解码保存到磁盘。
        """
        session_data = _session.get("data", {})
        if not session_data:
            return _error("session 未初始化", 500)

        prompt = (payload.prompt or "").strip()
        user_intent = (payload.user_intent or "").strip()
        intent_html = payload.intent_html or ""

        saved_images: list[dict[str, Any]] = []
        for img in payload.images:
            data_url = img.dataUrl
            if not data_url.startswith("data:image/"):
                continue
            saved_images.append({
                "inputLabel": img.inputLabel,
                "name": img.name,
                "dataUrl": data_url,
                "naturalWidth": img.naturalWidth,
                "naturalHeight": img.naturalHeight,
            })

        # 构建标注信息（从 prompt 中提取 <point>/<bbox> 标签）
        annotations: list[dict[str, Any]] = []
        aid = 0
        for match in re.finditer(r"(图\d+)<point>(\d+)\s+(\d+)</point>", prompt):
            aid += 1
            annotations.append({
                "id": aid,
                "type": "point",
                "image_label": match.group(1),
                "normalized_coords": [int(match.group(2)), int(match.group(3))],
                "token": match.group(0),
            })
        for match in re.finditer(r"(图\d+)<bbox>(\d+)\s+(\d+)\s+(\d+)\s+(\d+)</bbox>", prompt):
            aid += 1
            annotations.append({
                "id": aid,
                "type": "bbox",
                "image_label": match.group(1),
                "normalized_coords": [
                    int(match.group(2)),
                    int(match.group(3)),
                    int(match.group(4)),
                    int(match.group(5)),
                ],
                "token": match.group(0),
            })

        now = _timestamp()
        if saved_images:
            session_data["images"] = saved_images
        session_data["annotations"] = annotations
        session_data["prompt"] = prompt
        session_data["user_intent"] = user_intent
        session_data["intent_html"] = intent_html
        session_data["saved_at"] = now

        try:
            transition_state(session_data, STATE_SAVED, "user saved intent")
        except ValueError:
            pass

        _write_session()

        return JSONResponse({
            "ok": True,
            "session_id": session_data.get("session_id"),
            "session_path": _session.get("path", ""),
            "images_saved": len(saved_images),
            "annotations_found": len(annotations),
        })

    # 静态文件兜底：API 路由优先匹配，其余请求交给 StaticFiles（含根路径 index.html）
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


# ── CLI 入口（typer）──────────────────────────────────────────────────────────


def main(port: int = 8090, preload: list[str] | None = None) -> None:
    """
    启动 WebUI 服务。

    :param port: 服务端口号（默认 8090）
    :param preload: 预加载图片路径列表
    """
    preload_paths = preload or []

    # 确保 session 输出目录存在
    session_output_dir = Path(DEFAULT_OUTPUT_DIR) / "edit"
    session_output_dir.mkdir(parents=True, exist_ok=True)

    typer.echo("  Seedream 5.0 Pro 交互编辑 WebUI")
    typer.echo("  ─────────────────────────────────────")
    session_info = init_session_global(preload_paths)
    session_id = session_info.get("id", "")
    session_path = session_info.get("path", "")
    typer.echo(f"  会话 ID: {session_id}")
    typer.echo(f"  Session 文件: {session_path}")
    if preload_paths:
        typer.echo(f"  预加载图片: {len(preload_paths)} 张")
    typer.echo("  ─────────────────────────────────────")

    app = create_app()
    typer.echo(f"  服务地址: http://localhost:{port}")
    typer.echo(f"  远程访问: http://<your-ip>:{port}")
    typer.echo("  按 Ctrl+C 停止服务")
    typer.echo("")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")