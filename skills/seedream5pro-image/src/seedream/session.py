"""
Session 状态管理模块 - 管理编辑会话的状态机、加载/保存/初始化。

提供状态机常量、状态迁移、session 文件读写、会话初始化等功能。
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