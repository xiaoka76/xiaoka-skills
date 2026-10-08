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
│       ├── cli.py        # CLI 入口（子命令按“意图”划分，一个命令一件事）
│       ├── generate.py   # 核心逻辑
│       ├── config.py     # 配置常量
│       └── <module>.py   # 领域模块
└── references/           # 知识库文档
    ├── README.md
    └── <category>/
        └── <template>.md
```

## 当前技能列表

| 技能名称 | 描述 | 入口 |
|----------|------|------|
| `byted-web-search` | 火山引擎豆包搜索（Custom/Global 双引擎，含图搜图） | `python3 scripts/web_search.py` |
| `seedream-image` | Seedream 5.0 Pro 图像生成（文生图/图生图/图层拆分/透明背景/标记预览/生成记录） | `seedream draw` · `edit` · `split` · `cutout` · `mark` · `ls` · `show` · `replay` |

## Agent 交互规则

### 1. 技能发现

当用户请求涉及以下领域时，Agent 应优先查找 `skills/` 下对应的技能目录：

- **联网搜索** → `skills/byted-web-search/`（默认 Custom 版；海外/图搜图用 `--engine global`）
- **图像生成** → `skills/seedream-image/`
- 更多技能待添加

### 2. 技能清单 (`SKILL.md`)

每个技能的 `SKILL.md` 是 Agent 与该技能交互的入口文档，包含：
- 技能的能力描述和适用场景
- 调用方式（CLI 参数、Python API）
- 可用工具和参数说明
- 使用示例

Agent **必须**在执行任何技能操作前先读取 `SKILL.md`。

### 3. 知识库 (`references/`)

`references/` 目录包含技能所需的知识库文档。当前 `seedream-image` 技能内置 **17 类共 93 个提示词模板**，另有 4 份方法论文档。Agent 在执行任务时应当：
- **先看 `prompt-guide.md`**（官方《Seedream 4.0-5.0 提示词指南》要点：5 条通用规则 + 各场景官方范例）
- 根据任务类型（如"学术配图"、"品牌海报"）选择对应分类的模板
- 参考模板中的 JSON 结构构建提示词
- 遵循 `prompt-writing.md` 中的模板方法论

### 4. 生成记录规范

每次生成都会自动落地一条完整记录（提示词 / 参考图副本 / 参数 / 产物），Agent 应遵循：

- **查历史**：`seedream ls`（加 `--json` 便于程序化处理）
- **看详情**：`seedream show last` 或 `seedream show <run_id>`；要结构化数据用 `--json`
- **复用它人的图**：用户说"改上次那张图"时，先 `seedream show` 看清原提示词与输入，
  再用 `seedream edit "..." --images <该任务 inputs/ 里的副本>` 继续加工
- **复现**：`seedream replay <run_id>` **默认只预演、不消耗额度**，确认后加 `--run` 才真跑
- **不要直接 Read 产物或记录文件**：产物是二进制图片；记录信息一律走 `show --json` / `ls --json`
- **失败的任务同样保留输入**（`status=error`），可直接复现或改参数重跑
- 完整字段见 `skills/seedream-image/references/run-format.md`

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
- **图层拆分的产出**：1 张底图（`z_index=0`）+ 最多 16 个透明 PNG 图层；`run.json` 记录 `z_index` / 图层名 / 描述，坐标分两套：`bbox_base`+`bbox_base_size`（底图坐标系，**还原/重组用这个**）与 `bbox_pixel`+`prompt_fragment`（原图像素，**写 prompt 用这个**）
- **透明背景**：用 `seedream cutout <图>`，仅图生图 + 1 张带透明通道的图，输出**恒为 png**（不提供格式选项）

### 7. 坐标口径（全流程统一）

- **agent 只写原图像素**：直接在 prompt 里写 `<point>x y</point>` / `<bbox>x1 y1 x2 y2</bbox>`，坐标从 `mark` 网格上读数即可
- **CLI 负责校验 + 换算**：`seedream edit` / `seedream split` 在发出去之前自动把像素标签换成接口要求的 0~999；`mark` 与图层拆分给出的成品标签**也是像素**，可直接粘
- 校验清单：个数不对 / 非整数 / 超范围 / 多图未标归属 / 有标签却无参考图 → **报错中止**；写错标签名、框写反、逗号分隔 → **提示**并继续
- 对照表：`mark` 的输入/网格刻度/输出 `pixel` = 像素；`mark` 的 `fragments`、图层拆分的 `prompt_fragment`、`run.json.prompt` = **像素，可直接复制复用**；图层拆分的 `bbox_base` = 像素但属**底图坐标系**（配 `bbox_base_size` 使用）
- ⚠️ 接口返回的 `bounding_box.normalized` 是 **0~1000**、而 prompt 标签要 **0~999**，两者不同源 → 技能**不输出**该字段；`run.json.prompt_sent` 是唯一的换算后记录，**只写不读**
- **坐标只有一种形态：原图像素**。CLI 的对外输出只有像素；转换完全在 CLI 内部完成（`--norm` 这类回灌入口在 v3.0 已移除），唯一例外是 `run.json.prompt_sent`（换算后请求原文，仅供审计，**不要当输入**）

### 8. 标记预览（agent 侧交互式编辑）

- **编辑前先跑图层拆分**拿精确区域：手画框容易偏（实测第一次没框中、第二次底部仍在框外），而图层拆分会让模型自己圈定区域并给出**可直接用的 `<bbox>` 标签**
- **坐标一律按像素给**（`--point x,y` / `--box x1,y1,x2,y2`），`mark` 给出的成品标签也是像素，直接粘进 prompt 即可
- **先核对再提交**：先 `seedream mark <图>`（网格默认开，刻度在图片外留白区、值＝原图像素）读出坐标，再 `seedream mark <图> --box ...` 画框让有视觉的模型确认，偏了就改数字重跑
- ⚠️ **预览图不要当 `--images` 传**（带留白与刻度，污染输入）；要传标记图就用 `--plain`
- 用标记图做输入时（官方「任意标记」形式）**必须在 prompt 里写"移除所有标记"**，否则框可能被画进结果
- 方法优先级：① 纯提示词 → ③ 坐标/框选 → ④ 标记图；② 单点适合替换单个物体，修结构不如框选
- **分辨率默认自动**：按原始尺寸出图，仅当产物达到 2MB 预览上限时才自动降档；要强制原始尺寸加 `--max-edge 0`
- **参考图超限会被本地拦下**（像素/宽高比/宽高/30MB），并给出**可执行的缩放建议尺寸**；技能**不会自动改图**，缩不缩由用户决定

### 9. 编码规范

本项目的 Python 编码规范，核心要点：
- 使用 `|` 运算符表示联合类型
- 集合抽象基类从 `collections.abc` 导入
- 无返回值函数必须标注 `-> None`
- 所有公共函数必须包含完整注释

## 运行技能

```bash
# 安装为全局工具（推荐）
cd skills/seedream-image
uv tool install .
seedream draw "一只橘色虎斑猫，毛发蓬松，翡翠绿眼睛，坐在洒满阳光的木质窗台上，窗外是秋天枫叶，写实摄影风格，暖金色侧光，中景构图，超精细8K" --size 2K

# 或使用 uv run 直接运行
cd skills/seedream-image
uv run seedream draw "一只橘色虎斑猫，毛发蓬松，翡翠绿眼睛，坐在洒满阳光的木质窗台上，窗外是秋天枫叶，写实摄影风格，暖金色侧光，中景构图，超精细8K" --size 2K

# 需要设置 API Key（仅支持环境变量，不读取 .env 文件）
export ARK_API_KEY="your-api-key"

# 可选：Base URL（默认按量后付费端点 https://ark.cn-beijing.volces.com/api/v3）
# agent plan 用 https://ark.cn-beijing.volces.com/api/plan/v3，Key 与端点必须匹配，否则 401
export ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"

# 可选：生成记录的存放根目录（默认用当前工作目录下的 .seedream/）
export SEEDREAM_HOME="/path/to/data"
```

## 生成记录（输出目录）

每次生成一个目录，落在**数据根目录**（`$SEEDREAM_HOME`，未设置时为当前工作目录下的 `.seedream/`）：

```
<数据根>/
├── index.jsonl                     # 一行一条任务摘要，ls 直接读它
├── runs/<YYYYMMDD-HHMMSS-xxxxxx>/  # 一次生成 = 一个目录
│   ├── run.json                    # 提示词 / 参数 / 输入 / 产物（唯一真相）
│   ├── inputs/                     # 参考图副本（sha256 命名，可寻址）
│   └── outputs/                    # 产物（图层拆分：底图 + L01…L16）
└── mark/                           # mark 的标记预览图
```

- 图层拆分产出：底图 `<uid>-L00.png`、图层 `<uid>-L<nn>-<图层名>.png`（图层恒为 png）
- 查询用 `seedream ls` / `show` / `replay`，字段说明见 `references/run-format.md`
- 该目录已被加入 `.gitignore`，不会提交到版本控制。

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