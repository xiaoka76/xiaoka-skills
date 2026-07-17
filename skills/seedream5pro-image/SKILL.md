---
name: seedream5pro-image
description: Seedream 5.0 Pro 专用图像生成技能。文生图 / 图生图 / 交互编辑（<point>/<bbox> 坐标精确定位），自动保存到本地。内置 17 类提示词模板。使用该技能时：用户想画图、生成图片、改图、编辑图片、做海报/UI/产品图/插画/角色/地图/信息图/分镜等任何视觉内容，或需要高质量的 AI 图像生成能力。
license: MIT
tags: ["image-generation", "seedream-5.0-pro", "seedream", "volcengine", "text-to-image", "image-to-image", "interactive-edit", "local-save"]
version: 2.1.1
---

# Seedream 5.0 Pro 图像生成

## 概览

专为 **doubao-seedream-5-0-pro-260628** 打造的独立图像生成技能。内置 17 类提示词模板，支持文生图/图生图/交互编辑，自动保存到本地并生成会话记录。

**模型 ID**: `doubao-seedream-5-0-pro-260628`

### 能力支持

| 能力 | 支持 |
|------|------|
| 文生图 | ✅ |
| 单/多图生图 | ✅（最多 10 张参考图） |
| 交互编辑（point/bbox） | ✅ |
| 原生多语种文字渲染（14 种语言） | ✅ |
| 本地自动保存（无 403） | ✅ |
| 提示词优化（standard / fast） | ✅ |
| 文生组图 / 批量生成 | ❌ |
| 流式输出 | ❌ |
| 联网搜索 | ❌ |

### 分辨率支持

- 档位：`1K` / `2K`（默认 2K）
- 自定义像素：`宽x高`（总像素 921600~4624220，宽高比 1/16~16）
- 或用自然语言描述宽高比（如 `--size "2K"` 配合 prompt 写 "宽高比 16:9"）

使用档位模式时，各档位在不同宽高比下的实际像素值如下：

| 分辨率 | 宽高比 | 宽高像素值 |
|--------|--------|-----------|
| 1K | 1:1 | 1024x1024 |
| | 4:3 | 1152x864 |
| | 3:4 | 864x1152 |
| | 16:9 | 1424x800 |
| | 9:16 | 800x1424 |
| | 3:2 | 1248x832 |
| | 2:3 | 832x1248 |
| | 21:9 | 1568x672 |
| 2K | 1:1 | 2048x2048 |
| | 4:3 | 2368x1776 |
| | 3:4 | 1776x2368 |
| | 16:9 | 2816x1584 |
| | 9:16 | 1584x2816 |
| | 3:2 | 2496x1664 |
| | 2:3 | 1664x2496 |
| | 21:9 | 3136x1344 |

自定义像素注意事项：
- 总像素范围：`[1280x720]`(921600) ~ `[2048x2048x1.1025]`(4624220)
- 宽高比范围：`[1/16, 16]`
- 两个条件需同时满足

## Agent 使用规范（强制执行）

> **重要：seedream 5.0 Pro 是提示词驱动模型，提示词越丰富、越详细，生成效果越好。简短的提示词会导致画面空洞、细节缺失。Agent 必须严格遵守以下规则。**

### 1. 禁止自行编写简短提示词

**任何情况下，Agent 不得自行编写简短的自然语言提示词直接传给模型。** 包括但不限于：
- 禁止：用户说"画一只猫" → 直接写 `seedream generate -p "一只可爱的猫"`
- 禁止：用户说"做个海报" → 直接写 `seedream generate -p "一张科技风海报"`

### 2. 强制查阅模板（必须执行）

**每次生成任务，Agent 必须执行以下步骤：**

```
步骤 1 — 匹配模板
  → 根据用户意图，在 references/ 目录下找到最匹配的模板文件
  → 17 个分类目录：ui-mockups, product-visuals, portraits-and-characters,
     poster-and-campaigns, scenes-and-illustrations, maps, infographics,
     slides-and-visual-docs, storyboards-and-sequences, grids-and-collages,
     branding-and-packaging, avatars-and-profile, editing-workflows,
     assets-and-props, academic-figures, technical-diagrams,
     typography-and-text-layout

步骤 2 — 读取模板
  → 打开模板文件，理解其 JSON 结构和参数策略
  → 重点关注：主模板 JSON、参数策略（must-ask/defaultable/randomizable）、constraints

步骤 3 — 收集缺失信息
  → 按模板中「缺失信息优先提问顺序」向用户提问
  → 每次最多 2-3 个问题
  → 除非用户明确表示"使用默认值"或"你自己决定"，否则缺失信息必须向用户确认

步骤 4 — 展开 prompt
  → 将模板 JSON 展开为自然语言 prompt
  → 必须包含：主体描述、场景/背景、风格/流派、光影/氛围、构图/视角、质量词
  → 展开后的 prompt 应至少 80-150 字，确保足够丰富

步骤 5 — 展示确认（可选）
  → 可将展开后的完整 prompt 展示给用户确认
  → 简单任务可跳过此步骤直接执行 seedream generate
```

### 3. Prompt 丰富度底线

展开后的 prompt 必须覆盖以下维度（缺一不可）：

| 维度 | 说明 | 示例 |
|------|------|------|
| 主体描述 | 核心对象的外观、材质、姿态、表情 | "一只橘色虎斑猫，毛发蓬松，翡翠绿眼睛" |
| 场景/背景 | 环境、地点、时间 | "坐在洒满阳光的木质窗台上，窗外是秋天的枫叶" |
| 风格/流派 | 艺术风格、视觉流派 | "写实摄影风格，浅景深，85mm 镜头感" |
| 光影/氛围 | 光源方向、色温、氛围感 | "暖金色侧光从左侧窗户照入，营造温馨午后氛围" |
| 构图/视角 | 画面构图、视角 | "中景构图，猫位于画面右侧三分线，眼睛看向镜头" |
| 质量词 | 分辨率和细节要求 | "超精细细节，8K 分辨率，电影级质感" |

### 4. 找不到匹配模板时

如果 `references/` 下没有完全匹配的模板，Agent 必须：
1. 选择最接近的模板作为参考骨架
2. 仍然展开为丰富 prompt（覆盖上述 6 个维度）
3. 不得退化为简短的一句话描述

### 5. 简单任务也不能跳过

即使用户需求看起来很简单（如"画一只猫"），Agent 也**必须**：
- 查阅 `references/prompt-writing.md` 了解方法论
- 匹配最接近的模板（如 `portraits-and-characters/` 或 `scenes-and-illustrations/`）
- 展开为丰富 prompt，主动补充场景、光影、风格等细节
- 可向用户简要确认补充的细节是否合适

## 安装

```bash
# 安装为全局工具（推荐）
cd skills/seedream5pro-image
uv tool install .
seedream generate --help

# 或使用 uv run 直接运行（其次）
cd skills/seedream5pro-image
uv run seedream generate --help

# 或安装依赖后在项目中使用
cd skills/seedream5pro-image
pip install -e .
seedream generate --help
```

### 环境变量

```bash
export ARK_API_KEY="your-api-key"
```

API Key 仅通过环境变量配置（支持 `ARK_API_KEY` / `MODEL_IMAGE_API_KEY` / `MODEL_AGENT_API_KEY`，按优先级读取）。

## 用法

### 文生图

```bash
seedream generate -p "一只可爱的猫坐在窗台上，阳光洒进来" --size 2K
```

### 图生图（URL 或本地路径）

```bash
# 网络 URL
seedream generate -p "把这张照片转换成动漫风格" --images "https://example.com/photo.jpg" --size 2K

# 本地路径（自动编码为 Base64）
seedream generate -p "把这张照片转换成动漫风格" --images "./photo.jpg" --size 2K
```

### 多图融合

```bash
seedream generate -p "将图1的人物和图2的背景融合在一起" --images "https://example.com/person.jpg" --images "https://example.com/bg.jpg"
```

`--images` 可多次指定，最多 10 张参考图。

### 交互编辑

交互编辑通过 WebUI 完成，支持点选/框选标注，由 agent 配合模板润色 prompt 后执行生成：

```bash
# 启动 WebUI（默认端口 8090）
seedream webui

# 可选：预加载图片
seedream webui --preload /path/to/image.png

# 可选：指定端口号
seedream webui --port 8090
```

启动后在浏览器中操作：

1. 上传图片或查看预加载的图片
2. 选择「点选」或「框选」模式标注编辑区域
3. 在编辑意图框中输入指令（如"把这个狗换成猫"）
4. 点击「保存」后，agent 读取 session 润色 prompt 并执行生成

详细工作流见下方「交互编辑工作流（WebUI）」章节。

### 跳过提示词优化

```bash
seedream generate -p "..." --optimize fast
```

`fast` 模式表示跳过云端提示词优化，直接使用原始 prompt 生成，耗时更短但效果略低于 `standard` 模式。

### 输出目录

生成结果统一保存在 `.seedream/` 目录下，按会话类型和 ID 自动组织：

```
.seedream/
├── generate/<session_id>/      # 文生图/图生图
│   ├── session.json
│   └── output/...
└── edit/<session_id>/          # 交互编辑
    ├── session.json
    └── output/...
```

## 命令行参数

| 参数 | 简写 | 说明 | 默认 |
|------|------|------|------|
| `--prompt` | `-p` | 提示词 / 编辑指令（与 `--session` 互斥） | - |
| `--session` | `-S` | 从 session.json 读取 prompt 和图片路径 | - |
| `--images` | - | 参考图 URL 或本地路径（可多次指定，最多 10 张） | - |
| `--size` | `-s` | 分辨率：`1K` / `2K` 或自定义宽x高 | `2K` |
| `--output-format` | - | 输出格式：`png` / `jpeg` | `png` |
| `--watermark` | - | 启用水印 | 关闭 |
| `--optimize` | - | 提示词优化：`standard` / `fast` | `standard` |
| `--timeout` | `-t` | API 超时（秒） | `300` |

## 交互编辑

### 坐标系统

归一化坐标范围 **0~999**，左上角 `0,0`，右下角 `999,999`。

**转换公式**：
```
x_norm = round(x_px / 图片宽度 * 1000)
y_norm = round(y_px / 图片高度 * 1000)
```

### 编辑场景

| 场景 | Prompt 写法 |
|------|------------|
| 点选附近对象 | `把图1<point>520 460</point>位置换成皇冠` |
| 框选区域替换 | `把图1<bbox>120 180 640 760</bbox>区域替换成花园` |
| 跨图编辑 | `将图1<bbox>179 283 796 986</bbox>的主体放到图2<bbox>118 331 933 871</bbox>位置` |
| 多主体指定 | `把图1<bbox>120 180 640 760</bbox>区域内的左侧人物换成机器人` |
| 部分保持不变 | `把图1<bbox>120 180 640 760</bbox>区域替换成花园，图1<bbox>700 120 920 360</bbox>区域保持不变` |

## 交互编辑工作流（WebUI）

当用户需要对已有图片做局部修改时，可以使用交互编辑 WebUI 完成点选/框选标注，再由 agent 结合模板完善 prompt 后执行生成。

### 完整流程

1. Agent 启动 `seedream webui`，生成会话 ID，打开浏览器
2. 用户在 WebUI 中上传图片、标注编辑区域、输入编辑意图、点击保存
3. Agent 读取 session.json，匹配编辑模板，润色 prompt 后执行 `seedream generate --session`

### 启动 WebUI

```bash
seedream webui                          # 基本启动（默认 127.0.0.1:8090）
seedream webui --port 8090              # 指定端口
seedream webui --preload /path/to/img.png  # 预加载图片
seedream webui --host 0.0.0.0           # 允许局域网访问（谨慎使用）
```

> 默认绑定 `127.0.0.1`，仅本机可访问。如需局域网访问，显式传入 `--host 0.0.0.0`。

### Session 状态机

Edit session: `created → editing → saved`（保存后可回到 editing）。Generate session: `pending → running → success/error`。

### Session 文件

Edit session 和 Generate session 的完整 JSON 格式见 [references/session-format.md](references/session-format.md)。

### Agent 操作 Session

```bash
seedream session summary .seedream/edit/{uuid}/session.json  # 查看摘要
seedream session get-prompt .seedream/edit/{uuid}/session.json  # 获取 prompt
seedream session set-prompt .seedream/edit/{uuid}/session.json --prompt "..."  # 更新 prompt
seedream generate --session .seedream/edit/{uuid}/session.json  # 从 session 生成
```

### 编辑模板匹配

agent 读取 session 后，根据 `user_intent` 的关键词自动匹配编辑模板：

| 用户意图关键词 | 匹配模板 |
|---------------|---------|
| "换成"/"替换为"/"改成" | `references/editing-workflows/local-object-replacement.md` |
| "去掉"/"移除"/"删除"/"去除" | `references/editing-workflows/object-removal.md` |
| "换背景" | `references/editing-workflows/background-replacement.md` |
| "换发型"/"换衣服"/"化妆" | `references/editing-workflows/portrait-local-edit.md` |
| "精修"/"质感"/"锐化" | `references/editing-workflows/product-retouching.md` |

支持多目标组合，如"去掉A点的人 + 替换B框的桌子"。

## 提示词模板（强制使用）

> **见上方「Agent 使用规范」章节。每次生成任务必须查阅模板，禁止跳过。**

本技能内置 17 类共 91 个提示词模板，位于 `references/` 目录下。模板采用 JSON 结构化设计，覆盖主体、场景、风格、光影、构图、质量等维度，确保 prompt 足够丰富。

### 模板目录

```
references/
  prompt-writing.md              ← 模板方法论总规范（必读）
  ui-mockups/                    ← UI 样机（直播、聊天、社交）
  product-visuals/               ← 产品视觉（爆炸图、白底图、影棚图）
  portraits-and-characters/      ← 人物/角色肖像
  poster-and-campaigns/          ← 海报/品牌主视觉
  scenes-and-illustrations/      ← 场景插画
  maps/                          ← 地图类视觉
  infographics/                  ← 信息图
  slides-and-visual-docs/        ← 幻灯片/讲解图
  storyboards-and-sequences/     ← 分镜/漫画/流程板
  grids-and-collages/            ← 网格/拼贴
  branding-and-packaging/        ← 品牌/包装
  avatars-and-profile/           ← 头像/人设
  editing-workflows/             ← 编辑工作流
  assets-and-props/              ← 素材/道具
  academic-figures/              ← 学术配图
  technical-diagrams/            ← 技术架构图
  typography-and-text-layout/    ← 字体/版式
```

### 如何使用模板

**五步法（对应 Agent 使用规范中的步骤 1-5）**：

1. **匹配模板**：根据任务类型找到对应目录，打开具体模板文件
2. **读取模板**：理解 JSON 结构、参数策略（must-ask/defaultable/randomizable）和 constraints
3. **收集信息**：按模板中「缺失信息优先提问顺序」向用户提问核心参数
4. **展开 prompt**：将 JSON 展开为丰富自然语言 prompt，覆盖 6 个必要维度
5. **展示确认 → 执行**：用户确认后调用 `seedream generate`

模板中的 `{argument name="..." default="..."}` 是参数占位符：
- **核心参数（must-ask）**：缺失必问用户，如主体是谁、商品是什么
- **可默认参数（defaultable）**：有合理默认值，直接使用无需问
- **可随机参数（randomizable）**：自动补全，如聊天消息、路人昵称

### 示例

以 `ui-mockups/live-commerce-ui.md` 为例，模板 JSON 长这样：

```json
{
  "type": "电商直播 UI 样机",
  "goal": "生成一张高仿真的直播带货截图",
  "subject": {
    "source_mode": "celebrity-name",
    "celebrity_name": "Elon Musk",
    "description": "面带微笑，半身肖像"
  },
  "scene": { "background_style": "科技公司发布会后台" },
  "ui_overlay": { "platform_style": "通用中文直播带货平台 UI" },
  "style": { "visual_target": "逼真的直播截图样机" }
}
```

展开后变成丰富 prompt（注意：这不是简短的一句话，而是覆盖所有维度）：

```
生成一张高仿真的直播带货截图风格视觉图，主播是Elon Musk面带微笑的半身肖像，
背景为科技公司发布会后台，叠加通用中文直播带货平台UI，逼真的直播截图样机...
```

然后执行：

```bash
seedream generate -p "生成一张高仿真的直播带货截图风格视觉图..." --size 2K
```

## 提示词技巧

> **提示词越丰富，生成效果越好。禁止使用简短的一句话描述。每条 prompt 必须覆盖 6 个维度。**

### 基本结构

```
[主体描述] + [场景/背景] + [风格/流派] + [光影/氛围] + [构图/视角] + [质量/分辨率]
```

### 进阶结构

```
[主体描述], [创意风格], [独特视角/构图], [特殊光影/氛围], [强调创意表达]
```

### 中文提示词

5.0 Pro 对中文支持良好，直接写中文即可。以下是**合格 prompt 示例**（覆盖所有维度，约 80 字）：

```
"黄昏时分的赛博朋克茶馆，雨水顺着发光的霓虹窗户流下。屋内，一位银发少女坐在窗边，捧着一杯热茶。窗外，全息龙形灯笼在雨街上漂浮。细节丰富，电影级光影，超精细8K。"
```

### 不合格 prompt 示例（禁止使用）

以下是**简短 prompt 的典型错误**，Agent 不得生成此类 prompt：

| 错误示例 | 问题 |
|----------|------|
| `"一只猫"` | 只有主体，无场景、风格、光影、构图、质量词 |
| `"美丽的风景"` | 过于笼统，无任何具体细节 |
| `"科技风海报"` | 只有风格意向，无主体、场景、构图 |
| `"一个穿西装的商务人士"` | 缺少场景、光影、风格、构图描述 |

## 输出

### 目录结构

生成结果按会话类型组织，统一保存在 `.seedream/` 目录下：

```
.seedream/
├── edit/<session_id>/          # 交互编辑会话（WebUI）
│   ├── session.json            # 编辑状态、标注、图片(base64)
│   └── output/                 # 生成输出
│       ├── <uuid>.png/jpg          # 生成图片
│       ├── <uuid>.md               # 元数据
│       ├── <hash>.png/jpg          # 参考图（哈希值命名）
│       └── ...
└── generate/<session_id>/      # 普通生成会话（CLI 文生图/图生图）
    ├── session.json            # 生成状态、参数、输出记录
    └── output/
        ├── <uuid>.png/jpg
        ├── <uuid>.md
        └── ...
```

## 常见问题

### Q: 图片保存在哪里？
A: `.seedream/generate/<session_id>/output/`（文生图/图生图）或 `.seedream/edit/<session_id>/output/`（交互编辑）。

### Q: 最多能传多少张参考图？
A: 最多 10 张。

### Q: 提示词模板怎么用？
A: 参考上方「提示词模板」章节：匹配模板 → 读取模板 → 收集信息 → 展开 prompt → 执行。
