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
| `seedream5pro-image` | Seedream 5.0 Pro 图像生成（文生图/图生图/交互编辑） | `seedream generate` |

## Agent 交互规则

### 1. 技能发现

当用户请求涉及以下领域时，Agent 应优先查找 `skills/` 下对应的技能目录：

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

`references/` 目录包含技能所需的知识库文档。当前 `seedream5pro-image` 技能内置 **17 类共 91 个提示词模板**，分布在 `prompt-writing.md`（模板方法论总规范）和各分类目录中。Agent 在执行任务时应当：
- 根据任务类型（如"学术配图"、"品牌海报"）选择对应分类的模板
- 参考模板中的 JSON 结构构建提示词
- 遵循 `prompt-writing.md` 中的模板方法论

### 4. 编码规范

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
seedream generate --prompt "一只橘猫" --size 2K

# 或使用 uv run 直接运行
cd skills/seedream5pro-image
uv run seedream generate --prompt "一只橘猫" --size 2K

# 需要设置 API Key（或创建 .env 文件自动加载）
export ARK_API_KEY="your-api-key"
```

## 输出目录

图像生成结果按会话类型统一保存到 `.seedream/` 目录：

- 文生图/图生图 → `.seedream/generate/<session_id>/output/`
- 交互编辑 → `.seedream/edit/<session_id>/output/`

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