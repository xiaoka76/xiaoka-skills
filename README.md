# xiaoka-skills

> 开源 AI 技能合集 — 为 AI 开发环境注入专业能力。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 简介

`xiaoka-skills` 是一个开源项目，收录了一系列面向 AI 编码助手（如 Trae IDE）的**技能包**。每个技能包以独立目录组织，包含技能清单、可安装的 Python 包和知识库文档，帮助 AI 获得特定领域的专业能力。

## 技能列表

### 联网搜索 — `byted-web-search`

[火山引擎豆包搜索](https://www.volcengine.com/docs/87772/2272949) API 技能，支持 **Custom / Global 双引擎**。

**核心能力：**
- Custom 版（默认）：文搜文 / 文搜图，时延低（~700ms），支持权威分级、时效范围、Query 改写
- Global 版（`--engine global`）：全球站点覆盖、摘要长度可调、**图搜图（visual）**、ICP 备案过滤
- 免费额度：每月 500 次（Custom / Global 共用）

**快速开始：**

```bash
# 进入技能目录
cd skills/byted-web-search

# Custom 版文搜文（默认）
python3 scripts/web_search.py "北京天气"

# Global 版文搜文（全球站点）
python3 scripts/web_search.py --engine global "OpenAI latest news"

# Global 版图搜图（以图找图）
python3 scripts/web_search.py --engine global "同款商品" --type visual --image-file /path/to/img.jpg
```

详细用法请参阅 [SKILL.md](skills/byted-web-search/SKILL.md)。

---

### 图像生成 — `seedream-image`

[Seedream 5.0 Pro](https://www.volcengine.com/product/doubao-seedream) 专用图像生成技能。支持文生图、图生图、交互编辑、图层拆分与透明背景，内置 17 类共 93 个提示词模板。

**核心能力：**
- 文生图（支持中文 prompt）
- 单/多图生图（最多 10 张参考图）
- 交互编辑（`<point>` / `<bbox>` 坐标精确定位，先用 `mark` 读像素坐标）
- 图层拆分（把单张图拆成 1 张底图 + 最多 16 个透明图层，带 z_index / 边界框 / 图层名）
- 透明背景（`seedream cutout`，产出带 alpha 通道的素材图）
- 标记预览（`seedream mark`：坐标网格 + 彩色标记，让 agent 自己核对编辑位置后再提交；分辨率自动——原始尺寸出图，超 2MB 预览上限才自动降档）
- 参考图本地预检（像素 / 宽高比 / 大小超限时给出可执行的缩放建议，不自动改图）
- 原生多语种文字渲染（14 种语言）
- **生成记录**（提示词 / 参考图副本 / 参数 / 产物全量落盘，`ls` 查询 · `show` 查看 · `replay` 复现）
- 分辨率档位切换（1K / 1.5K / 2K，支持自定义宽高）
- 子命令按**意图**划分（`draw` / `edit` / `split` / `cutout`，参数即该场景必需的信息）

**内置模板分类（17 类共 93 个模板）：**

| 分类 | 说明 |
|------|------|
| 学术配图 | 图文摘要、机制图、神经网络架构等 |
| 素材/道具 | 游戏截图样机、拟物化图标 |
| 头像/人设 | 角色肖像、贴纸集、风格迁移 |
| 品牌/包装 | 饮料标签、品牌识别板、吉祥物设计 |
| 编辑工作流 | 背景替换、对象移除、产品精修 |
| 网格/拼贴 | 广告横幅、动漫 pitch 板、lookbook |
| 信息图 | bento 网格、KPI 仪表盘、分步信息图 |
| 地图 | 美食地图、城市插画、旅行路线图 |
| 人物/角色 | 角色设定表、创始人肖像、虚拟主播 |
| 海报/主视觉 | 品牌海报、营销 KV、编辑封面 |
| 产品视觉 | 电商展板、爆炸视图、影棚级产品 |
| 场景插画 | 概念场景、治愈系场景、绘本场景 |
| 幻灯片/讲解图 | 教育图表、政策风格幻灯片 |
| 分镜/漫画/流程 | 电影分镜、四格漫画、产品 TVC 分镜 |
| 技术架构图 | ER 图、思维导图、网络拓扑、系统架构 |
| 字体/版式 | 双语排版、标题安全海报 |
| UI 样机 | 聊天界面、着陆页、直播电商 UI |

**快速开始：**

```bash
# 进入技能目录
cd skills/seedream-image

# 设置 API Key（仅支持环境变量，不读取 .env 文件）
export ARK_API_KEY="your-api-key"

# 可选：切换 Base URL（默认按量后付费端点）
# agent plan 用户填 https://ark.cn-beijing.volces.com/api/plan/v3，Key 与端点必须匹配
export ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"

# 安装为全局工具（推荐）
uv tool install .
seedream draw "一只橘猫坐在窗台上，午后阳光" --size 2K

# 或使用 uv run 直接运行
uv run seedream draw "一只橘猫坐在窗台上，午后阳光" --size 2K

# 图生图 / 编辑（URL 或本地路径）
seedream edit "把这只猫放在日式庭院里" \
    --images "https://example.com/cat.jpg" \
    --size 1K
# 产物格式：draw / edit 默认 jpeg（体积小，可直接查看与发送），需无损加 --format png

# 看历史任务 / 看详情 / 复现（默认只预演，加 --run 真跑）
seedream ls
seedream show last
seedream replay last --run

# 图层拆分：把设计稿拆成 1 底图 + 最多 16 个透明图层（-p 可省略）
seedream split ./poster.png

# 透明背景：输出带 alpha 通道的素材图（1 张带透明通道的输入图，输出恒为 png）
seedream cutout ./product.png

# 标记预览：先看网格读坐标，再画框核对（坐标一律按像素给）
seedream mark ./photo.png                      # 出网格图读坐标（默认原始尺寸）
seedream mark ./photo.png --box 980,640,1180,860:手部 -o ./check.png
# 提交模式：输出纯标记图，可直接作为参考图（prompt 里记得写“移除所有标记”）
seedream mark ./photo.png --box 980,640,1180,860 --plain -o ./marked.png
```

详细用法请参阅 [SKILL.md](skills/seedream-image/SKILL.md)。

---

### 公文排版 — `gongwen-skill`

按《党政机关公文格式》（GB/T 9704-2012）把中文正式材料生成可直接交付的公文 DOCX：版心、字体、标题层级、文号、页码、附件、版记，支持**预印红头纸套打 / 完整电子红头**、联合行文，以及信函 / 命令（令）/ 纪要 / 横排表格四种专门版式。

> 本技能复制自上游开源项目 [mizzlelover/gongwen-gbt9704-skill](https://github.com/mizzlelover/gongwen-gbt9704-skill)（MIT License，Copyright © 2026 mizzlelover），快照 v2.0.0；本副本改名为 `gongwen-skill`，并将 DOCX 打包/读包与 PDF→PNG 改为内置实现（`scripts/zip.mjs`、`scripts/pdf2png.mjs` + `vendor/pdfium`），排版逻辑与原版一致。

**核心能力：**
- 普通稿（`ordinary`）：A4、156mm×225mm 版心、三号仿宋正文、小标宋二号标题、四级标题层次
- 正式发文（`formal`）：默认预印红头纸套打；`--letterhead digital` 生成完整电子红头；文号 / 签发人 / 份号 / 密级 / 紧急程度按标准定位
- 专门版式：信函 `letter` / 命令（令）`command` / 纪要 `minutes` / 横排表格 `horizontal-table`
- 联合行文（`--joint-org`）、分离装订附件（`--attachment-detached`）、版记（抄送 / 印发）、单双页页码、Word/WPS 可更新目录
- 内置独立校验器；文号与日期写法有合法性拦截，输出后可直接自检

**快速开始：**（生成与校验只需 Node.js ≥18，无需 `zip` / `unzip`；PDF→PNG 已内置，docx→PDF 仍需 LibreOffice；输出完全保真需目标机装有方正小标宋 + 仿宋系字体，缺失时会明确警告并替代）

```bash
# 进入技能目录
cd skills/gongwen-skill

# 普通稿：生成 + 校验
node scripts/generate_gongwen_docx.mjs --input 草稿.md --output /tmp/gongwen.docx --format ordinary --title "文档标题"
node scripts/verify_gongwen_docx.mjs --input /tmp/gongwen.docx --profile ordinary

# 正式发文（预印红头纸套打；72mm 为默认留白起点，可按实际纸样调 37–130mm）
node scripts/generate_gongwen_docx.mjs --input 草稿.md --output /tmp/formal.docx --format formal --letterhead preprinted --letterhead-reserve-mm 72 --org "发文机关名称" --doc-no "单位发〔2026〕1号" --title "文档标题"
```

详细用法请参阅 [SKILL.md](skills/gongwen-skill/SKILL.md)（含全部参数、边界与验证方法）。

---

## 项目结构

```
xiaoka-skills/
├── skills/                  # 技能目录
│   ├── byted-web-search/    # 火山引擎豆包搜索（Custom/Global 双引擎）
│   ├── gongwen-skill/       # 公文排版（GB/T 9704-2012 DOCX 生成；复制自 mizzlelover/gongwen-gbt9704-skill）
│   └── seedream-image/      # 图像生成技能
│       ├── SKILL.md         # 技能清单
│       ├── pyproject.toml   # 包配置
│       ├── src/seedream/    # 可安装的 Python 包
│       │   ├── cli.py       # CLI 入口（draw/edit/split/cutout/mark/ls/show/replay）
│       │   ├── generate.py  # 核心生成逻辑（调接口 + 产物落盘）
│       │   ├── run.py       # 生成记录：任务目录、索引、输入副本、run.json 读写
│       │   ├── tags.py      # prompt 内坐标标签的校验与换算
│       │   ├── mark.py      # 标记预览渲染（网格 / 标签 / 自动降档）
│       │   └── config.py    # 配置常量与数据根目录解析
│       └── references/      # 知识库（17 类共 93 个提示词模板）
│           ├── README.md
│           ├── prompt-writing.md
│           └── <category>/
│               └── <template>.md
├── AGENTS.md                # AI Agent 交互指南
├── LICENSE                  # MIT 许可证
└── README.md
```

## 添加新技能

欢迎贡献新的技能包！请参考 [AGENTS.md](AGENTS.md) 中的目录结构规范，创建包含 `SKILL.md` 的技能目录。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。

Copyright © 2026 xiaoka