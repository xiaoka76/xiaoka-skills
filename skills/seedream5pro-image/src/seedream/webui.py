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
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from seedream.config import DEFAULT_OUTPUT_DIR
from seedream.session import (
    STATE_EDITING,
    STATE_SAVED,
    init_session,
    read_image_dimensions,
    transition_state,
)

# ── 路径配置 ──────────────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = 8090
# 单个上传文件大小上限（字节），与 API 30MB 限制对齐并留出余量
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
# 单次 /api/save 请求体大小上限（字节），防止超大 base64 payload 导致 OOM
MAX_SAVE_BYTES = 100 * 1024 * 1024


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
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0


class AnnotationData(BaseModel):
    """保存接口中的标注条目"""

    id: int
    type: str  # "point" | "bbox"
    image_label: str = ""
    normalized_coords: list[int] = []
    token: str = ""


class SaveRequest(BaseModel):
    """保存接口的请求体"""

    prompt: str = ""
    user_intent: str = ""
    intent_html: str = ""
    images: list[SaveImage] = []
    annotations: list[AnnotationData] = []


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
        """返回 session 信息，包括图片（含 dataUrl）、标注和已保存的 prompt/intent"""
        data = _session.get("data", {})
        images = data.get("images", [])
        return {
            "session_id": data.get("session_id", ""),
            "status": data.get("state_machine", {}).get("current_state", "unknown"),
            "images": images,
            "annotations": data.get("annotations", []),
            "prompt": data.get("prompt", ""),
            "user_intent": data.get("user_intent", ""),
            "intent_html": data.get("intent_html", ""),
        }

    @app.post("/api/upload")
    async def upload(files: list[UploadFile] = File(...)) -> JSONResponse:
        """
        上传图片处理。

        接收 multipart/form-data 格式的图片文件，转换为 base64 后直接嵌入 session.json。
        单个文件不超过 MAX_UPLOAD_BYTES，防止内存被撑爆。
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
            if len(body_data) > MAX_UPLOAD_BYTES:
                return _error(
                    f"文件 {upload_file.filename or idx} 超过 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 限制",
                    413,
                )
            filename = upload_file.filename or f"image-{idx}.png"
            mime = upload_file.content_type or mimetypes.guess_type(filename)[0] or "image/png"
            if not mime.startswith("image/"):
                return _error(f"不支持的文件类型: {mime}", 415)
            b64 = base64.b64encode(body_data).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            width, height = read_image_dimensions(body_data)
            saved_images.append({
                "inputLabel": f"图{existing_count + len(saved_images) + 1}",
                "name": filename,
                "dataUrl": data_url,
                "naturalWidth": width,
                "naturalHeight": height,
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
        请求体大小受 MAX_SAVE_BYTES 限制，防止超大 base64 payload 导致 OOM。
        """
        session_data = _session.get("data", {})
        if not session_data:
            return _error("session 未初始化", 500)

        # 粗略估算 payload 大小（pydantic 已解析为对象，按 dataUrl 总长度估算）
        total_bytes = sum(len(img.dataUrl) for img in payload.images) + len(payload.prompt) + len(payload.intent_html)
        if total_bytes > MAX_SAVE_BYTES:
            return _error(f"请求数据过大（{total_bytes // (1024 * 1024)}MB），超过 {MAX_SAVE_BYTES // (1024 * 1024)}MB 限制", 413)

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
                "x": img.x,
                "y": img.y,
                "width": img.width,
                "height": img.height,
            })

        # 使用前端直接传来的标注数据（保持 ID 一致，避免重新解析导致不匹配）
        annotations: list[dict[str, Any]] = []
        for ann in payload.annotations:
            annotations.append({
                "id": ann.id,
                "type": ann.type,
                "image_label": ann.image_label,
                "normalized_coords": ann.normalized_coords,
                "token": ann.token,
            })

        now = _timestamp()
        # 只更新/追加图片，不替换已有图片，防止丢失未在本次保存中引用的图片
        if saved_images:
            existing_images = session_data.get("images", [])
            # 用 dataUrl 去重：已存在的图片保留，新图片追加
            existing_urls = {img.get("dataUrl", "") for img in existing_images}
            merged = list(existing_images)
            for img in saved_images:
                if img.get("dataUrl", "") not in existing_urls:
                    merged.append(img)
                    existing_urls.add(img.get("dataUrl", ""))
            session_data["images"] = merged
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