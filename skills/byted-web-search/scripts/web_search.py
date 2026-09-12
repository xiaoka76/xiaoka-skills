# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env python3
"""火山引擎豆包搜索 API 客户端（双引擎：Custom / Global）。

Custom 版（默认，原名 联网搜索/融合信息搜索）：
    官方文档：https://www.volcengine.com/docs/85508/1650263
    新版 API 参考：https://www.volcengine.com/docs/87772/2272953
    URL: https://open.feedcoopapi.com/search_api/web_search （API Key）
      或 mercury.volcengineapi.com?Action=WebSearch&Version=2025-01-01 （AK/SK TOP网关）
    能力：文搜文/文搜图、权威分级、时效范围、Query 改写、行业搜索

Global 版（--engine global，豆包搜索 Global 版）：
    接口文档：https://www.volcengine.com/docs/87772/2548026
    URL: https://open.feedcoopapi.com/search_api/global_search
    仅支持 API Key（按量后付费 Key），不支持 AK/SK / TOP 网关。
    能力：文搜文/文搜图/图搜图(visual)、全球站点覆盖、摘要长度可调、
         单条结果多图、ICP 备案过滤

签名参考：https://github.com/volcengine/volc-openapi-demos/blob/main/signature/python/sign.py

凭证（Claw 中优先）：拿 Key 后直接在聊天框发给我即可，无需编辑配置。
认证优先级：1) WEB_SEARCH_API_KEY 或 --api-key  2) VOLCENGINE_ACCESS_KEY+SECRET_KEY（仅 Custom）  3) VeFaaS IAM（仅 Custom）

示例：
    python web_search.py "北京天气"                                  # Custom 文搜文
    python web_search.py "OpenAI 最新发布" --time-range OneWeek      # Custom 时效
    python web_search.py "故宫博物院" --type image --count 3         # Custom 文搜图
    python web_search.py --engine global "OpenAI latest news"        # Global 文搜文
    python web_search.py --engine global "山景" --type image         # Global 文搜图
    python web_search.py --engine global "同款商品" --type visual \
        --image-url https://example.com/img.jpg                      # Global 图搜图
"""

import argparse
import base64
import datetime
import getpass
import hashlib
import hmac
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import quote

SERVICE = "volc_torchlight_api"
VERSION = "2025-01-01"
REGION = "cn-beijing"
HOST = "mercury.volcengineapi.com"
ACTION = "WebSearch"
INTERNAL_API_URL = "https://open.feedcoopapi.com/search_api/web_search"
GLOBAL_API_URL = "https://open.feedcoopapi.com/search_api/global_search"
TRAFFIC_TAG_HEADER = "X-Traffic-Tag"
TRAFFIC_TAG_VALUE = "skill_web_search_common"
TIME_RANGE_SHORTCUTS = {"OneDay", "OneWeek", "OneMonth", "OneYear"}
DATE_RANGE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$")
LEGACY_ENV_PATH = "/root/.openclaw/.env"
USER_ENV_PATH = str(Path.home() / ".openclaw/.env")
SUMMARY_PREVIEW_LIMIT = 1000
ERROR_HINTS = {
    "10400": "提示：参数错误。请检查 Query、Count、DocCount、TimeRange 等参数格式是否正确。",
    "10402": "提示：搜索类型非法。Custom 支持 web/image；Global 支持 web/image/visual。",
    "10403": "提示：账号或权限异常。请确认 API Key 来自联网搜索控制台，或检查账号权限。",
    "10406": "提示：免费额度已耗尽。请检查账户额度或联系支持。",
    "10407": "提示：当前无可用免费策略。请检查账户状态或联系支持。",
    "10408": "提示：服务未付费开通。请到控制台确认是否已开通付费调用。",
    "10409": "提示：套餐模式不支持。Global 版仅支持按量后付费，请确认 Key 来自「按量后付费」tab。",
    "10410": "提示：无可用搜索套餐。请检查账号是否已开通豆包搜索套餐。",
    "10412": "提示：搜索套餐额度不足。请检查套餐额度或联系运营处理。",
    "10500": "提示：服务内部错误。建议稍后重试，或联系支持。",
    "10501": "提示：免费额度链路依赖失败。可重试，持续失败请携带 RequestId 排查。",
    "700429": "提示：免费链路触发限流。请降频后重试。",
    "700901": "提示：APIKey 无效（Global 版）。请检查 Authorization 是否为 Bearer APIKey，且 Key 来自「按量后付费」tab。",
    "100013": "提示：子账号未授权 TorchlightApiFullAccess。",
}


# ---- 依赖加载 ----

def _require_requests():
    try:
        import requests
    except ImportError:
        print("Error: requests not installed. Run: pip install requests", file=sys.stderr)
        sys.exit(1)
    return requests


def _load_legacy_env_file(env_path: str = LEGACY_ENV_PATH) -> None:
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue

                try:
                    parsed = shlex.split(value, comments=True)
                    value = parsed[0] if parsed else ""
                except ValueError:
                    value = value.strip("\"'")

                os.environ.setdefault(key, value)
    except OSError:
        return


def _load_legacy_env_files() -> None:
    seen_paths = set()
    for env_path in (LEGACY_ENV_PATH, USER_ENV_PATH):
        normalized = os.path.abspath(os.path.expanduser(env_path))
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        _load_legacy_env_file(normalized)


# ---- 火山引擎 HMAC-SHA256 签名 (基于官方示例) ----

def _hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def _hash_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _norm_query(params: dict) -> str:
    query = ""
    for key in sorted(params.keys()):
        if isinstance(params[key], list):
            for value in params[key]:
                query += quote(key, safe="-_.~") + "=" + quote(value, safe="-_.~") + "&"
        else:
            query += quote(key, safe="-_.~") + "=" + quote(str(params[key]), safe="-_.~") + "&"
    return query[:-1].replace("+", "%20") if query else ""


def _utc_now():
    try:
        from datetime import timezone
        return datetime.datetime.now(timezone.utc)
    except ImportError:
        return datetime.datetime.utcnow()


def _sign_request(method: str, ak: str, sk: str, body: str, session_token: str = "") -> dict:
    now = _utc_now()
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    x_content_sha256 = _hash_sha256(body)
    content_type = "application/json"

    query_params = {"Action": ACTION, "Version": VERSION}

    signed_header_keys = ["content-type", "host", "x-content-sha256", "x-date", "x-traffic-tag"]
    if session_token:
        signed_header_keys.append("x-security-token")
    signed_header_keys.sort()
    signed_headers_str = ";".join(signed_header_keys)

    canonical_header_lines = [
        f"content-type:{content_type}",
        f"host:{HOST}",
        f"x-content-sha256:{x_content_sha256}",
        f"x-date:{x_date}",
        f"x-traffic-tag:{TRAFFIC_TAG_VALUE}",
    ]
    if session_token:
        canonical_header_lines.append(f"x-security-token:{session_token}")
        canonical_header_lines.sort()

    canonical_request = "\n".join(
        [
            method.upper(),
            "/",
            _norm_query(query_params),
            "\n".join(canonical_header_lines),
            "",
            signed_headers_str,
            x_content_sha256,
        ]
    )

    credential_scope = f"{short_date}/{REGION}/{SERVICE}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            credential_scope,
            _hash_sha256(canonical_request),
        ]
    )

    k_date = _hmac_sha256(sk.encode("utf-8"), short_date)
    k_region = _hmac_sha256(k_date, REGION)
    k_service = _hmac_sha256(k_region, SERVICE)
    k_signing = _hmac_sha256(k_service, "request")
    signature = _hmac_sha256(k_signing, string_to_sign).hex()

    authorization = (
        f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers_str}, "
        f"Signature={signature}"
    )

    headers = {
        "Content-Type": content_type,
        "Host": HOST,
        "X-Date": x_date,
        "X-Content-Sha256": x_content_sha256,
        TRAFFIC_TAG_HEADER: TRAFFIC_TAG_VALUE,
        "Authorization": authorization,
    }
    if session_token:
        headers["X-Security-Token"] = session_token
    return headers


# ---- 凭证获取 ----

def _get_credentials() -> tuple:
    """返回 (ak, sk, session_token)。"""
    ak = os.getenv("VOLCENGINE_ACCESS_KEY")
    sk = os.getenv("VOLCENGINE_SECRET_KEY")
    if ak and sk:
        return ak, sk, ""

    try:
        from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

        cred = get_credential_from_vefaas_iam()
        return cred.access_key_id, cred.secret_access_key, cred.session_token
    except Exception:
        return None, None, ""


# ---- 请求构建 ----

def _get_api_key(cli_api_key: Optional[str]) -> Optional[str]:
    api_key = cli_api_key or os.getenv("WEB_SEARCH_API_KEY")
    return api_key.strip() if api_key else None


def _validate_time_range(time_range: Optional[str]) -> Optional[str]:
    if not time_range:
        return None
    if time_range in TIME_RANGE_SHORTCUTS:
        return time_range

    match = DATE_RANGE_PATTERN.match(time_range)
    if not match:
        raise ValueError(
            "--time-range 需为 OneDay/OneWeek/OneMonth/OneYear，或日期区间 YYYY-MM-DD..YYYY-MM-DD。"
        )

    start_text, end_text = match.groups()
    try:
        start_date = datetime.date.fromisoformat(start_text)
        end_date = datetime.date.fromisoformat(end_text)
    except ValueError as exc:
        raise ValueError("--time-range 中的日期需为有效的 YYYY-MM-DD。") from exc

    if start_date > end_date:
        raise ValueError("--time-range 的开始日期不能晚于结束日期。")

    return time_range


def build_body_custom(
        query: str,
        search_type: str = "web",
        count: int = 10,
        time_range: Optional[str] = None,
        auth_level: int = 0,
        query_rewrite: bool = False,
) -> dict:
    """Custom 版请求体。"""
    body = {"Query": query, "SearchType": search_type, "Count": count}

    if search_type == "web":
        body["NeedSummary"] = True
        filters = {}
        if auth_level > 0:
            filters["AuthInfoLevel"] = auth_level
        if filters:
            body["Filter"] = filters
        if time_range:
            body["TimeRange"] = time_range

    if query_rewrite:
        body["QueryControl"] = {"QueryRewrite": True}

    return body


def build_body_global(
        query: str,
        search_type: str = "web",
        doc_count: int = 10,
        max_snippet_length: Optional[int] = None,
        max_image_count_per_doc: Optional[int] = None,
        icp_host_only: bool = False,
        image_filter: Optional[dict] = None,
        image_query: Optional[dict] = None,
        enable_waiting: bool = False,
        max_wait_time: Optional[int] = None,
) -> dict:
    """Global 版请求体。"""
    body = {"SearchType": search_type}

    if search_type == "visual":
        # 图搜图：Query 可选（辅助检索），ImageQuery 必填
        if query:
            body["Query"] = query
        if image_query is not None:
            body["ImageQuery"] = image_query
        if doc_count is not None and doc_count > 0:
            body["DocCount"] = doc_count
        if max_snippet_length:
            body["MaxSnippetLength"] = max_snippet_length
    else:
        body["Query"] = query
        if doc_count is not None:
            body["DocCount"] = doc_count
        if max_snippet_length:
            body["MaxSnippetLength"] = max_snippet_length

    if search_type == "web" and max_image_count_per_doc:
        body["MaxImageCountPerDoc"] = max_image_count_per_doc
    if search_type == "image" and image_filter:
        body["ImageFilter"] = image_filter

    if icp_host_only:
        body["Filter"] = {"IcpHostOnly": True}

    if enable_waiting:
        body["EnableWaiting"] = True
        if max_wait_time:
            body["MaxWaitTime"] = max_wait_time

    return body


# ---- API 调用 ----

def do_search(
        body: dict,
        engine: str = "custom",
        api_key: Optional[str] = None,
        ak: Optional[str] = None,
        sk: Optional[str] = None,
        session_token: str = "",
):
    requests = _require_requests()
    body_str = json.dumps(body, ensure_ascii=False)

    if engine == "global":
        # Global 版仅支持 API Key（Bearer），不支持 AK/SK TOP 网关
        if not api_key:
            raise ValueError("Global 版仅支持 API Key 认证，请设置 WEB_SEARCH_API_KEY 或传入 --api-key（按量后付费 Key）。")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        url = GLOBAL_API_URL
    elif api_key:
        headers = {
            "Content-Type": "application/json",
            TRAFFIC_TAG_HEADER: TRAFFIC_TAG_VALUE,
            "Authorization": f"Bearer {api_key}",
        }
        url = INTERNAL_API_URL
    else:
        if not ak or not sk:
            raise ValueError("missing volcengine credentials")
        headers = _sign_request("POST", ak, sk, body_str, session_token)
        url = f"https://{HOST}?Action={ACTION}&Version={VERSION}"

    response = requests.post(url, headers=headers, data=body_str.encode("utf-8"), timeout=30)
    response.raise_for_status()
    return response.json()


# ---- 输出格式化 ----

def _format_snippet_text(snippet_list) -> str:
    """Global 版 Snippet 数组 → 拼接文本。"""
    parts = []
    for s in snippet_list or []:
        if isinstance(s, dict) and s.get("Type") == "text" and s.get("Text"):
            parts.append(s["Text"].strip())
    return "\n".join(parts)


def _format_snippet_images(snippet_list, limit: int = 3) -> list:
    """Global 版 Snippet 数组 → 图片列表。"""
    images = []
    for s in snippet_list or []:
        if isinstance(s, dict) and s.get("Type") == "image":
            img = s.get("Image") or {}
            images.append(img)
    return images[:limit]


def format_output_custom(data: dict, search_type: str) -> str:
    result = data.get("Result", {})
    lines = [f"结果数: {result.get('ResultCount', 0)}  耗时: {result.get('TimeCost', 0)}ms", ""]

    if search_type == "web":
        for item in result.get("WebResults") or []:
            lines.append(f"[{item.get('SortId', '')}] {item.get('Title', '')}")

            meta_parts = [part for part in [item.get("SiteName", ""), item.get("AuthInfoDes", "")] if part]
            if meta_parts:
                lines.append(f"    {' | '.join(meta_parts)}")

            if item.get("Url"):
                lines.append(f"    {item['Url']}")

            summary = item.get("Summary") or item.get("Snippet", "")
            if summary:
                lines.append(f"    {summary[:SUMMARY_PREVIEW_LIMIT]}")
            lines.append("")

    elif search_type == "image":
        for item in result.get("ImageResults") or []:
            image = item.get("Image", {})
            lines.append(f"[{item.get('SortId', '')}] {item.get('Title', '')}")
            if image.get("Url"):
                lines.append(f"    {image['Url']}")
            lines.append(f"    {image.get('Width', '?')}x{image.get('Height', '?')} ({image.get('Shape', '')})")
            lines.append("")

    return "\n".join(lines)


def format_output_global(data: dict, search_type: str) -> str:
    result = data.get("Result", {})
    lines = [f"总结果数: {result.get('TotalDocCount', 0)}", ""]

    for item in result.get("Documents") or []:
        title = item.get("Title", "")
        lines.append(f"[{item.get('Rank', '')}] {title}")

        host = item.get("HostInfo") or {}
        doc_info = item.get("DocumentInfo") or {}
        meta_parts = []
        if host.get("Hostname"):
            meta_parts.append(host["Hostname"])
        if host.get("AuthorityLevel"):
            meta_parts.append(f"权威度:{host['AuthorityLevel']}")
        if doc_info.get("Filetype") and doc_info["Filetype"] != "webpage":
            meta_parts.append(doc_info["Filetype"])
        if doc_info.get("PublishTime"):
            meta_parts.append(f"发布时间:{doc_info['PublishTime']}")
        if meta_parts:
            lines.append(f"    {' | '.join(meta_parts)}")

        if item.get("Url"):
            lines.append(f"    {item['Url']}")

        if search_type == "web":
            text = _format_snippet_text(item.get("Snippet"))
            if text:
                lines.append(f"    {text[:SUMMARY_PREVIEW_LIMIT]}")
            images = _format_snippet_images(item.get("Snippet"))
            for img in images:
                if img.get("ImageUrl"):
                    lines.append(f"    [图] {img['ImageUrl']}")
        else:
            # image / visual：Snippet 中的图片为主
            images = _format_snippet_images(item.get("Snippet"))
            for img in images:
                if img.get("ImageUrl"):
                    lines.append(f"    [图] {img['ImageUrl']}")
                    lines.append(f"    {img.get('Width', '?')}x{img.get('Height', '?')} {img.get('Alt', '')}")
            text = _format_snippet_text(item.get("Snippet"))
            if text:
                lines.append(f"    {text[:SUMMARY_PREVIEW_LIMIT]}")

        lines.append("")

    return "\n".join(lines)


def format_output(data: dict, engine: str, search_type: str) -> str:
    if engine == "global":
        return format_output_global(data, search_type)
    return format_output_custom(data, search_type)


# ---- CLI ----

def _parse_image_query(image_url: Optional[str], image_base64: Optional[str], roi: Optional[str]) -> dict:
    """构造 Global 图搜图 ImageQuery。"""
    if not image_url and not image_base64:
        raise ValueError("图搜图(visual) 需要 --image-url 或 --image-base64（二选一）。")
    if image_url and image_base64:
        raise ValueError("--image-url 与 --image-base64 只能传一个。")

    image_query = {}
    if image_url:
        image_query["Url"] = image_url
    else:
        image_query["ImageBase64"] = image_base64

    if roi:
        parts = roi.split(",")
        if len(parts) != 4:
            raise ValueError("--roi 需为 4 个相对坐标：XMin,YMin,XMax,YMax（0~1，如 0.1,0.1,0.9,0.9）。")
        try:
            xmin, ymin, xmax, ymax = (float(p) for p in parts)
        except ValueError as exc:
            raise ValueError("--roi 坐标需为数字。") from exc
        if not (0 <= xmin < xmax <= 1 and 0 <= ymin < ymax <= 1):
            raise ValueError("--roi 需满足 0 ≤ XMin < XMax ≤ 1，0 ≤ YMin < YMax ≤ 1。")
        image_query["RegionOfInterest"] = {
            "XMin": xmin, "YMin": ymin, "XMax": xmax, "YMax": ymax,
        }

    return image_query


def _parse_image_filter(short_edge_min, short_edge_max, aspect_min, aspect_max) -> Optional[dict]:
    """构造 Global 文搜图 ImageFilter。"""
    values = [short_edge_min, short_edge_max, aspect_min, aspect_max]
    if all(v is None for v in values):
        return None

    image_filter = {}
    if short_edge_min is not None:
        image_filter["ShortEdgePixelMin"] = short_edge_min
    if short_edge_max is not None:
        image_filter["ShortEdgePixelMax"] = short_edge_max
    if aspect_min is not None:
        image_filter["AspectRatioMin"] = aspect_min
    if aspect_max is not None:
        image_filter["AspectRatioMax"] = aspect_max
    return image_filter


def main():
    _load_legacy_env_files()
    # 尝试从 skill 根目录加载 .env（与 scripts/ 同级）
    _skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _load_legacy_env_file(os.path.join(_skill_root, ".env"))

    parser = argparse.ArgumentParser(
        description="火山引擎豆包搜索 API（Custom / Global 双引擎）\n"
        "Custom: https://www.volcengine.com/docs/87772/2272953\n"
        "Global: https://www.volcengine.com/docs/87772/2548026\n"
        "凭证：Claw 中直接在聊天框发 Key 即可；或 WEB_SEARCH_API_KEY / --api-key"
    )
    parser.add_argument("query", nargs="?", default="", help="搜索关键词（visual 图搜图时可留空）")
    parser.add_argument("--engine", "-e", default="custom", choices=["custom", "global"],
                        help="custom=Custom版(默认)；global=Global版")
    parser.add_argument("--type", "-t", default="web", help="web/image/visual（visual 仅 global）")
    parser.add_argument("--count", "-c", type=int, default=None,
                        help="返回条数：custom web≤50/image≤5；global ≤20")
    parser.add_argument("--time-range", help="[仅 custom] OneDay/OneWeek/OneMonth/OneYear/YYYY-MM-DD..YYYY-MM-DD")
    parser.add_argument("--auth-level", type=int, default=0, choices=[0, 1], help="[仅 custom] 1=仅权威来源")
    parser.add_argument("--query-rewrite", action="store_true", help="[仅 custom] 开启 Query 改写")
    parser.add_argument("--max-snippet-length", type=int, default=None,
                        help="[仅 global] 单个摘要片段最大 tokens（≤3000，推荐 ≤1000）")
    parser.add_argument("--max-image-count", type=int, default=None,
                        help="[仅 global] 单条 web 结果最多返回图片数（≤10，默认3）")
    parser.add_argument("--icp-host-only", action="store_true",
                        help="[仅 global] 仅在国内 ICP 备案网站中搜索")
    parser.add_argument("--image-url", help="[仅 global visual] 查询图片 URL")
    parser.add_argument("--image-base64", help="[仅 global visual] 查询图片纯 Base64（无 data: 前缀）")
    parser.add_argument("--image-file", help="[仅 global visual] 本地图片文件（自动转 Base64）")
    parser.add_argument("--roi", help="[仅 global visual] 感兴趣区域 XMin,YMin,XMax,YMax（0~1）")
    parser.add_argument("--short-edge-min", type=int, default=None, help="[仅 global image] 图片短边下限")
    parser.add_argument("--short-edge-max", type=int, default=None, help="[仅 global image] 图片短边上限")
    parser.add_argument("--aspect-ratio-min", type=float, default=None, help="[仅 global image] 宽高比下限(h/w)")
    parser.add_argument("--aspect-ratio-max", type=float, default=None, help="[仅 global image] 宽高比上限(h/w)")
    parser.add_argument("--enable-waiting", action="store_true", help="[仅 global] 开启队列模式")
    parser.add_argument("--max-wait-time", type=int, default=None, help="[仅 global] 队列等待上限 ms（≤10000）")
    parser.add_argument("--api-key", help="API Key（优先于环境变量 WEB_SEARCH_API_KEY）")
    parser.add_argument("--prompt-api-key", action="store_true", help="交互式输入 API Key（不回显）")

    args = parser.parse_args()

    # ---- 参数校验 ----

    # 引擎/类型组合
    if args.type not in ("web", "image", "visual"):
        print(f"Error: --type 仅支持 web/image/visual，收到 '{args.type}'。", file=sys.stderr)
        sys.exit(1)
    if args.type == "visual" and args.engine != "global":
        print("Error: 图搜图(visual) 仅 Global 版支持，请加 --engine global。", file=sys.stderr)
        sys.exit(1)

    # 查询词（visual 可空）
    if args.engine == "visual" or (args.engine == "global" and args.type == "visual"):
        query_required = False
    else:
        query_required = True
    if query_required and (not args.query or not args.query.strip()):
        print("Error: 请输入搜索词。", file=sys.stderr)
        sys.exit(1)
    if args.query and len(args.query) > 100:
        print("Error: 搜索词超过 100 字符，API 可能截断。建议精简后重试。", file=sys.stderr)
        sys.exit(1)

    # 各引擎不支持的参数
    if args.engine == "global" and (args.time_range or args.auth_level or args.query_rewrite):
        print("Error: --time-range/--auth-level/--query-rewrite 仅 Custom 版支持，Global 版请去掉这些参数。", file=sys.stderr)
        sys.exit(1)

    # count
    if args.count is not None and args.count < 1:
        print("Error: --count 需 ≥ 1。", file=sys.stderr)
        sys.exit(1)
    if args.engine == "custom":
        if args.count is None:
            args.count = 10
        if args.type == "image" and args.count > 5:
            print("Error: custom image 类型最多返回 5 条，请调整 --count。", file=sys.stderr)
            sys.exit(1)
        if args.type == "web" and args.count > 50:
            print("Error: custom web 类型最多返回 50 条，请调整 --count。", file=sys.stderr)
            sys.exit(1)
    else:
        if args.count is not None and args.count > 20:
            print("Error: global 最多返回 20 条，请调整 --count。", file=sys.stderr)
            sys.exit(1)

    # Global 专属参数范围
    if args.engine == "global":
        if args.max_snippet_length is not None and not (0 < args.max_snippet_length <= 3000):
            print("Error: --max-snippet-length 需在 1~3000 之间。", file=sys.stderr)
            sys.exit(1)
        if args.max_image_count is not None and not (0 < args.max_image_count <= 10):
            print("Error: --max-image-count 需在 1~10 之间。", file=sys.stderr)
            sys.exit(1)
        if args.max_wait_time is not None and not (0 < args.max_wait_time <= 10000):
            print("Error: --max-wait-time 需在 1~10000 之间。", file=sys.stderr)
            sys.exit(1)

    # 图搜图参数
    image_query = None
    if args.engine == "global" and args.type == "visual":
        if args.image_file:
            try:
                with open(args.image_file, "rb") as f:
                    args.image_base64 = base64.b64encode(f.read()).decode("ascii")
            except OSError as exc:
                print(f"Error: 无法读取图片文件 {args.image_file}: {exc}", file=sys.stderr)
                sys.exit(1)
        try:
            image_query = _parse_image_query(args.image_url, args.image_base64, args.roi)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    image_filter = None
    if args.engine == "global" and args.type == "image":
        image_filter = _parse_image_filter(
            args.short_edge_min, args.short_edge_max,
            args.aspect_ratio_min, args.aspect_ratio_max,
        )

    try:
        time_range = _validate_time_range(args.time_range) if args.engine == "custom" else None
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ---- 凭证 ----

    api_key = _get_api_key(args.api_key)
    if not api_key and args.prompt_api_key:
        entered = getpass.getpass("API Key: ").strip()
        api_key = entered or None

    ak = sk = session_token = None
    if args.engine == "global":
        if not api_key:
            print(
                "Error: Global 版需要 API Key（按量后付费）。请配置任一方式：\n"
                "1) 【推荐】若在 Claw 中使用：拿 Key 后直接在聊天框发给我即可，无需编辑配置\n"
                "2) API Key：设置 WEB_SEARCH_API_KEY 或传入 --api-key\n"
                "Global 版不支持 AK/SK 签名。开通指南：references/setup-guide.md 或 SKILL.md",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        if not api_key:
            ak, sk, session_token = _get_credentials()
            if not ak or not sk:
                print(
                    "Error: 未找到凭证。请配置以下任一方式：\n"
                    "1) 【推荐】若在 Claw 中使用：拿 Key 后直接在聊天框发给我即可，无需编辑配置\n"
                    "2) API Key：设置 WEB_SEARCH_API_KEY 或传入 --api-key\n"
                    "3) AK/SK：设置 VOLCENGINE_ACCESS_KEY 和 VOLCENGINE_SECRET_KEY\n"
                    "开通指南：references/setup-guide.md 或 SKILL.md",
                    file=sys.stderr,
                )
                sys.exit(1)

    # ---- 构建请求体 ----

    if args.engine == "global":
        body = build_body_global(
            query=args.query.strip(),
            search_type=args.type,
            doc_count=args.count,
            max_snippet_length=args.max_snippet_length,
            max_image_count_per_doc=args.max_image_count,
            icp_host_only=args.icp_host_only,
            image_filter=image_filter,
            image_query=image_query,
            enable_waiting=args.enable_waiting,
            max_wait_time=args.max_wait_time,
        )
    else:
        body = build_body_custom(
            query=args.query.strip(),
            search_type=args.type,
            count=args.count,
            time_range=time_range,
            auth_level=args.auth_level,
            query_rewrite=args.query_rewrite,
        )

    requests = _require_requests()
    try:
        data = do_search(
            body,
            engine=args.engine,
            api_key=api_key,
            ak=ak,
            sk=sk,
            session_token=session_token or "",
        )
    except requests.exceptions.HTTPError as exc:
        print(f"HTTP Error: {exc}", file=sys.stderr)
        if exc.response is not None:
            status = exc.response.status_code
            body = exc.response.text or ""
            if status == 429:
                print(
                    "提示：请求频率过高触发限流，建议降频后重试。"
                    "详见 references/setup-guide.md",
                    file=sys.stderr,
                )
            elif status == 401 and ("InvalidAccessKey" in body or "invalid" in body.lower()):
                print(
                    "提示：AK/SK 无效或已失效。请检查 VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY，"
                    "或改用 API Key（Claw 中可直接在聊天框发给我）。详见 references/setup-guide.md",
                    file=sys.stderr,
                )
            else:
                print(body, file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if data is None:
        print("No response.", file=sys.stderr)
        sys.exit(1)

    error = (data.get("ResponseMetadata") or {}).get("Error")
    if error:
        code = error.get("Code", "")
        msg = error.get("Message", "")
        print(f"API Error [{code}]: {msg}", file=sys.stderr)
        if str(code).lower() == "invalid_api_key" or "10403" in str(code):
            if args.engine == "global":
                print(
                    "提示：Global 版请确认 API Key 来自联网搜索控制台「按量后付费」tab "
                    "https://console.volcengine.com/search-infinity/api-key?tab=post_paid ，"
                    "而非订阅套餐/Agent Plan Key。若在 Claw 中，可重新在聊天框发正确的 Key 给我。",
                    file=sys.stderr,
                )
            else:
                print(
                    "提示：请确认 API Key 来自联网搜索控制台 https://console.volcengine.com/search-infinity/api-key ，"
                    "而非火山方舟(Ark)。若在 Claw 中，可重新在聊天框发正确的 Key 给我。详见 references/setup-guide.md",
                    file=sys.stderr,
                )
        elif "429" in str(code) or "flowlimit" in str(code).lower() or "100018" in str(code):
            print(
                "提示：请求频率过高触发限流，建议降频后重试。",
                file=sys.stderr,
            )
        else:
            hint = ERROR_HINTS.get(str(code))
            if hint:
                print(hint, file=sys.stderr)
        sys.exit(1)

    print(format_output(data, args.engine, args.type))


if __name__ == "__main__":
    main()
