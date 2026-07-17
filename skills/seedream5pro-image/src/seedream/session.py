"""
Session 状态管理模块 - 管理编辑会话和生成会话的状态机、加载/保存/初始化。

提供状态机常量、状态迁移、session 文件读写、会话初始化等功能。
支持两种会话类型：
- edit: 交互编辑会话（WebUI），路径为 .seedream/edit/<session_id>/
- generate: 普通生成会话（CLI 文生图/图生图），路径为 .seedream/generate/<session_id>/
"""

from __future__ import annotations

import base64
import json
import mimetypes
import uuid
import warnings
from pathlib import Path

from .config import DEFAULT_OUTPUT_DIR, iso_timestamp

# ── 状态机常量 ─────────────────────────────────────────────────────────────────

STATE_CREATED = "created"
STATE_EDITING = "editing"
STATE_SAVED = "saved"

_VALID_TRANSITIONS: dict[str, set[str]] = {
    STATE_CREATED: {STATE_EDITING},
    STATE_EDITING: {STATE_EDITING, STATE_SAVED},
    STATE_SAVED: {STATE_EDITING},
}


# ── 状态机函数 ─────────────────────────────────────────────────────────────────


def transition_state(session_data: dict, target: str, event: str) -> None:
    """
    执行状态机迁移。

    更新 session_data 中的 state_machine 字段，记录迁移历史。

    :param session_data: session 数据字典（会原地修改）
    :param target: 目标状态
    :param event: 迁移事件描述
    :raises ValueError: 如果迁移不合法
    """
    sm = session_data.setdefault("state_machine", {
        "current_state": STATE_CREATED,
        "history": [],
    })
    current = sm["current_state"]
    allowed = _VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(
            f"状态迁移不合法: {current} -> {target}（允许: {allowed}）"
        )
    now = iso_timestamp()
    sm["history"].append({
        "state": target,
        "timestamp": now,
        "event": event,
    })
    sm["current_state"] = target


# ── Session 读写函数 ──────────────────────────────────────────────────────────


def load_session(path: str | Path) -> dict:
    """
    加载 session.json 文件。

    :param path: session.json 文件路径
    :return: 解析后的 JSON 字典
    :raises FileNotFoundError: 文件不存在时抛出
    :raises json.JSONDecodeError: JSON 格式错误时抛出
    """
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_session(path: str | Path, data: dict) -> None:
    """
    将字典写回 session.json 文件。

    :param path: session.json 文件路径
    :param data: 要写入的字典数据
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_session(preload_paths: list[str]) -> tuple[dict, Path]:
    """
    初始化会话：生成 UUID，创建目录，处理预加载图片（base64 嵌入 JSON），创建 session.json。

    :param preload_paths: 预加载图片路径列表
    :return: (session_data, session_path) 元组
    """
    session_id = uuid.uuid4().hex[:12]
    session_dir = Path(DEFAULT_OUTPUT_DIR) / "edit" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    preloaded_images: list[dict] = []
    for path in preload_paths:
        p = Path(path)
        if not p.exists():
            warnings.warn(f"预加载图片不存在: {path}")
            continue
        data = p.read_bytes()
        mime = mimetypes.guess_type(str(p))[0] or "image/png"
        b64 = base64.b64encode(data).decode("ascii")
        preloaded_images.append({
            "inputLabel": f"图{len(preloaded_images) + 1}",
            "name": p.name,
            "dataUrl": f"data:{mime};base64,{b64}",
            "naturalWidth": 0,
            "naturalHeight": 0,
        })

    now = iso_timestamp()
    session_data: dict = {
        "session_id": session_id,
        "created_at": now,
        "state_machine": {
            "current_state": STATE_CREATED,
            "history": [
                {"state": STATE_CREATED, "timestamp": now, "event": "session initialized"},
            ],
        },
        "images": preloaded_images,
        "annotations": [],
        "prompt": "",
        "user_intent": "",
        "intent_html": "",
    }

    if preloaded_images:
        transition_state(session_data, STATE_EDITING, "preloaded images added")

    session_path = session_dir / "session.json"
    save_session(session_path, session_data)

    return session_data, session_path


# ── 辅助函数 ──────────────────────────────────────────────────────────────────


def format_coords(coords: list[int]) -> str:
    """将坐标列表格式化为空格分隔的字符串。"""
    return " ".join(str(c) for c in coords)


def data_url_summary(data_url: str) -> str:
    """
    从 dataUrl 中提取格式和大小信息作为摘要。

    :param data_url: data URL 字符串
    :return: 格式摘要，如 "[Base64] image/png, ~123 KB"
    """
    if not data_url or not data_url.startswith("data:image/"):
        return "[no image]"
    try:
        header = data_url.split(",", 1)[0]
        mime = header.split(":")[1].split(";")[0] if ":" in header else "?"
        b64_part = data_url.split(",", 1)[1] if "," in data_url else ""
        size_kb = len(b64_part) * 3 // 4 // 1024
        return f"[Base64] {mime}, ~{size_kb} KB"
    except (IndexError, ValueError):
        return "[Base64]"


# ── 引用图摘要 ─────────────────────────────────────────────────────────────────


def _ref_label(ref: str) -> str:
    """
    为参考图生成友好标签，避免将完整 base64 数据写入元数据。

    :param ref: 参考图 URL 或 base64 data URI
    :return: 友好标签字符串
    """
    if ref.startswith("data:image/"):
        fmt_end = ref.index(";")
        fmt = ref[11:fmt_end]
        size_kb = len(ref) * 3 // 4 / 1024
        return f"[Base64] {fmt}, ~{size_kb:.0f} KB"
    return ref


# ── 生成会话管理 ────────────────────────────────────────────────────────────────


def init_generate_session(task_data: dict) -> tuple[dict, Path]:
    """
    初始化普通生成会话（文生图/图生图）。

    创建 .seedream/generate/<session_id>/session.json，记录执行状态和参数。

    :param task_data: 生成任务参数（prompt、size、image 等）
    :return: (session_data, session_path) 元组
    """
    session_id = uuid.uuid4().hex[:12]
    session_dir = Path(DEFAULT_OUTPUT_DIR) / "generate" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    now = iso_timestamp()
    session_data: dict = {
        "session_id": session_id,
        "created_at": now,
        "status": "pending",
        "error": None,
        "prompt": task_data.get("prompt", ""),
        "params": {
            "size": task_data.get("size", "2K"),
            "output_format": task_data.get("output_format", "jpeg"),
            "watermark": task_data.get("watermark", False),
            "optimize": task_data.get("optimize_prompt_options", {}).get("mode", "standard"),
        },
        "ref_images": [],
        "outputs": [],
    }

    # 记录参考图摘要
    ref_images = task_data.get("image")
    if ref_images:
        ref_list: list[str] = ref_images if isinstance(ref_images, list) else [ref_images]
        session_data["ref_images"] = [_ref_label(r) for r in ref_list]

    session_path = session_dir / "session.json"
    save_session(session_path, session_data)

    return session_data, session_path


def update_generate_session(session_path: str | Path, status: str, result: dict) -> dict:
    """
    更新生成会话状态（成功/失败）和输出文件列表。

    :param session_path: session.json 文件路径
    :param status: 状态值（"success" | "error" | "running"）
    :param result: single_generate 的返回结果
    :return: 更新后的 session_data
    """
    data = load_session(session_path)
    data["status"] = status
    data["error"] = result.get("error")

    if status == "success" and result.get("all_images"):
        outputs = []
        for img_path in result["all_images"]:
            outputs.append({
                "image_path": img_path,
                "metadata_path": result.get("metadata_path", ""),
                "uid": result.get("uid", ""),
            })
        data["outputs"] = outputs

    save_session(session_path, data)
    return data


def add_edit_session_output(session_path: str | Path, result: dict) -> dict:
    """
    向编辑会话的 session.json 中添加生成输出记录。

    :param session_path: edit session 的 session.json 路径
    :param result: single_generate 的返回结果
    :return: 更新后的 session_data
    """
    data = load_session(session_path)
    outputs = data.setdefault("outputs", [])
    if result.get("status") == "success" and result.get("all_images"):
        for img_path in result["all_images"]:
            outputs.append({
                "image_path": img_path,
                "metadata_path": result.get("metadata_path", ""),
                "uid": result.get("uid", ""),
                "generated_at": iso_timestamp(),
            })
    save_session(session_path, data)
    return data