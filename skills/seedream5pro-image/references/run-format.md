# 生成记录（run）文件格式

一次生成 = 一个 run，落在**数据根目录**（`$SEEDREAM_HOME`，未设置时为当前工作目录下的 `.seedream/`）：

```
<数据根>/
├── index.jsonl                     # 一行一条任务摘要，append-only，ls 直接读它
├── runs/
│   └── 20261008-143022-a1b2/       # run id = YYYYMMDD-HHMMSS-<4位随机>
│       ├── run.json                # 唯一真相
│       ├── inputs/                 # 参考图副本（sha256 前 12 位命名）
│       └── outputs/                # 产物
└── mark/                           # mark 的标记预览图
```

> 目录名以日期时间开头，所以 `ls runs/` 自带时间排序，人和 agent 都不必解析 JSON 就能按时间找。

## run.json

```json
{
  "run_id": "20261008-143022-a1b2",
  "kind": "edit",
  "created_at": "2026-10-08T14:30:22",
  "finished_at": "2026-10-08T14:30:51",
  "status": "success",
  "error": null,
  "prompt": "将图1<bbox>300 1240 610 1590</bbox>区域内的纸杯替换成白色陶瓷马克杯，保持其他部分不变",
  "prompt_sent": "将图1<bbox>180 497 367 637</bbox>区域内的纸杯替换成白色陶瓷马克杯，保持其他部分不变",
  "replayed_from": "20261008-120015-9f3c",
  "params": {
    "size": "2K",
    "output_format": "png",
    "watermark": false,
    "optimize": "standard",
    "layer_decomposition": false,
    "background": "opaque"
  },
  "inputs": [
    {
      "source": "/home/me/photo.png",
      "path": "/.../runs/20261008-143022-a1b2/inputs/5be509078f9e.png",
      "sha256": "5be509078f9e...(64 位)",
      "size": 590399,
      "width": 1664,
      "height": 2496,
      "label": "photo.png (1664x2496, 577 KB)"
    }
  ],
  "outputs": [
    {
      "index": 1,
      "path": "/.../runs/20261008-143022-a1b2/outputs/3aa9a7aa925a.png",
      "size": "1664x2496",
      "output_format": "png",
      "z_index": null,
      "name": null,
      "description": null,
      "bbox_pixel": null,
      "prompt_fragment": null,
      "bbox_note": null
    }
  ],
  "updated_at": "2026-10-08T14:30:51"
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `kind` | `draw` / `edit` / `split` / `cutout`，与四个生成子命令一一对应 |
| `status` | `pending` → `running` → `success` / `error`（失败时 `error` 写错误信息） |
| `prompt` | CLI **实际接收**的提示词（含**原图像素**标签）—— **要复用/要粘贴就用这个** |
| `prompt_sent` | **实际发给接口**的提示词（坐标已换算）。**仅供审计，绝不要当输入** |
| `replayed_from` | 由 `seedream replay` 产生时，记录来源 run id |
| `params` | 本次请求的全部开关，复现所需信息齐全 |
| `inputs[]` | 参考图。**内容已复制到 `inputs/`**，`path` 可寻址、`sha256` 可校验 —— 原图移动或删除也能复现 |
| `outputs[]` | 产物。图层拆分时含 `z_index` / `name` / `description` / `bbox_base` / `bbox_base_size` / `bbox_pixel` / `prompt_fragment` |

### 两个关键设计

1. **参考图在发请求之前就落盘**：即使生成失败，输入依旧保存在 `inputs/`，可直接复现或改参数重跑。
2. **换算只发生一次，且只从像素版出发**：`replay` 发送的是 `prompt`（像素版），会**重新走一遍**
   校验换算；`prompt_sent` 只写不读。这样「把 0~999 的值再当像素换算一次」的路径根本不存在。

### 图层坐标的两套口径（别混用）

| 字段 | 坐标系 | 用途 |
|------|--------|------|
| `bbox_base` + `bbox_base_size` | **底图**坐标系（图层分辨率与底图一致） | 还原 / 重组图层 |
| `bbox_pixel` / `prompt_fragment` | **原输入图**坐标系（像素） | 写进 prompt 继续编辑 |

## index.jsonl

每完成一次任务追加一行（同一 run 出现多次时以最后一行为准），供 `seedream ls` 快速读取：

```json
{"run_id": "20261008-143022-a1b2", "kind": "edit", "status": "success",
 "created_at": "2026-10-08T14:30:22", "prompt": "将图1<bbox>180 497 367 637</bbox>…",
 "inputs": 1, "outputs": 1}
```

## 读记录的三种方式

```bash
seedream ls                      # 列出全部任务（最新在前）
seedream ls -n 5 --json          # 程序化取最近 5 条
seedream show last               # 最近一次的完整记录
seedream show <run_id> --json    # 交给程序处理
```

> ⚠️ 不要用 Read 工具直接读 `outputs/` 里的图片，也不要把 `run.json` 当二进制读 —— 用 `show --json`。

## v2 遗留目录

v2 的 `.seedream/generate/<id>/` 与 `.seedream/edit/<id>/`（`session.json` 结构）**不再被新命令使用，也不会被迁移**。
用 `seedream ls --all` 可以只读地列出它们。
