"""
任务记录（run）—— 目录布局、命名、索引与读写。

一次生成 = 一个 run，落在 ``<home>/runs/<run_id>/``：

.. code-block:: text

    .seedream/
    ├── index.jsonl                  # append-only，一行一条，供 ls 直接读
    └── runs/
        └── 20261008-143022-a1b2c3/
            ├── run.json             # 唯一真相：这图是怎么来的
            ├── inputs/              # 参考图副本（内容寻址命名，可复用）
            └── outputs/             # 产物

设计要点：
- 目录名以日期时间开头 → ``ls runs/`` 自带时间排序，人和 agent 都不必解析 JSON
- 参考图在**发请求之前**就落盘并记入 run.json → 即使生成失败，输入依旧可复用
- run.json 是唯一真相：不再另写 per-image 的 .md 元数据（旧版散在两处，口径不一）
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import struct
import uuid
from datetime import datetime
from pathlib import Path

from .config import ensure_home, index_path, runs_dir
from .generate import probe_image_size

# ── 常量 ──────────────────────────────────────────────────────────────────────

# 四种生成意图，与四个子命令一一对应
RUN_KINDS: tuple[str, ...] = ("draw", "edit", "split", "cutout")

# run id 形态：YYYYMMDD-HHMMSS-<6 位随机十六进制>
# 随机位为 6；放宽到 4~8 是为了让「索引缺失」回退扫描也能认出更早/更晚格式的目录
RUN_ID_RE: re.Pattern[str] = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4,8}$")

_VALID_STATUS: set[str] = {"pending", "running", "success", "error"}


# ── 命名与路径 ────────────────────────────────────────────────────────────────


def new_run_id() -> str:
    """
    生成新的 run id，形如 ``20261008-143022-a1b2c3``（日期时间 + 6 位随机十六进制）。

    :return: run id 字符串
    """
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def run_dir(run_id: str) -> Path:
    """返回指定 run 的目录：``<home>/runs/<run_id>``。"""
    return runs_dir() / run_id


def _pick_free_run_id() -> str:
    """
    挑一个当前尚不存在的 run id。

    同一秒内连续跑多个任务时，随机位再宽也可能撞上；这里显式查重，
    避免两次任务被 ``mkdir(exist_ok=True)`` 合并进同一个目录、互相覆盖产物与记录。

    :return: 未被占用的 run id
    """
    for _ in range(20):
        candidate = new_run_id()
        if not (runs_dir() / candidate).exists():
            return candidate
    raise RuntimeError("无法分配新的任务 id（同一秒内连续创建过多任务），请稍后重试")


def create_run(run_id: str | None = None) -> tuple[str, Path]:
    """
    创建一次任务的目录骨架（run.json 由 :func:`save_run` 后续写入）。

    :param run_id: 指定 run id；为 None 时自动生成（并确保不与已有目录重名）
    :return: (run_id, run 目录路径) 元组
    """
    ensure_home()
    rid = run_id or _pick_free_run_id()
    directory = runs_dir() / rid
    (directory / "inputs").mkdir(parents=True, exist_ok=True)
    (directory / "outputs").mkdir(parents=True, exist_ok=True)
    return rid, directory


def resolve_run(ref: str | None = None) -> tuple[str, Path]:
    """
    把用户输入的任务引用解析成 (run_id, 目录)。

    支持三种写法：
    - ``None`` / ``"last"``：最近一次任务
    - run id（``20261008-143022-a1b2``）
    - 目录路径或 run.json 路径

    :param ref: 任务引用
    :return: (run_id, 目录) 元组
    :raises FileNotFoundError: 找不到目标任务
    """
    if ref is None or ref == "last":
        latest = read_index(limit=1)
        if latest:
            rid = latest[0]["run_id"]
            candidate = runs_dir() / rid
            if candidate.is_dir():
                return rid, candidate
        # 索引缺失或指向已删除目录时，按 run.json 里的 created_at 找最新
        # （不能按目录名排序：同一秒内的多个任务，id 的随机后缀会破坏字典序）
        best: tuple[str, str, Path] | None = None
        if runs_dir().is_dir():
            for p in runs_dir().iterdir():
                if not p.is_dir() or not RUN_ID_RE.match(p.name):
                    continue
                try:
                    created = load_run(p).get("created_at") or ""
                except (OSError, json.JSONDecodeError):
                    created = ""
                key = (created, p.name)
                if best is None or key > (best[0], best[1]):
                    best = (created, p.name, p)
        if best is not None:
            return best[1], best[2]
        raise FileNotFoundError("还没有任何生成任务（先用 draw / edit / split / cutout 生成一次）")

    # 显式路径（目录或 run.json 文件）
    p = Path(ref).expanduser()
    if p.exists():
        if p.is_file():
            p = p.parent
        if (p / "run.json").exists():
            return p.name, p.resolve()

    # run id
    candidate = runs_dir() / ref
    if candidate.is_dir():
        return ref, candidate

    raise FileNotFoundError(f"找不到任务: {ref}")


# ── 读写 ──────────────────────────────────────────────────────────────────────


def save_run(directory: Path, data: dict) -> None:
    """
    原子写入 run.json（先写临时文件再 os.replace，避免中途崩溃留下坏文件）。

    :param directory: run 目录
    :param data: 完整记录
    """
    directory = Path(directory)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    tmp = directory / "run.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, directory / "run.json")


def load_run(directory: Path) -> dict:
    """
    读取 run.json。

    :param directory: run 目录或 run.json 路径
    :return: 记录字典
    """
    directory = Path(directory)
    path = directory if directory.suffix == ".json" else directory / "run.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_index(data: dict) -> None:
    """
    把一条任务摘要追加到 index.jsonl（append-only，供 ``ls`` 快速读取）。

    :param data: 完整记录
    """
    ensure_home()
    entry = {
        "run_id": data.get("run_id", ""),
        "kind": data.get("kind", ""),
        "status": data.get("status", ""),
        "created_at": data.get("created_at", ""),
        "prompt": (data.get("prompt") or "")[:200],
        "inputs": len(data.get("inputs", [])),
        "outputs": len(data.get("outputs", [])),
    }
    with open(index_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_index(limit: int | None = None) -> list[dict]:
    """
    倒序读取索引（最新在前）。同一 run 有多条时只保留最后一条。

    :param limit: 最多返回条数
    :return: 摘要字典列表
    """
    path = index_path()
    if not path.exists():
        return []
    latest: dict[str, dict] = {}
    order: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = entry.get("run_id", "")
            if not rid:
                continue
            if rid not in latest:
                order.append(rid)
            latest[rid] = entry
    entries = [latest[rid] for rid in order]
    entries.reverse()
    alive: list[dict] = []
    for entry in entries:
        directory = runs_dir() / entry["run_id"]
        # 索引是 append-only 的：任务目录被外部删掉（例如手工清理）后，索引里会留下幽灵条目。
        # 这里以**磁盘为准**跳过它，否则 `ls` 会列出一堆 `show` 打不开的记录。
        if not directory.is_dir():
            continue
        entry["dir"] = str(directory)
        alive.append(entry)
    if limit is not None:
        return alive[:limit]
    return alive


def list_legacy_runs() -> list[dict]:
    """
    列出 v2 遗留目录（``generate/``、``edit/``），只读，不迁移。

    :return: 摘要字典列表（按时间倒序）
    """
    home = ensure_home()
    legacy: list[dict] = []
    for kind in ("generate", "edit"):
        base = home / kind
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if not d.is_dir():
                continue
            sess = d / "session.json"
            if not sess.exists():
                continue
            try:
                with open(sess, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            legacy.append({
                "run_id": d.name,
                "kind": f"legacy-{kind}",
                "status": payload.get("status", payload.get("state_machine", {}).get("current_state", "?")),
                "created_at": payload.get("created_at", ""),
                "prompt": (payload.get("prompt") or "")[:200],
                "inputs": len(payload.get("ref_images", payload.get("images", []))),
                "outputs": len(payload.get("outputs", [])),
                "dir": str(d),
            })
    legacy.sort(key=lambda e: (e.get("created_at") or "", e["run_id"]), reverse=True)
    return legacy


# ── 输入记录 ──────────────────────────────────────────────────────────────────


def record_input(directory: Path, ref: str) -> dict:
    """
    记录一张参考图：本地文件/data URI 复制进 ``inputs/``（内容寻址命名），URL 只记链接。

    在**发请求之前**调用，因此即使生成失败，输入也已经被保存下来可复用。

    三种输入形态都支持（与 :func:`seedream.generate.resolve_image_path` 的契约保持一致）：
    本地路径、``data:image/...;base64,...``、``http(s)://``。

    :param directory: run 目录
    :param ref: 用户传入的参考图
    :return: 输入记录项 {source, path, sha256, size, width, height, label}
    :raises FileNotFoundError: 本地路径不存在
    """
    if ref.startswith(("http://", "https://")):
        return {
            "source": ref,
            "path": None,
            "sha256": None,
            "size": None,
            "width": None,
            "height": None,
            "label": ref,
        }

    if ref.startswith("data:image/"):
        raw = data_url_to_bytes(ref)
        ext = guess_ext_from_data_url(ref)
        source = "(data URI)"
        name = f"data-uri{ext}"
    else:
        src = Path(ref).expanduser()
        if not src.is_file():
            raise FileNotFoundError(f"参考图不存在: {ref}")
        raw = src.read_bytes()
        ext = src.suffix.lower() or ".png"
        source = str(src.resolve())
        name = src.name

    digest = hashlib.sha256(raw).hexdigest()
    target = Path(directory) / "inputs" / f"{digest[:12]}{ext}"
    if not target.exists():
        target.write_bytes(raw)

    # 尺寸统一走 PIL（与 _execute 的校验同源），PIL 读不了时退回内置解析器
    size = probe_image_size(str(target)) or read_image_dimensions(raw)
    width, height = size
    return {
        "source": source,
        "path": str(target.resolve()),
        "sha256": digest,
        "size": len(raw),
        "width": width,
        "height": height,
        "label": f"{name} ({width}x{height}, {format_size(len(raw))})",
    }


def read_image_dimensions(data: bytes) -> tuple[int, int]:
    """
    从图片字节流头部解析宽高（PNG/JPEG/GIF/WebP/BMP，无第三方依赖）。

    :param data: 图片原始字节
    :return: (width, height)，无法识别时返回 (0, 0)
    """
    # 低于 8 字节无法匹配任何格式签名；各分支内部用 try/except 防御短数据
    if len(data) < 8:
        return (0, 0)

    # PNG: IHDR chunk 中 width/height 为 4 字节大端
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        try:
            return struct.unpack(">II", data[16:24])
        except struct.error:
            return (0, 0)

    # GIF: width/height 为 2 字节小端，偏移 6
    if data[:6] in (b"GIF87a", b"GIF89a"):
        try:
            return struct.unpack("<HH", data[6:10])
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
                width, height = struct.unpack("<HH", data[26:30])
                return (width & 0x3FFF, height & 0x3FFF)
            if chunk == b"VP8L" and len(data) >= 25:
                bits = int.from_bytes(data[21:25], "little")
                return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
            if chunk == b"VP8X" and len(data) >= 30:
                return (
                    int.from_bytes(data[24:27], "little") + 1,
                    int.from_bytes(data[27:30], "little") + 1,
                )
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
            # SOF 范围 0xC0~0xCF，排除 0xC4(DHT)/0xC8(JPG)/0xCC(DAC)
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return (width, height)
            if i + 4 <= len(data):
                seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg_len
            else:
                break
        return (0, 0)

    return (0, 0)


# ── 展示辅助 ──────────────────────────────────────────────────────────────────


def format_size(num_bytes: int | None) -> str:
    """把字节数格式化成人读字符串。"""
    if not num_bytes:
        return "?"
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / 1024 / 1024:.1f} MB"
    return f"{num_bytes / 1024:.0f} KB"


def guess_ext_from_data_url(data_url: str) -> str:
    """从 data URL 的 MIME 推断扩展名（data URI 作为参考图输入时用）。"""
    mime = data_url.split(",", 1)[0].split(":")[-1].split(";")[0]
    return mimetypes.guess_extension(mime or "image/png") or ".png"


def data_url_to_bytes(data_url: str) -> bytes:
    """解码 data URL 的 base64 载荷。"""
    return base64.b64decode(data_url.split(",", 1)[1])
