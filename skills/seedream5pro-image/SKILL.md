---
name: seedream5pro-image
description: Seedream 5.0 Pro 专用图像生成技能。文生图 / 图生图 / 交互编辑（<point>/<bbox> 坐标精确定位），自动保存到本地。内置 17 类提示词模板。使用该技能时：用户想画图、生成图片、改图、编辑图片、做海报/UI/产品图/插画/角色/地图/信息图/分镜等任何视觉内容，或需要高质量的 AI 图像生成能力。
license: Apache-2.0
tags: ["image-generation", "seedream-5.0-pro", "seedream", "volcengine", "text-to-image", "image-to-image", "interactive-edit", "local-save"]
version: 2.0.0
---

# Seedream 5.0 Pro 图像生成

## 概览

专为 **doubao-seedream-5-0-pro-260628** 打造的独立图像生成技能。无外部依赖、无版本选择、无冗余参数——只做一件事：高质量图像生成。

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

## 安装

```bash
# 安装依赖
pip install httpx

# 安装为全局工具
uv tool install .

# 或直接在项目中使用
cd skills/seedream5pro-image
uv run seedream generate --help
```

### 环境变量

```bash
export ARK_API_KEY="your-api-key"
# 或创建 .env 文件（自动加载）
# ARK_API_KEY=your-api-key
```

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

### 交互编辑 - 框选替换

```bash
seedream generate -p "把图1<bbox>179 283 796 986</bbox>的主体放到图2<bbox>118 331 933 871</bbox>位置" --images "https://example.com/obj.jpg" --images "https://example.com/target.jpg"
```

### 交互编辑 - 点选

```bash
seedream generate -p "把图1<point>520 460</point>位置换成皇冠" --images "https://example.com/img.jpg"
```

### 交互编辑 - 任意标记

```bash
seedream generate -p "根据手绘草图对图像进行编辑。在左下角标记区域添加一叠杂志。移除所有草图线条。保持构图不变。" --images "https://example.com/marked.png"
```

### 快速模式

```bash
seedream generate -p "..." --optimize fast
```

### PNG 输出

```bash
seedream generate -p "..." --output-format png
```

### 自定义保存目录

```bash
seedream generate -p "..." --output-dir ./my-images
```

## 命令行参数

| 参数 | 简写 | 说明 | 默认 |
|------|------|------|------|
| `--prompt` | `-p` | 提示词 / 编辑指令（与 `--session` 互斥） | - |
| `--session` | `-S` | 从 session.json 读取 prompt 和图片路径 | - |
| `--images` | - | 参考图 URL 或本地路径（可多次指定，最多 10 张） | - |
| `--size` | `-s` | 分辨率档位或宽x高 | `2K` |
| `--output-format` | - | 输出格式：`png` / `jpeg` | `jpeg` |
| `--output-dir` | `-o` | 图片保存目录 | `.seedream` |
| `--watermark` | - | 启用水印 | 关闭 |
| `--optimize` | - | 提示词优化：`standard` / `fast` | `standard` |
| `--timeout` | `-t` | API 超时（秒） | `300` |

## Python API

```python
from seedream.generate import single_generate

result = single_generate({
    "prompt": "一只可爱的猫坐在窗台上",
    "size": "2K",
    "output_format": "png",
    "watermark": False,
})
print(f"图片已保存: {result['image_path']}")
print(f"元数据: {result['metadata_path']}")
```

### 坐标转换工具

```python
from seedream.generate import normalize_coords

# 点选：像素坐标 (520, 460) → 归一化坐标
x, y = normalize_coords(1024, 768, 520, 460)
prompt = f"把图1<point>{x} {y}</point>位置换成皇冠"

# 框选：像素坐标 (120, 180, 640, 760) → 归一化坐标
x1, y1, x2, y2 = normalize_coords(1920, 1080, 120, 180, 640, 760)
prompt = f"把图1<bbox>{x1} {y1} {x2} {y2}</bbox>区域替换成花园"
```

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

```
用户：修改这张图片（或类似语义）
  → agent 启动 seedream webui
    → 生成会话 ID，创建 session.json
    → 输出 session 文件路径
    → 打开浏览器访问 WebUI
  → 用户在 WebUI 中：
    1. 上传图片（或预加载已生成的图片）
    2. 选择「点选」或「框选」模式，在图片上标注编辑区域
    3. 在「编辑意图」框中输入模糊指令（如"把这个狗换成猫"）
    4. 点击「保存」
  → 回到 agent，用户说"查看我的标注"
    → agent 读取 session.json
    → 分析用户意图，匹配 references/editing-workflows/ 下的模板
    → 润色 prompt，展示给用户确认
  → 用户确认后
    → agent 调用 seedream generate --session <session-path> 执行生成
```

### 启动 WebUI

```bash
# 基本启动
seedream webui

# 指定端口
seedream webui --port 8090

# 预加载图片（可多次指定）
seedream webui --preload /path/to/image1.png --preload /path/to/image2.jpg
```

启动后命令行会输出：
```
  Seedream 5.0 Pro 交互编辑 WebUI
  ─────────────────────────────────────
  会话 ID: a1b2c3d4e5f6
  Session 文件: .seedream/edit/a1b2c3d4e5f6/session.json
  ─────────────────────────────────────
  服务地址: http://localhost:8090
  远程访问: http://<your-ip>:8090
```

### Session 状态机

WebUI 的 session 采用状态机设计，跟踪编辑会话的生命周期：

| 状态 | 说明 |
|------|------|
| `created` | 会话已创建，无图片 |
| `editing` | 已上传图片或添加标注，正在编辑中 |
| `saved` | 用户已保存编辑意图 |

状态迁移：`created → editing → saved`，保存后仍可回到 `editing` 继续编辑。

### Session 文件

WebUI 保存的数据存储在 `.seedream/edit/{session_id}/session.json`，图片以 base64 格式直接嵌入 JSON，不再保存独立图片文件：

```json
{
  "session_id": "a1b2c3d4e5f6",
  "state_machine": {
    "current_state": "saved",
    "history": [
      {"state": "created", "timestamp": "2024-01-01T00:00:00", "event": "session initialized"},
      {"state": "editing", "timestamp": "2024-01-01T00:01:00", "event": "image uploaded"},
      {"state": "saved", "timestamp": "2024-01-01T00:02:00", "event": "user saved intent"}
    ]
  },
  "images": [
    {
      "inputLabel": "图1",
      "name": "photo.jpg",
      "dataUrl": "data:image/jpeg;base64,/9j/4AAQ...",
      "naturalWidth": 1920,
      "naturalHeight": 1080
    }
  ],
  "annotations": [
    {
      "id": 1,
      "type": "bbox",
      "image_label": "图1",
      "normalized_coords": [179, 283, 796, 986],
      "token": "图1<bbox>179 283 796 986</bbox>"
    }
  ],
  "prompt": "把 图1<bbox>179 283 796 986</bbox> 的狗换成猫",
  "user_intent": "把这个狗换成更好看的猫"
}
```

### Agent 读取 Session

使用 `seedream session` 子命令让 agent 方便地读取和修改 session：

```bash
# 查看 session 摘要（含状态机状态、图片、标注、prompt）
seedream session summary .seedream/edit/{uuid}/session.json

# 获取当前 prompt
seedream session get-prompt .seedream/edit/{uuid}/session.json

# 更新 prompt（agent 润色后）
seedream session set-prompt .seedream/edit/{uuid}/session.json --prompt "以 REFERENCE_0 为基础，将图1<bbox>179 283 796 986</bbox>中的狗替换为一只橘猫..."

# 列出图片信息
seedream session list-images .seedream/edit/{uuid}/session.json
```

### 从 Session 生成

```bash
# 直接使用 session.json 执行生成
seedream generate --session .seedream/edit/{uuid}/session.json

# 或指定额外参数
seedream generate --session .seedream/edit/{uuid}/session.json --size 2K --output-format png
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

## 提示词模板

本技能内置 17 类共 91 个提示词模板，位于 `references/` 目录下。

### 模板目录

```
references/
  prompt-writing.md              ← 模板方法论总规范
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

**三步法**：

1. **找分类**：根据任务类型找到对应目录，打开具体模板文件
2. **填参数**：模板中的 `{argument name="..." default="..."}` 是参数占位符
   - **核心参数**（缺失必问用户）：如主体是谁、商品是什么
   - **可默认参数**（有合理默认值）：如灯光、背景色
   - **可随机参数**（自动补全）：如聊天消息、路人昵称
3. **展开 → 执行**：把 JSON 展开成自然语言 prompt，传给 `seedream generate`

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

展开后变成：

```
生成一张高仿真的直播带货截图风格视觉图，主播是Elon Musk面带微笑的半身肖像，背景为科技公司发布会后台，叠加通用中文直播带货平台UI，逼真的直播截图样机...
```

然后执行：

```bash
seedream generate -p "生成一张高仿真的直播带货截图风格视觉图..." --size 2K
```

## 提示词技巧

### 基本结构

```
[主体描述] + [风格/流派] + [光影/氛围] + [质量/分辨率]
```

### 进阶结构

```
[主体描述], [创意风格], [独特视角/构图], [特殊光影/氛围], [强调创意表达]
```

### 中文提示词

5.0 Pro 对中文支持良好，直接写中文即可：

```
"黄昏时分的赛博朋克茶馆，雨水顺着发光的霓虹窗户流下。屋内，一位银发少女坐在窗边，捧着一杯热茶。窗外，全息龙形灯笼在雨街上漂浮。细节丰富，电影级光影，超精细8K。"
```

## 输出

### 返回格式

```json
{
  "status": "success",
  "image_path": "/app/workspace/.seedream/a1b2c3d4e5f6.jpg",
  "metadata_path": "/app/workspace/.seedream/a1b2c3d4e5f6.md",
  "model": "doubao-seedream-5-0-pro-260628",
  "output_dir": "/app/workspace/.seedream",
  "error": null
}
```

### 文件命名规则

- 图片: `{uuid前12位}.{扩展名}`（如 `a1b2c3d4e5f6.jpg`）
- 元数据: `{uuid前12位}.md`（如 `a1b2c3d4e5f6.md`），包含提示词、模型、尺寸、参数等完整信息



## 常见问题

### Q: 图片保存在哪里？
A: 默认 `.seedream/`，可通过 `--output-dir` 自定义。

### Q: 为什么没有 `--group` 参数？
A: 5.0 Pro 不支持批量生成（文生组图）。如需该功能，请使用 5.0 lite。

### Q: 最多能传多少张参考图？
A: 最多 10 张。

### Q: 提示词模板怎么用？
A: 参考上方「提示词模板」章节。三步法：找分类 → 填参数 → 展开执行。



## 许可证

Apache License 2.0