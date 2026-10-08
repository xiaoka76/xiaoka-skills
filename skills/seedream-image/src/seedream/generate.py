"""
Seedream 5.0 Pro - 图像生成核心函数模块

提供文生图、图生图、交互编辑的纯函数接口，不包含 CLI 代码。
任务记录（run.json / inputs / outputs）由 :mod:`seedream.run` 负责，
本模块只负责"把请求发出去、把产物落盘"。
"""

import base64
import hashlib
import os
import re
import time
import uuid

import httpx

from .config import (
    API_BASE,
    API_KEY,
    IMAGE_FORMAT_MAP,
    LAYER_ALLOWED_FORMATS,
    MIN_LAYER_PIXELS,
    MAX_REF_ASPECT,
    MAX_REF_BYTES,
    MAX_REF_IMAGES,
    MAX_REF_PIXELS,
    MIN_REF_EDGE,
    MIN_REF_PIXELS,
    MODEL_ID,
)

# ── 共享 HTTP 客户端（连接池复用）──────────────────────────────────────────────

_http_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """获取模块级 httpx.Client（连接池复用）。

    超时**按请求传**（``client.post(..., timeout=...)``），不改写共享实例的状态——
    否则并发或连续调用会互相覆盖超时设置。
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client()
    return _http_client


# ── API 重试配置 ──────────────────────────────────────────────────────────────

_MAX_RETRIES: int = 3
_RETRY_BACKOFF: float = 1.5  # 指数退避基数（秒）

# ── 输出格式映射 ──────────────────────────────────────────────────────────────

_FORMAT_TO_EXT: dict[str, str] = {
    "png": "png", "jpeg": "jpg", "jpg": "jpg", "webp": "webp",
}


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
    公式: norm = clamp(round(px / 尺寸 * 1000), 0, 999)

    :param img_width: 图片宽度（像素，必须 > 0）
    :param img_height: 图片高度（像素，必须 > 0）
    :param coords: 2 个坐标（点选）或 4 个坐标（框选）
    :return: 归一化后的坐标元组，每个值被 clamp 到 [0, 999]
    :raises ValueError: 坐标数量不是 2 或 4，或图片尺寸非正
    """
    if img_width <= 0 or img_height <= 0:
        raise ValueError(f"图片尺寸必须为正数，当前 width={img_width}, height={img_height}")

    def _norm(px: int, size: int) -> int:
        return max(0, min(999, round(px / size * 1000)))

    n = len(coords)
    if n == 2:
        x, y = coords
        return (_norm(x, img_width), _norm(y, img_height))
    elif n == 4:
        x1, y1, x2, y2 = coords
        return (
            _norm(x1, img_width), _norm(y1, img_height),
            _norm(x2, img_width), _norm(y2, img_height),
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

    ⚠️ 维护者注意：有几个参数**必须显式下发**，不能依赖接口默认值，否则行为反直觉——
    ``watermark`` 默认 ``true``（不传就带"AI 生成"水印）、``output_format`` 默认 ``jpeg``、
    ``response_format`` 默认 ``url``（链接 24 小时后失效）。CLI 一律显式覆盖这三项，
    因此在 CLI 这一层它们是"确定行为"，调用方（agent）无需知道接口默认值长什么样。

    ``output_format`` 的 CLI 默认值与接口默认值**碰巧一致**（都是 ``jpeg``），但不要因此
    省掉显式下发：``split`` 底图与 ``cutout`` 仍显式传 ``png``，一旦哪天接口默认值变动，
    靠显式下发才能保证两条路径行为不变。

    :param item: 任务参数，包含 prompt、size、image 等字段
    :return: 发送给 API 的请求体字典
    """
    body: dict = {"model": MODEL_ID}

    # 图层拆分场景下 prompt 为可选参数：不传时模型自动识别主要元素
    prompt = item.get("prompt")
    if prompt:
        body["prompt"] = prompt

    supported_fields: list[str] = [
        "size", "response_format", "watermark", "image",
        "output_format", "optimize_prompt_options",
        "layer_decomposition", "background",
    ]
    for field in supported_fields:
        if field in item and item[field] is not None:
            body[field] = item[field]

    return body


def _call_api(item: dict, timeout: int) -> dict:
    """调用 Seedream 5.0 Pro 图像生成 API（含指数退避重试）。

    :param item: 任务参数
    :param timeout: API 超时秒数
    :return: API 返回的 JSON 响应
    :raises httpx.HTTPStatusError: HTTP 非 2xx（不可重试的状态码直接抛出）
    :raises httpx.RequestError: 网络层错误（重试耗尽后抛出）
    """
    url = f"{API_BASE}/images/generations"
    body = _build_request_body(item)
    client = _get_client()

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = client.post(url, headers=_get_headers(), json=body,
                            timeout=httpx.Timeout(float(timeout)))
            if resp.status_code >= 400:
                detail = resp.text
                try:
                    parsed = resp.json()
                    if isinstance(parsed, dict) and "error" in parsed:
                        detail = str(parsed["error"])
                except (ValueError, TypeError):
                    pass
                # 4xx 错误（非 429）不可重试，直接抛出
                if resp.status_code != 429 and resp.status_code < 500:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code} {resp.reason_phrase}: {detail}",
                        request=resp.request,
                        response=resp,
                    )
                # 429 / 5xx 可重试
                last_error = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code} {resp.reason_phrase}: {detail}",
                    request=resp.request,
                    response=resp,
                )
            else:
                return resp.json()
        except httpx.RequestError as e:
            last_error = e

        if attempt < _MAX_RETRIES - 1:
            wait = _RETRY_BACKOFF ** (attempt + 1)
            time.sleep(wait)

    raise last_error  # type: ignore[arg-type]


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
    # 超时按请求传，与 _call_api 一致 —— 不改写共享 client 的状态
    client = _get_client()
    resp = client.get(url, timeout=httpx.Timeout(120.0))
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


def suggest_reference_size(width: int, height: int) -> tuple[int, int]:
    """给出把图片压进官方限制内的建议尺寸（等比缩小）。"""
    ratio = (MAX_REF_PIXELS / (width * height)) ** 0.5
    if ratio >= 1:
        return width, height
    return max(MIN_REF_EDGE + 1, int(width * ratio)), max(MIN_REF_EDGE + 1, int(height * ratio))


def _check_reference_limits(path: str) -> None:
    """校验本地参考图是否超出官方图生图限制。

    超过限制时接口必定报错，所以这里**直接给出可执行的缩放建议**而不是把错误留到调用时。
    读不出尺寸（缺 Pillow / 格式不支持）时跳过像素校验，交给接口判断。

    :raises ValueError: 超出限制
    """
    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > MAX_REF_BYTES / (1024 * 1024):
        raise ValueError(
            f"参考图超过 {MAX_REF_BYTES // (1024 * 1024)} MB 限制: {path}（{size_mb:.1f} MB）。"
            f"可先压缩再传入"
        )

    dims = probe_image_size(path)
    if dims is None:
        return
    width, height = dims

    if min(width, height) <= MIN_REF_EDGE:
        raise ValueError(
            f"参考图宽高必须大于 {MIN_REF_EDGE}px: {path}（{width}x{height}）"
        )
    pixels = width * height
    if pixels < MIN_REF_PIXELS:
        raise ValueError(f"参考图总像素过小: {path}（{pixels}，下限 {MIN_REF_PIXELS}）")

    aspect = width / height
    if aspect > MAX_REF_ASPECT or aspect < 1 / MAX_REF_ASPECT:
        raise ValueError(
            f"参考图宽高比超出 [1/{MAX_REF_ASPECT:.0f}, {MAX_REF_ASPECT:.0f}]: "
            f"{path}（{width}x{height}，比例 {aspect:.2f}）"
        )

    if pixels > MAX_REF_PIXELS:
        new_w, new_h = suggest_reference_size(width, height)
        raise ValueError(
            f"参考图总像素超限: {path}（{width}x{height} = {pixels / 10000:.0f} 万像素，"
            f"上限 {MAX_REF_PIXELS // 10000} 万像素）。"
            f"建议先等比缩放到 {new_w}x{new_h} 再传入——这一步交给你决定，不会自动改图"
        )


def suggest_layer_scale_up(width: int, height: int) -> tuple[int, int]:
    """给出把图片放大到图层拆分下限之上的建议尺寸（等比放大）。"""
    ratio = (MIN_LAYER_PIXELS / (width * height)) ** 0.5
    return max(MIN_REF_EDGE + 1, round(width * ratio)), max(MIN_REF_EDGE + 1, round(height * ratio))


def check_layer_decomposition_limits(path: str) -> None:
    """校验本地图片是否满足**图层拆分**对输入图的专属限制。

    官方对图层拆分比对普通图生图更严：格式仅 ``png`` / ``jpeg``，总像素
    ``[512×512, 6000×6000]``。不先拦的话，小图/别的格式要等接口报错才知道。

    读不出尺寸（缺 Pillow / 格式不支持）时跳过像素校验，交给接口判断。

    :param path: 本地图片路径
    :raises ValueError: 不满足图层拆分限制
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in LAYER_ALLOWED_FORMATS:
        raise ValueError(
            f"图层拆分仅支持 png / jpeg 输入: {path}（当前 {ext or '无扩展名'}）。"
            f"请先转成 png 再传入"
        )

    dims = probe_image_size(path)
    if dims is None:
        return
    width, height = dims
    pixels = width * height
    if pixels < MIN_LAYER_PIXELS:
        new_w, new_h = suggest_layer_scale_up(width, height)
        raise ValueError(
            f"图层拆分要求输入图总像素 ≥ {MIN_LAYER_PIXELS}（512x512）: "
            f"{path}（{width}x{height} = {pixels / 10000:.1f} 万像素，不足）。"
            f"建议先等比放大到 {new_w}x{new_h} 再传入——这一步交给你决定，不会自动改图"
        )
    if pixels > MAX_REF_PIXELS:
        new_w, new_h = suggest_reference_size(width, height)
        raise ValueError(
            f"图层拆分输入图总像素超限: {path}（{width}x{height} = {pixels / 10000:.0f} 万像素，"
            f"上限 {MAX_REF_PIXELS // 10000} 万像素）。"
            f"建议先等比缩放到 {new_w}x{new_h} 再传入——这一步交给你决定，不会自动改图"
        )


def probe_image_size(path: str) -> tuple[int, int] | None:
    """读取本地图片宽高；读不出来返回 None（不抛异常）。"""
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def resolve_image_path(path: str) -> str:
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

    _check_reference_limits(path)

    with open(path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("ascii")

    return f"data:image/{img_format};base64,{b64_data}"


def _slugify(text: str, max_len: int = 24) -> str:
    """将图层名称转为安全的文件名片段（保留中英文与数字，其余转 -）。"""
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text).strip("-")
    return slug[:max_len] or "layer"


def bbox_base_to_input(
    bbox: list[int],
    base_size: str | tuple[int, int],
    input_size: tuple[int, int] | list[int],
) -> list[int] | None:
    """把图层 bbox 从**输出底图坐标系**换算到**原输入图**的像素坐标系。

    图层拆分的 ``bounding_box.absolute`` 用的是输出底图坐标（分辨率＝size 档位，
    例如 2K），而 agent 后续编辑的是**原输入图**，两者分辨率可能不同（宽高比一致），
    因此按比例换算。这样图层 bbox 就能与全局口径（原图像素）对齐、直接粘进 prompt。

    :param bbox: 底图坐标系下的 ``[left, top, right, bottom]``
    :param base_size: 底图尺寸（``"1664x2496"`` 或 ``(1664, 2496)``）
    :param input_size: 原输入图尺寸 ``(宽, 高)``
    :return: 原输入图像素坐标系下的 bbox；**底图尺寸无法解析时返回 None**
        （宁可明确"换算不了"，也不要回退成一组看起来合理、实际坐标错误的标签）
    """
    if isinstance(base_size, str):
        try:
            base_w, base_h = (int(v) for v in base_size.lower().split("x"))
        except (ValueError, TypeError):
            return None
    else:
        base_w, base_h = base_size
    in_w, in_h = input_size
    if base_w <= 0 or base_h <= 0 or in_w <= 0 or in_h <= 0:
        return None
    scaled = [
        round(bbox[0] * in_w / base_w), round(bbox[1] * in_h / base_h),
        round(bbox[2] * in_w / base_w), round(bbox[3] * in_h / base_h),
    ]
    return [
        max(0, min(in_w - 1, scaled[0])), max(0, min(in_h - 1, scaled[1])),
        max(0, min(in_w - 1, scaled[2])), max(0, min(in_h - 1, scaled[3])),
    ]


# ── 核心生成函数 ──────────────────────────────────────────────────────────────


def single_generate(
    item: dict,
    output_dir: str,
    timeout: int = 300,
) -> dict:
    """
    执行一次图像生成（文生图 / 图生图 / 交互编辑 / 图层拆分）。

    :param item: 任务参数
        - prompt (str, 可选): 提示词；图层拆分场景下可省略
        - size (str, 可选): 尺寸，默认 "2K"
        - image (str | list, 可选): 参考图 URL 或 URL 列表
        - output_format (str, 可选): "png" 或 "jpeg"
        - watermark (bool, 可选): 是否加水印
        - optimize_prompt_options (dict, 可选): 提示词优化配置
        - layer_decomposition (bool, 可选): 图层拆分开关（仅支持单张输入图）
        - background (str, 可选): "transparent" 或 "opaque"
    :param output_dir: 产物保存目录（通常是 run 目录下的 outputs/）
    :param timeout: API 超时秒数
    :return: 结果字典
        - status: "success" | "error"
        - image_path: 本地路径（图层拆分场景为底图） | None
        - all_images: 全部输出图的本地路径列表
        - records: 每张产物的记录（含 size / output_format / z_index / 图层信息）
        - layers: 图层拆分场景下的输出记录（含 z_index / name / bounding_box）
        - model: 模型 ID
        - output_dir: 目录路径
        - error: 错误信息 | None
    """
    # 强制 b64_json 模式确保本地保存
    item["response_format"] = "b64_json"

    is_layer_mode = bool(item.get("layer_decomposition"))
    output_format = item.get("output_format", "png")
    uid = uuid.uuid4().hex[:12]

    try:
        response = _call_api(item, timeout)

        if "error" in response:
            return {
                "status": "error",
                "image_path": None,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": str(response["error"]),
            }

        data_list = response.get("data", [])
        if not data_list:
            return {
                "status": "error",
                "image_path": None,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": "API 返回空数据",
            }

        records: list[dict] = []
        for i, img_data in enumerate(data_list):
            if "error" in img_data:
                continue

            # 图层拆分场景下 API 逐图返回 output_format（图层恒为 png），以响应为准
            img_format = img_data.get("output_format") or output_format
            ext = _FORMAT_TO_EXT.get(img_format, "png")

            z_index = img_data.get("z_index")
            if z_index is not None:
                filename = f"{uid}-L{z_index:02d}"
                if z_index > 0 and img_data.get("name"):
                    filename += f"-{_slugify(str(img_data['name']))}"
            else:
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
                records.append({
                    "path": local_path,
                    "size": img_data.get("size", ""),
                    "output_format": img_format,
                    "z_index": z_index,
                    "name": img_data.get("name"),
                    "description": img_data.get("description"),
                    "bounding_box": img_data.get("bounding_box"),
                })

        if records:
            # 图层拆分：底图（z_index=0）在前，其余按 z_index 升序；普通场景保持返回顺序
            records.sort(key=lambda r: (r["z_index"] is None, r["z_index"] or 0))
            # 坐标口径统一：图层 bbox 是像素（底图坐标系），这里一次性换成 prompt 标签，
            # 标签就是原图像素，agent 直接拿去用；坐标格式的转换在发送前统一完成
            if is_layer_mode:
                base = next((r for r in records if r.get("z_index") == 0), None)
                base_size = (base or {}).get("size")
                input_size = item.get("input_size")
                for rec in records:
                    box = (rec.get("bounding_box") or {}).get("absolute")
                    if not (rec.get("z_index") and isinstance(box, list) and len(box) == 4):
                        continue
                    # 底图坐标系原值始终保留：还原 / 重组图层要靠它（图层分辨率 = 底图分辨率）
                    rec["bbox_base"] = box
                    rec["bbox_base_size"] = base_size
                    if not base_size:
                        rec["bbox_note"] = (
                            "接口未返回底图尺寸，无法换算成原图像素标签；"
                            "可直接用 bbox_base + bbox_base_size 做图层还原"
                        )
                        continue
                    if not input_size:
                        rec["bbox_note"] = (
                            "参考图尺寸未知（网络 URL？），无法把底图坐标换算成原图像素标签；"
                            "改用本地图片路径即可获得可直接粘贴的 <bbox>"
                        )
                        continue
                    # 单独兜住：换算失败只降级为提示，不能把一次已经成功、已经花了额度的生成判成 error
                    try:
                        px = bbox_base_to_input(box, base_size, input_size)
                    except (ValueError, TypeError, ZeroDivisionError) as e:
                        rec["bbox_note"] = (
                            f"底图坐标换算失败（{type(e).__name__}: {e}），"
                            f"已保留 bbox_base 原值供还原使用"
                        )
                        continue
                    if px is None:
                        # 底图尺寸不是 WxH 形态（或非正）→ 明确说换算不了，不给出可疑标签
                        rec["bbox_note"] = (
                            f"底图尺寸 {base_size!r} 不是「宽x高」形态，无法换算成原图像素标签；"
                            f"已保留 bbox_base 原值供还原使用"
                        )
                        continue
                    # 对外一律原图像素：换算回输入图坐标系，标签可直接粘进 prompt
                    rec["bbox_pixel"] = px
                    rec["prompt_fragment"] = f"<bbox>{' '.join(str(v) for v in px)}</bbox>"
            results = [r["path"] for r in records]
            return {
                "status": "success",
                "image_path": results[0],  # 单图场景返回第一张；图层场景返回底图
                "all_images": results,
                "records": records,
                "layers": records if is_layer_mode else [],
                "uid": uid,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": None,
            }
        else:
            return {
                "status": "error",
                "image_path": None,
                "model": MODEL_ID,
                "output_dir": os.path.abspath(output_dir),
                "error": "生成失败：所有图片数据均为空",
            }

    except httpx.HTTPStatusError as e:
        return {
            "status": "error",
            "image_path": None,
            "model": MODEL_ID,
            "output_dir": os.path.abspath(output_dir),
            "error": str(e),
        }
    except httpx.RequestError as e:
        return {
            "status": "error",
            "image_path": None,
            "model": MODEL_ID,
            "output_dir": os.path.abspath(output_dir),
            "error": f"网络请求失败: {e}",
        }
    except Exception as e:
        return {
            "status": "error",
            "image_path": None,
            "model": MODEL_ID,
            "output_dir": os.path.abspath(output_dir),
            "error": f"{type(e).__name__}: {e}",
        }
