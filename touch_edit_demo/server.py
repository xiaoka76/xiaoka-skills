#!/usr/bin/env python3
# coding=utf-8
"""Self-contained TouchEdit study demo.

Serves local static files and exposes /api/generate that calls the Ark
images generation API (doubao-seedream) using the prompt + first image
composed by the frontend.
"""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from volcenginesdkarkruntime import Ark


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DEFAULT_PORT = 8090

ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "doubao-seedream-5-0-pro-260628"


def _json_dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _get_ark_client() -> Ark:
    api_key = os.getenv('ARK_API_KEY')
    if not api_key:
        raise RuntimeError("ARK_API_KEY environment variable is not set.")
    return Ark(base_url=ARK_BASE_URL, api_key=api_key)


class Handler(BaseHTTPRequestHandler):
    server_version = "TouchEditStudyDemo/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = _json_dumps(payload)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            return self._send_json(200, {"ok": True, "mode": "study"})
        return self._serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/generate":
            return self._handle_generate()
        return self._send_json(404, {"error": f"unknown endpoint: {path}"})

    def _handle_generate(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return self._send_json(400, {"error": f"invalid JSON: {exc}"})

        prompt = (payload.get("prompt") or "").strip()
        images = payload.get("images") or []
        if not prompt:
            return self._send_json(400, {"error": "prompt is required"})
        if not images:
            return self._send_json(400, {"error": "at least one image is required"})

        # 收集所有图片的 dataUrl；单张时以 string 传入，多张时以 list 传入
        image_urls = [img.get("dataUrl") for img in images if img.get("dataUrl")]
        if not image_urls:
            return self._send_json(400, {"error": "no image dataUrl found"})
        image_arg = image_urls[0] if len(image_urls) == 1 else image_urls

        try:
            client = _get_ark_client()
            resp = client.images.generate(
                model=ARK_MODEL,
                prompt=prompt,
                image=image_arg,
                size="2K",
                output_format="png",
                response_format="url",
                watermark=False,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[generate] error: {exc!r}")
            return self._send_json(500, {"error": str(exc)})

        try:
            url = resp.data[0].url
        except (AttributeError, IndexError) as exc:
            return self._send_json(502, {"error": f"unexpected ark response: {exc}"})

        return self._send_json(
            200,
            {
                "model": ARK_MODEL,
                "prompt": prompt,
                "url": url,
            },
        )

    def _serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        rel_path = unquote(path.lstrip("/"))
        file_path = (STATIC_DIR / rel_path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.is_file():
            self.send_error(404)
            return

        mime, _ = mimetypes.guess_type(str(file_path))
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"TouchEdit study demo listening on http://localhost:{port}")
    print(f"Using Ark model: {ARK_MODEL}")
    if not os.environ.get("ARK_API_KEY"):
        print("[warn] ARK_API_KEY is not set; /api/generate will fail until it is exported.")
    server.serve_forever()


if __name__ == "__main__":
    main()
