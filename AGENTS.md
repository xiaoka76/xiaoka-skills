# xiaoka-skills: AI Agent 交互指南

本文件为 AI 编码助手（如 Trae IDE Agent）提供与本项目交互的指引。

## 项目概述

`xiaoka-skills` 是一个开源 AI 技能合集，每个技能是一个独立的目录，包含技能清单 (`SKILL.md`)、脚本和知识库。项目旨在为 AI 开发环境注入特定的专业能力。

## 技能目录结构

每个技能遵循统一的结构：

```
skills/<skill-name>/
├── SKILL.md              # 技能清单（元数据、能力描述、调用方式）
├── pyproject.toml        # 包配置（支持 uv tool install）
├── src/                  # 可安装的 Python 包
│   └── <package>/
│       ├── cli.py        # CLI 入口
│       ├── generate.py   # 核心生成逻辑
│       ├── session.py    # Session 管理
│       ├── webui.py      # WebUI 后端
│       ├── config.py     # 配置常量
│       └── static/       # WebUI 前端文件
└── references/           # 知识库文档
    ├── README.md
    └── <category>/
        └── <template>.md
```

## 当前技能列表

| 技能名称 | 描述 | 入口 |
|----------|------|------|
| `byted-web-search` | 火山引擎豆包搜索（Custom/Global 双引擎，含图搜图） | `python3 scripts/web_search.py` |
| `seedream5pro-image` | Seedream 5.0 Pro 图像生成（文生图/图生图/交互编辑/图层拆分/透明背景/标记预览） | `seedream generate` · `seedream mark` |

## Agent 交互规则

### 1. 技能发现

当用户请求涉及以下领域时，Agent 应优先查找 `skills/` 下对应的技能目录：

- **联网搜索** → `skills/byted-web-search/`（默认 Custom 版；海外/图搜图用 `--engine global`）
- **图像生成** → `skills/seedream5pro-image/`
- 更多技能待添加

### 2. 技能清单 (`SKILL.md`)

每个技能的 `SKILL.md` 是 Agent 与该技能交互的入口文档，包含：
- 技能的能力描述和适用场景
- 调用方式（CLI 参数、Python API）
- 可用工具和参数说明
- 使用示例

Agent **必须**在执行任何技能操作前先读取 `SKILL.md`。

### 3. 知识库 (`references/`)

`references/` 目录包含技能所需的知识库文档。当前 `seedream5pro-image` 技能内置 **17 类共 91 个提示词模板**，另有 3 份方法论文档。Agent 在执行任务时应当：
- **先看 `prompt-guide.md`**（官方《Seedream 4.0-5.0 提示词指南》要点：5 条通用规则 + 各场景官方范例）
- 根据任务类型（如"学术配图"、"品牌海报"）选择对应分类的模板
- 参考模板中的 JSON 结构构建提示词
- 遵循 `prompt-writing.md` 中的模板方法论

### 4. Session 操作规范

Agent 在 WebUI 交互编辑流程中，应遵循以下规范：

- **查看会话状态**：使用 `seedream session summary` 命令查看会话摘要（含图片数量、标注、状态、完整 prompt 和 user_intent）
- **禁止直接读取 session.json**：图片以 base64 格式嵌入其中，文件通常有几 MB 甚至更大，不应使用 Read 工具直接读取
- **更新 prompt**：使用 `seedream session set-prompt` 命令更新
- **执行生成**：使用 `seedream generate --session` 从 session 执行生成

### 5. 提示词策略

Agent 需根据任务类型选择不同的提示词策略：

- **文生图（无参考图）**：prompt 必须覆盖主体、场景、风格、光影、构图、质量 6 个维度，确保足够丰富（80-150 字）
- **图生图/编辑（有参考图）**：prompt 应简洁明确，用"图1"/"图2"指代参考图，让模型从参考图中提取视觉特征。禁止编造参考图中不存在的细节
- **官方 5 条硬要求**（见 `references/prompt-guide.md`）：① 用**连贯自然语言**写主体+行为+环境，不要堆词块 ② 写明**用途/类型**（logo/海报/UI/实景图）③ 有风格需求用**精准风格词**或给参考图 ④ 要渲染的**文字放双引号** ⑤ 编辑时用**明确指令**并**显式声明保持不变的部分**，不用模糊代词
- **参考图生图只写两部分**：① 指明参考对象（人物形象/风格/材质）② 描述要生成的画面；多图输入明确写"图一/图二"各自承担什么
- ⚠️ 官方口径与本节"80-150 字"有轻微张力：官方强调**简洁精确优于堆砌华丽词汇**。两者可按任务取舍，但 5 条硬要求始终适用

### 6. 图层拆分 / 透明背景

- **图层拆分的 prompt 可省略**：不传 `-p` 时模型自动识别主要元素；也可用自然语言指定拆分对象，或用 `<bbox>` 像素坐标精准圈定区域
- **图层拆分约束**：仅 1 张输入图、仅 png/jpeg、size 仅档位（含 `auto`）、不支持自定义宽x高；任一图层失败即整体报错
- **图层拆分的产出**：1 张底图（`z_index=0`）+ 最多 16 个透明 PNG 图层，元数据记录 `z_index` / 图层名 / 描述 / `bounding_box`
- **透明背景**：`--background transparent`，仅图生图 + 1 张带透明通道的图，输出必须为 png

### 7. 坐标口径（全流程统一）

- **agent 只写原图像素**：直接在 prompt 里写 `<point>x y</point>` / `<bbox>x1 y1 x2 y2</bbox>`，坐标从 `mark` 网格上读数即可
- **`seedream generate` 负责校验 + 换算**：发出去之前自动把像素标签换成接口要求的 0~999；`mark` 与图层拆分给出的成品标签**也是像素**，可直接粘
- 校验清单：个数不对 / 非整数 / 超范围 / 多图未标归属 / 有标签却无参考图 → **报错中止**；写错标签名、框写反、逗号分隔 → **提示**并继续
- 对照表：`mark` 的输入/网格刻度/输出 `pixel` = 像素；`mark` 的 `fragments`、图层拆分的 `prompt_fragment` = **工具算好的 0~999，直接复制**；图层拆分的 `bounding_box.absolute` = 像素但属**底图坐标系**（换算须用底图尺寸，不是原图尺寸）
- ⚠️ 接口返回的 `bounding_box.normalized` 是 **0~1000**、而 prompt 标签要 **0~999**，两者不同源 → 技能**不输出**该字段
- **坐标只有一种形态：原图像素**。CLI 的任何输出都只有像素；坐标格式的转换完全在 `generate` 内部完成
- `--norm` 只是回灌逃生舱，不是常规路径

### 8. 标记预览（agent 侧交互式编辑）

- **编辑前先跑图层拆分**拿精确区域：手画框容易偏（实测第一次没框中、第二次底部仍在框外），而图层拆分会让模型自己圈定区域并给出**可直接用的 `<bbox>` 标签**
- **坐标一律按像素给**（`--point x,y` / `--box x1,y1,x2,y2`），`mark` 给出的成品标签也是像素，直接粘进 prompt 即可
- **先核对再提交**：先 `mark --image`（网格默认开，刻度在图片外留白区、值＝原图像素）读出坐标，再 `mark --box ...` 画框让有视觉的模型确认，偏了就改数字重跑
- ⚠️ **预览图不要当 `--images` 传**（带留白与刻度，污染输入）；要传标记图就用 `--plain`
- 用标记图做输入时（官方「任意标记」形式）**必须在 prompt 里写"移除所有标记"**，否则框可能被画进结果
- 方法优先级：① 纯提示词 → ③ 坐标/框选 → ④ 标记图；② 单点适合替换单个物体，修结构不如框选
- **分辨率默认自动**：按原始尺寸出图，仅当产物达到 2MB 预览上限时才自动降档；要强制原始尺寸加 `--max-edge 0`
- **参考图超限会被本地拦下**（像素/宽高比/宽高/30MB），并给出**可执行的缩放建议尺寸**；技能**不会自动改图**，缩不缩由用户决定

### 9. 编码规范

项目遵循 `.trae/rules/code-style.md` 中定义的 Python 编码规范，核心要点：
- 使用 `|` 运算符表示联合类型
- 集合抽象基类从 `collections.abc` 导入
- 无返回值函数必须标注 `-> None`
- 所有公共函数必须包含完整注释

## 运行技能

```bash
# 安装为全局工具（推荐）
cd skills/seedream5pro-image
uv tool install .
seedream generate -p "一只橘色虎斑猫，毛发蓬松，翡翠绿眼睛，坐在洒满阳光的木质窗台上，窗外是秋天枫叶，写实摄影风格，暖金色侧光，中景构图，超精细8K" --size 2K

# 或使用 uv run 直接运行
cd skills/seedream5pro-image
uv run seedream generate -p "一只橘色虎斑猫，毛发蓬松，翡翠绿眼睛，坐在洒满阳光的木质窗台上，窗外是秋天枫叶，写实摄影风格，暖金色侧光，中景构图，超精细8K" --size 2K

# 需要设置 API Key（仅支持环境变量，不读取 .env 文件）
export ARK_API_KEY="your-api-key"

# 可选：Base URL（默认按量后付费端点 https://ark.cn-beijing.volces.com/api/v3）
# agent plan 用 https://ark.cn-beijing.volces.com/api/plan/v3，Key 与端点必须匹配，否则 401
export ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"

# 启动交互编辑 WebUI（默认端口 8000）
seedream webui --preload /path/to/image.png
```

## 输出目录

图像生成结果按会话类型统一保存到 `.seedream/` 目录：

- 文生图/图生图/图层拆分 → `.seedream/generate/<session_id>/output/`
- 交互编辑 → `.seedream/edit/<session_id>/output/`
- 图层拆分产出：底图 `<uuid>-L00.<ext>`、图层 `<uuid>-L<nn>-<图层名>.png`（图层恒为 png）

该目录已被加入 `.gitignore`，不会提交到版本控制。

## 添加新技能

要添加新技能，请创建以下目录结构：

```
skills/<new-skill>/
├── SKILL.md              # 必需：技能清单
├── pyproject.toml        # 可选：包配置
├── src/                  # 可选：Python 包
└── references/           # 可选：知识库文档
```

`SKILL.md` 必须包含：名称、描述、版本、标签、核心能力说明。