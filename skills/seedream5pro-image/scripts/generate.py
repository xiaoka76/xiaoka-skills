#!/usr/bin/env python3
"""
Seedream 5.0 Pro - 独立图像生成脚本

专为 doubao-seedream-5-0-pro-260628 设计，无外部依赖（仅 httpx）。
支持文生图、图生图、交互编辑（<point>/<bbox>），自动保存到本地。

用法:
  python generate.py -p "一只猫" --size 2K
  python generate.py -p "把图1<bbox>179 283 796 986</bbox>的主体放到图2<bbox>118 331 933 871</bbox>位置" --images "url1" "url2"
"""

import argparse
import base64
import os
import re
import sys
import uuid
from datetime import datetime


import httpx

# ── 模型配置 ──────────────────────────────────────────────────────────────────
MODEL_ID = "doubao-seedream-5-0-pro-260628"

API_KEY = (
    os.getenv("ARK_API_KEY")
    or os.getenv("MODEL_IMAGE_API_KEY")
    or os.getenv("MODEL_AGENT_API_KEY")
)
API_BASE = (
    os.getenv("ARK_BASE_URL")
    or os.getenv("MODEL_IMAGE_API_BASE")
    or "https://ark.cn-beijing.volces.com/api/v3"
).rstrip("/")
API_BASE = re.sub(r"/api/coding/(?:lite/|pro/)?v3$", "/api/v3", API_BASE)

DEFAULT_OUTPUT_DIR = "seedream-output"
SUPPORTED_IMAGE_FORMATS = {"jpeg", "png", "webp", "bmp", "tiff", "gif", "heic", "heif"}
MAX_REF_IMAGES = 10


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def normalize_coords(
    img_width: int, img_height: int,
    *coords: int,
) -> tuple:
    """
    将像素坐标转换为 Seedream 5.0 Pro 归一化坐标 (0-999)。

    点选: normalize_coords(w, h, x, y) -> (x_norm, y_norm)
    框选: normalize_coords(w, h, x1, y1, x2, y2) -> (x1_norm, y1_norm, x2_norm, y2_norm)

    坐标系统: (0,0) = 左上角, (999,999) = 右下角
    公式: norm = round(px / 尺寸 * 1000)
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


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ── API 调用 ──────────────────────────────────────────────────────────────────

def _get_headers() -> dict:
    if not API_KEY:
        raise ValueError("请设置 ARK_API_KEY 或 MODEL_IMAGE_API_KEY 或 MODEL_AGENT_API_KEY 环境变量")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }


def _build_request_body(item: dict) -> dict:
    """构建 5.0-pro 专用请求体"""
    body = {
        "model": MODEL_ID,
        "prompt": item.get("prompt", ""),
    }

    supported_fields = [
        "size", "response_format", "watermark", "image",
        "output_format", "optimize_prompt_options",
    ]
    for field in supported_fields:
        if field in item and item[field] is not None:
            body[field] = item[field]

    return body


def _call_api(item: dict, timeout: int) -> dict:
    url = f"{API_BASE}/images/generations"
    body = _build_request_body(item)
    with httpx.Client(timeout=float(timeout)) as client:
        resp = client.post(url, headers=_get_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


def _download_image(url: str, output_dir: str, filename: str, ext: str) -> str:
    """从 URL 下载图片并保存到本地"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{filename}.{ext}")
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
    return os.path.abspath(path)


def _save_b64(b64_data: str, output_dir: str, filename: str, ext: str) -> str:
    """解码 base64 并保存到本地"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{filename}.{ext}")
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return os.path.abspath(path)


def _ref_label(ref: str) -> str:
    """为参考图生成友好标签，避免将完整 base64 数据写入元数据"""
    if ref.startswith("data:image/"):
        # Base64 data URI — 只记录格式和长度
        fmt_end = ref.index(";")
        fmt = ref[11:fmt_end]  # "data:image/<fmt>;..." 中提取 <fmt>
        size_kb = len(ref) * 3 // 4 / 1024  # base64 解码后的近似字节数
        return f"[Base64] {fmt}, ~{size_kb:.0f} KB"
    return ref


_IMAGE_FORMAT_MAP = {
    ".jpg": "jpeg", ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
    ".bmp": "bmp",
    ".tiff": "tiff", ".tif": "tiff",
    ".gif": "gif",
    ".heic": "heic", ".heif": "heif",
}


def _resolve_image_path(path: str) -> str:
    """
    将图片路径解析为 API 可接受的格式。

    - 本地文件 → 读取并编码为 Base64 Data URI
    - 网络 URL  → 原样返回
    - Base64 Data URI → 原样返回
    """
    if path.startswith(("http://", "https://", "data:image/")):
        return path

    # 本地文件：检查是否存在
    if not os.path.exists(path):
        raise FileNotFoundError(f"参考图文件不存在: {path}")

    ext = os.path.splitext(path)[1].lower()
    img_format = _IMAGE_FORMAT_MAP.get(ext)
    if img_format is None:
        raise ValueError(f"不支持的图片格式: {ext}，支持的格式: {', '.join(sorted(_IMAGE_FORMAT_MAP))}")

    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > 30:
        raise ValueError(f"图片超过 30 MB 限制: {path} ({size_mb:.1f} MB)")

    with open(path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("ascii")

    return f"data:image/{img_format};base64,{b64_data}"


def _save_metadata(item: dict, image_paths: list[str], output_dir: str, filename: str) -> str:
    """将生成参数和结果保存为同名 .md 元数据文件"""
    lines = [
        f"# 图像生成元数据",
        f"",
        f"- **生成时间**: {_timestamp()}",
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
            lines.append(f"- **参考图**:")
            for i, ref in enumerate(ref_images):
                label = _ref_label(ref)
                lines.append(f"  - [{i + 1}] {label}")
        else:
            lines.append(f"- **参考图**: {_ref_label(ref_images)}")
    lines.extend([
        f"",
        f"## 输出文件",
    ])
    for i, p in enumerate(image_paths):
        lines.append(f"- 图片 [{i + 1}]: `{p}`")
    lines.append(f"- 元数据: `{os.path.join(os.path.abspath(output_dir), filename)}.md`")
    lines.append("")

    path = os.path.join(output_dir, f"{filename}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return os.path.abspath(path)


def single_generate(
    item: dict,
    timeout: int = 300,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict:
    """
    执行一次图像生成（文生图 / 图生图 / 交互编辑）。

    Args:
        item: 任务参数
            - prompt (str, 必填): 提示词
            - size (str, 可选): 尺寸，默认 "2K"
            - image (str/list, 可选): 参考图 URL 或 URL 列表
            - output_format (str, 可选): "png" 或 "jpeg"
            - watermark (bool, 可选): 是否加水印
            - optimize_prompt_options (dict, 可选): 提示词优化配置
        timeout: API 超时秒数
        output_dir: 图片保存目录

    Returns:
        {
            "status": "success" | "error",
            "image_path": "本地路径" | None,
            "metadata_path": "本地路径" | None,
            "model": "doubao-seedream-5-0-pro-260628",
            "output_dir": "目录路径",
            "error": "错误信息" | None
        }
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

        results = []
        for i, img_data in enumerate(data_list):
            if "error" in img_data:
                continue

            filename = f"{uid}-{i}" if len(data_list) > 1 else uid
            local_path = None

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


# ── CLI 入口 ──────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 入口：解析参数并执行图像生成"""
    parser = argparse.ArgumentParser(
        description="Seedream 5.0 Pro 图像生成 - 文生图 / 图生图 / 交互编辑，自动保存到本地"
    )
    parser.add_argument("--prompt", "-p", required=True, help="提示词 / 编辑指令")
    parser.add_argument("--images", nargs="+", default=None, help="参考图（URL 或本地路径，1 张或多张，最多 10 张）")
    parser.add_argument("--size", "-s", default="2K", help="分辨率: 1K / 2K / 宽x高（默认 2K）")
    parser.add_argument("--output-format", choices=["png", "jpeg"], default="jpeg", help="输出格式")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"保存目录（默认 {DEFAULT_OUTPUT_DIR}）")
    parser.add_argument("--watermark", action="store_true", help="启用水印（默认关闭）")
    parser.add_argument("--optimize", choices=["standard", "fast"], default="standard", help="提示词优化模式（默认 standard）")
    parser.add_argument("--timeout", "-t", type=int, default=300, help="API 超时秒数（默认 300）")

    args = parser.parse_args()

    if not API_KEY:
        print("错误: 请设置 ARK_API_KEY 环境变量")
        sys.exit(1)

    # 构建请求
    task = {
        "prompt": args.prompt,
        "size": args.size,
        "output_format": args.output_format,
        "watermark": args.watermark,
    }

    task["optimize_prompt_options"] = {"mode": args.optimize}

    # 参考图：自动检测本地路径并编码为 Base64 Data URI
    if args.images:
        if len(args.images) > MAX_REF_IMAGES:
            print(f"错误: 最多支持 {MAX_REF_IMAGES} 张参考图")
            sys.exit(1)

        resolved = []
        for path in args.images:
            try:
                resolved.append(_resolve_image_path(path))
            except (FileNotFoundError, ValueError) as e:
                print(f"错误: {e}")
                sys.exit(1)

        task["image"] = resolved if len(resolved) > 1 else resolved[0]

    # 打印信息
    print(f"  Seedream 5.0 Pro 图像生成")
    print(f"  Prompt: {args.prompt[:80]}{'...' if len(args.prompt) > 80 else ''}")
    print(f"  Size: {args.size}")
    print(f"  输出目录: {args.output_dir}")
    print(f"  格式: {args.output_format}")
    if args.images:
        print(f"  参考图: {len(args.images)} 张")
    if args.watermark:
        print(f"  水印: 开启")
    print(f"  优化模式: {args.optimize}")
    print()

    # 执行
    result = single_generate(task, timeout=args.timeout, output_dir=args.output_dir)

    if result["status"] == "success":
        print(f"  生成成功!")
        size_kb = os.path.getsize(result["image_path"]) / 1024 if os.path.exists(result["image_path"]) else 0
        print(f"  图片: {result['image_path']} ({size_kb:.0f} KB)")
        print(f"  元数据: {result['metadata_path']}")
        if len(result.get("all_images", [])) > 1:
            print(f"  共 {len(result['all_images'])} 张图片")
    else:
        print(f"  生成失败: {result['error']}")


if __name__ == "__main__":
    main()