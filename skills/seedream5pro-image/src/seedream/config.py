"""
Seedream 5.0 Pro - 配置常量

模型和 API 配置参数，供 generate.py 等模块导入使用。
"""

import os
import re
from datetime import datetime

# ── 模型配置 ──────────────────────────────────────────────────────────────────

MODEL_ID: str = "doubao-seedream-5-0-pro-260628"

API_KEY: str | None = (
    os.getenv("ARK_API_KEY")
    or os.getenv("MODEL_IMAGE_API_KEY")
    or os.getenv("MODEL_AGENT_API_KEY")
)

API_BASE: str = re.sub(
    r"/api/coding/(?:lite/|pro/)?v3$",
    "/api/v3",
    (
        os.getenv("ARK_BASE_URL")
        or os.getenv("MODEL_IMAGE_API_BASE")
        or "https://ark.cn-beijing.volces.com/api/v3"
    ).rstrip("/"),
)

DEFAULT_OUTPUT_DIR: str = ".seedream"

SUPPORTED_IMAGE_FORMATS: set[str] = {
    "jpeg", "png", "webp", "bmp", "tiff", "gif", "heic", "heif",
}

MAX_REF_IMAGES: int = 10

IMAGE_FORMAT_MAP: dict[str, str] = {
    ".jpg": "jpeg", ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
    ".bmp": "bmp",
    ".tiff": "tiff", ".tif": "tiff",
    ".gif": "gif",
    ".heic": "heic", ".heif": "heif",
}


def timestamp() -> str:
    """返回当前时间戳字符串，格式为 YYYYMMDD-HHMMSS。"""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_timestamp() -> str:
    """返回当前 ISO 格式时间戳字符串，格式为 YYYY-MM-DDTHH:MM:SS。"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def ref_label(ref: str) -> str:
    """
    为参考图生成友好标签，避免将完整 base64 数据写入元数据。

    :param ref: 参考图 URL 或 base64 data URI
    :return: 友好标签字符串
    """
    if ref.startswith("data:image/"):
        fmt_end = ref.index(";")
        fmt = ref[11:fmt_end]  # "data:image/<fmt>;..." 中提取 <fmt>
        size_kb = len(ref) * 3 // 4 / 1024  # base64 解码后的近似字节数
        return f"[Base64] {fmt}, ~{size_kb:.0f} KB"
    return ref