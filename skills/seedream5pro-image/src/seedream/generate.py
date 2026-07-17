"""
Seedream 5.0 Pro - 图像生成核心函数模块

提供文生图、图生图、交互编辑的纯函数接口，不包含 CLI 代码。
供外部模块（如 CLI 脚本、Web UI）导入使用。
"""

import base64
import os
import uuid

import httpx

from .config import (
    API_BASE,
    API_KEY,
    DEFAULT_OUTPUT_DIR,
    IMAGE_FORMAT_MAP,
    MAX_REF_IMAGES,
    MODEL_ID,
    SUPPORTED_IMAGE_FORMATS,
    timestamp,
)


# ── 工具函数 ──────────────────────────────────────────────────────────────────


def normalize_coords(
    img_width: int, img_height: int,
    *coords: int,
) -> tuple[int, ...]:
    """
    将像素坐标转换为 Seedream 5.0 Pro 归一化坐标 (0-999)。

    点选: normalize_coords(w, h, x, y) -> (x_norm, y_norm)
    框选: normalize_coords(w, h, x1, y1, x2, y2) -> (x1_norm, y1_norm, x2_norm, y2_norm)

    坐标系统: (0,0) = 左上角, (999,999) = 右下角
    公式: norm = round(px / 尺寸 * 1000)

    :param img_width: 图片宽度（像素）
    :param img_height: 图片高度（像素）
    :param coords: 2 个坐标（点选）或 4 个坐标（框选）
    :return: 归一化后的坐标元组
    :raises ValueError: 坐标数量不是 2 或 4
    """
    n = len(coords)
    if n == 2:
        x, y = coords
        return (round(x / img_width * 1000), round(y / img_height * 1000))
    elif n == 4:
        x1, y1, x2, y2 = coords
        return (
            round(x1 / img_width * 1000), round(y1 / img_height * 1000),
            round(x2 / img_width * 1000), round(y2 / img_height * 1000),
        )
    else:
        raise ValueError("需要 2 个坐标（点选）或 4 个坐标（框选）")


# ── API 调用 ──────────────────────────────────────────────────────────────────


def _get_headers() -> dict[str, str]:
    """构建 API 请求头。"""
    if not API_KEY:
        raise ValueError("请设置 ARK_API_KEY 或 MODEL_IMAGE_API_KEY 或 MODEL_AGENT_API_KEY 环境变量")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }


def _build_request_body(item: dict) -> dict:
    """构建 5.0-pro 专用请求体。

    :param item: 任务参数，包含 prompt、size、image 等字段
    :return: 发送给 API 的请求体字典
    """
    body: dict = {
        "model": MODEL_ID,
        "prompt": item.get("prompt", ""),
    }

    supported_fields: list[str] = [
        "size", "response_format", "watermark", "image",
        "output_format", "optimize_prompt_options",
    ]
    for field in supported_fields:
        if field in item and item[field] is not None:
            body[field] = item[field]

    return body


def _call_api(item: dict, timeout: int) -> dict:
    """调用 Seedream 5.0 Pro 图像生成 API。

    :param item: 任务参数
    :param timeout: API 超时秒数
    :return: API 返回的 JSON 响应
    """
    url = f"{API_BASE}/images/generations"
    body = _build_request_body(item)
    with httpx.Client(timeout=float(timeout)) as client:
        resp = client.post(url, headers=_get_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


def _download_image(url: str, output_dir: str, filename: str, ext: str) -> str:
    """从 URL 下载图片并保存到本地。

    :param url: 图片 URL
    :param output_dir: 输出目录
    :param filename: 文件名（不含扩展名）
    :param ext: 文件扩展名
    :return: 保存的图片绝对路径
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{filename}.{ext}")
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
    return os.path.abspath(path)


def _save_b64(b64_data: str, output_dir: str, filename: str, ext: str) -> str:
    """解码 base64 并保存到本地。

    :param b64_data: Base64 编码的图片数据
    :param output_dir: 输出目录
    :param filename: 文件名（不含扩展名）
    :param ext: 文件扩展名
    :return: 保存的图片绝对路径
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{filename}.{ext}")
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return os.path.abspath(path)


def _ref_label(ref: str) -> str:
    """为参考图生成友好标签，避免将完整 base64 数据写入元数据。

    :param ref: 参考图 URL 或 base64 data URI
    :return: 友好标签字符串
    """
    if ref.startswith("data:image/"):
        # Base64 data URI - 只记录格式和长度
        fmt_end = ref.index(";")
        fmt = ref[11:fmt_end]  # "data:image/<fmt>;..." 中提取 <fmt>
        size_kb = len(ref) * 3 // 4 / 1024  # base64 解码后的近似字节数
        return f"[Base64] {fmt}, ~{size_kb:.0f} KB"
    return ref


def _resolve_image_path(path: str) -> str:
    """
    将图片路径解析为 API 可接受的格式。

    - 本地文件 -> 读取并编码为 Base64 Data URI
    - 网络 URL  -> 原样返回
    - Base64 Data URI -> 原样返回

    :param path: 图片路径、URL 或 Base64 Data URI
    :return: 可传入 API 的图片引用
    :raises FileNotFoundError: 本地文件不存在
    :raises ValueError: 不支持的图片格式或超过大小限制
    """
    if path.startswith(("http://", "https://", "data:image/")):
        return path

    # 本地文件：检查是否存在
    if not os.path.exists(path):
        raise FileNotFoundError(f"参考图文件不存在: {path}")

    ext = os.path.splitext(path)[1].lower()
    img_format = IMAGE_FORMAT_MAP.get(ext)
    if img_format is None:
        raise ValueError(f"不支持的图片格式: {ext}，支持的格式: {', '.join(sorted(IMAGE_FORMAT_MAP))}")

    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > 30:
        raise ValueError(f"图片超过 30 MB 限制: {path} ({size_mb:.1f} MB)")

    with open(path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("ascii")

    return f"data:image/{img_format};base64,{b64_data}"


def _save_metadata(item: dict, image_paths: list[str], output_dir: str, filename: str) -> str:
    """将生成参数和结果保存为同名 .md 元数据文件。

    :param item: 生成任务参数
    :param image_paths: 生成的图片路径列表
    :param output_dir: 输出目录
    :param filename: 文件名前缀（不含扩展名）
    :return: 元数据文件绝对路径
    """
    lines: list[str] = [
        "# 图像生成元数据",
        "",
        f"- **生成时间**: {timestamp()}",
        f"- **模型**: {MODEL_ID}",
        f"- **提示词**: {item.get('prompt', '')}",
        f"- **尺寸**: {item.get('size', '2K')}",
        f"- **输出格式**: {item.get('output_format', 'jpeg')}",
        f"- **水印**: {'开启' if item.get('watermark') else '关闭'}",
        f"- **优化模式**: {item.get('optimize_prompt_options', {}).get('mode', 'standard')}",
    ]
    ref_images = item.get("image")
    if ref_images:
        if isinstance(ref_images, list):
            lines.append("- **参考图**:")
            for i, ref in enumerate(ref_images):
                label = _ref_label(ref)
                lines.append(f"  - [{i + 1}] {label}")
        else:
            lines.append(f"- **参考图**: {_ref_label(ref_images)}")
    lines.extend([
        "",
        "## 输出文件",
    ])
    for i, p in enumerate(image_paths):
        lines.append(f"- 图片 [{i + 1}]: `{p}`")
    lines.append(f"- 元数据: `{os.path.join(os.path.abspath(output_dir), filename)}.md`")
    lines.append("")

    path = os.path.join(output_dir, f"{filename}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return os.path.abspath(path)


# ── 核心生成函数 ──────────────────────────────────────────────────────────────


def single_generate(
    item: dict,
    timeout: int = 300,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict:
    """
    执行一次图像生成（文生图 / 图生图 / 交互编辑）。

    :param item: 任务参数
        - prompt (str, 必填): 提示词
        - size (str, 可选): 尺寸，默认 "2K"
        - image (str | list, 可选): 参考图 URL 或 URL 列表
        - output_format (str, 可选): "png" 或 "jpeg"
        - watermark (bool, 可选): 是否加水印
        - optimize_prompt_options (dict, 可选): 提示词优化配置
    :param timeout: API 超时秒数
    :param output_dir: 图片保存目录
    :return: 结果字典
        - status: "success" | "error"
        - image_path: 本地路径 | None
        - metadata_path: 本地路径 | None
        - model: 模型 ID
        - output_dir: 目录路径
        - error: 错误信息 | None
    """
    # 强制 b64_json 模式确保本地保存
    item["response_format"] = "b64_json"

    output_format = item.get("output_format", "jpeg")
    ext = "png" if output_format == "png" else "jpg"
    uid = uuid.uuid4().hex[:12]

    try:
        response = _call_api(item, timeout)

        if "error" in response:
            return {
                "status": "error",
                "image_path": None,
                "metadata_path": None,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": str(response["error"]),
            }

        data_list = response.get("data", [])
        if not data_list:
            return {
                "status": "error",
                "image_path": None,
                "metadata_path": None,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": "API 返回空数据",
            }

        results: list[str] = []
        for i, img_data in enumerate(data_list):
            if "error" in img_data:
                continue
            if "b64_json" not in img_data:
                continue

            filename = f"{uid}-{i}" if len(data_list) > 1 else uid
            local_path: str | None = None

            # 优先 b64_json
            b64 = img_data.get("b64_json")
            if b64:
                local_path = _save_b64(b64, output_dir, filename, ext)
            else:
                url = img_data.get("url")
                if url:
                    local_path = _download_image(url, output_dir, filename, ext)

            if local_path:
                results.append(local_path)

        if results:
            metadata_path = _save_metadata(item, results, output_dir, uid)
            return {
                "status": "success",
                "image_path": results[0],  # 单图场景返回第一张
                "metadata_path": metadata_path,
                "all_images": results,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": None,
            }
        else:
            return {
                "status": "error",
                "image_path": None,
                "metadata_path": None,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": "生成失败：所有图片数据均为空",
            }

    except Exception as e:
        return {
            "status": "error",
            "image_path": None,
            "metadata_path": None,
            "model": MODEL_ID,
            "output_dir": os.path.abspath(output_dir),
            "error": str(e),
        }


def generate_from_session(session_data: dict, **kwargs) -> dict:
    """
    从 session JSON 数据执行图像生成。

    从 session 中读取图片的 dataUrl（base64 嵌入），直接传给 API，
    与 CLI 的 ``--session`` 模式行为一致。

    :param session_data: session.json 的 dict 内容
        - prompt (str): 提示词（含 <point>/<bbox> 坐标）
        - images (list): 图片列表，每个元素包含 dataUrl 等字段
    :param kwargs: 传递给 single_generate 的其他参数
    :return: single_generate 的返回结果
    """
    task: dict[str, str | list[str] | None] = {
        "prompt": session_data["prompt"],
    }
    data_urls = [img["dataUrl"] for img in session_data.get("images", []) if img.get("dataUrl")]
    if data_urls:
        task["image"] = data_urls if len(data_urls) > 1 else data_urls[0]
    task.update(kwargs)
    return single_generate(task)