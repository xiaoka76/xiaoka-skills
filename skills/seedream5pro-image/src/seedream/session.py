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
import os
import struct
import uuid
import warnings
from pathlib import Path

from .config import DEFAULT_OUTPUT_DIR, iso_timestamp, ref_label

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
    将字典写回 session.json 文件（原子写入，防止进程崩溃时文件损坏）。

    先写入临时文件，再通过 os.replace 原子替换目标文件。

    :param path: session.json 文件路径
    :param data: 要写入的字典数据
    """
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


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
        width, height = read_image_dimensions(data)
        preloaded_images.append({
            "inputLabel": f"图{len(preloaded_images) + 1}",
            "name": p.name,
            "dataUrl": f"data:{mime};base64,{b64}",
            "naturalWidth": width,
            "naturalHeight": height,
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


def read_image_dimensions(data: bytes) -> tuple[int, int]:
    """
    从图片字节流头部解析宽高（支持 PNG/JPEG/GIF/WebP/BMP，无第三方依赖）。

    :param data: 图片原始字节
    :return: (width, height)，无法识别时返回 (0, 0)
    """
    # 低于 8 字节无法匹配任何格式签名；各格式分支内部用 try/except 防御短数据
    if len(data) < 8:
        return (0, 0)

    # PNG: IHDR chunk 中 width/height 为 4 字节大端
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        try:
            width, height = struct.unpack(">II", data[16:24])
            return (width, height)
        except struct.error:
            return (0, 0)

    # GIF: width/height 为 2 字节小端，偏移 6
    if data[:6] in (b"GIF87a", b"GIF89a"):
        try:
            width, height = struct.unpack("<HH", data[6:10])
            return (width, height)
        except struct.error:
            return (0, 0)

    # BMP: width/height 为 4 字节小端，偏移 18
    if data[:2] == b"BM":
        try:
            width, height = struct.unpack("<ii", data[18:26])
            return (abs(width), abs(height))
        except struct.error:
            return (0, 0)

    # WebP: RIFF....WEBP，按子格式解析
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        try:
            if chunk == b"VP8 " and len(data) >= 30:
                # lossy：宽高在 chunk 头后第 6 字节起，2 字节小端
                width, height = struct.unpack("<HH", data[26:30])
                return (width & 0x3FFF, height & 0x3FFF)
            if chunk == b"VP8L" and len(data) >= 25:
                # lossless：1 字节签名后 14+14 位
                bits = int.from_bytes(data[21:25], "little")
                width = (bits & 0x3FFF) + 1
                height = ((bits >> 14) & 0x3FFF) + 1
                return (width, height)
            if chunk == b"VP8X" and len(data) >= 30:
                # extended：3 字节小端宽高（值-1）
                width = int.from_bytes(data[24:27], "little") + 1
                height = int.from_bytes(data[27:30], "little") + 1
                return (width, height)
        except struct.error:
            return (0, 0)

    # JPEG: 扫描 SOF 标记
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            # SOF 标记范围 0xC0~0xCF，排除 0xC4(DHT)/0xC8(JPG)/0xCC(DAC)
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return (width, height)
            # 跳过本段：2 字节大端长度
            if i + 4 <= len(data):
                seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg_len
            else:
                break
        return (0, 0)

    return (0, 0)


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
        session_data["ref_images"] = [ref_label(r) for r in ref_list]

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