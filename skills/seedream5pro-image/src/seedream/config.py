"""
Seedream 5.0 Pro - 配置常量

模型和 API 配置参数，供 generate.py 等模块导入使用。
"""

import os
import re
from pathlib import Path

# ── 模型配置 ──────────────────────────────────────────────────────────────────

MODEL_ID: str = "doubao-seedream-5-0-pro-260628"

# API Key 与 Base URL 均仅通过环境变量注入，请求发往 {API_BASE}/images/generations。
# 火山方舟按套餐区分端点前缀，Key 与端点必须匹配，否则返回 401：
#   按量后付费   https://ark.cn-beijing.volces.com/api/v3        （默认）
#   coding plan  https://ark.cn-beijing.volces.com/api/coding/v3 （无图像接口，下方自动归一到 /api/v3）
#   agent plan   https://ark.cn-beijing.volces.com/api/plan/v3   （图像用量计入套餐额度）

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

# ── 数据根目录 ────────────────────────────────────────────────────────────────
# 解析顺序：$SEEDREAM_HOME（显式指定）> 当前工作目录/.seedream
#
# 为什么不放 ~/.seedream：多个 agent 可能共用一个容器与同一个 /root，
# 家目录会让它们的产物混住；而 cwd 是每个 agent 自己的工作区，天然隔离。
# 需要集中存放时用 SEEDREAM_HOME 显式指定即可。

HOME_DIRNAME: str = ".seedream"

# 子目录名（与 runs_dir() / index_path() 配套，测试与文档会引用）
RUNS_DIRNAME: str = "runs"
INDEX_FILENAME: str = "index.jsonl"


def resolve_home() -> Path:
    """
    返回数据根目录。

    :return: ``$SEEDREAM_HOME`` 解析后的绝对路径；未设置时为 ``cwd/.seedream``
    """
    override = os.getenv("SEEDREAM_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd() / HOME_DIRNAME


def runs_dir() -> Path:
    """返回存放各次生成任务的目录：``<home>/runs``。"""
    return resolve_home() / RUNS_DIRNAME


def index_path() -> Path:
    """返回任务索引文件路径：``<home>/index.jsonl``（append-only，一行一条）。"""
    return resolve_home() / INDEX_FILENAME


def ensure_home() -> Path:
    """确保根目录与 runs 目录存在，返回根目录。"""
    runs_dir().mkdir(parents=True, exist_ok=True)
    return resolve_home()


MAX_REF_IMAGES: int = 10

# ── 参考图限制（对齐官方《图片生成 API》）───────────────────────────────────────
# 单张参考图：总像素 [196, 6000×6000]，宽高 > 14px，宽高比 [1/16, 16]，≤ 30MB
MAX_REF_PIXELS: int = 36_000_000
MIN_REF_PIXELS: int = 196
MIN_REF_EDGE: int = 14
MAX_REF_ASPECT: float = 16.0
MAX_REF_BYTES: int = 30 * 1024 * 1024


# 平台内联预览上限：产物达到这个体积就自动降档重渲染
PREVIEW_MAX_BYTES: int = 2 * 1024 * 1024

# ── 分辨率档位 ────────────────────────────────────────────────────────────────
# 图片生成场景：1K / 1.5K / 2K（1.5K 与 1K 同价，画质更优）
# 图层拆分场景：1K / 1.5K / 2K / auto（auto 按输入图尺寸自适应，不可与宽x高混用）
SIZE_TIERS: set[str] = {"1K", "1.5K", "2K"}

# ── 图层拆分 ──────────────────────────────────────────────────────────────────
# 单张输入图可拆解为 1 张底图（z_index=0）+ 最多 MAX_LAYERS 个图层（png，带透明通道）
MAX_LAYERS: int = 16

# 透明背景模式仅支持带透明通道的输入图，这些格式天然不含 alpha 通道
ALPHA_LESS_FORMATS: set[str] = {".jpg", ".jpeg"}

IMAGE_FORMAT_MAP: dict[str, str] = {
    ".jpg": "jpeg", ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
    ".bmp": "bmp",
    ".tiff": "tiff", ".tif": "tiff",
    ".gif": "gif",
    ".heic": "heic", ".heif": "heif",
}
