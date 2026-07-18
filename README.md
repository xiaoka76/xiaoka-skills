# xiaoka-skills

> 开源 AI 技能合集 — 为 AI 开发环境注入专业能力。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 简介

`xiaoka-skills` 是一个开源项目，收录了一系列面向 AI 编码助手（如 Trae IDE）的**技能包**。每个技能包以独立目录组织，包含技能清单、可安装的 Python 包和知识库文档，帮助 AI 获得特定领域的专业能力。

## 技能列表

### 图像生成 — `seedream5pro-image`

[Seedream 5.0 Pro](https://www.volcengine.com/product/doubao-seedream) 专用图像生成技能。支持文生图、图生图、交互编辑，内置 17 类共 91 个提示词模板。

**核心能力：**
- 文生图（支持中文 prompt）
- 单/多图生图（最多 10 张参考图）
- 交互编辑（WebUI 点选/框选标注 + `<point>` / `<bbox>` 坐标精确定位）
- 原生多语种文字渲染（14 种语言）
- 自动本地保存（带会话记录）
- 一键分辨率切换（1K / 2K，支持自定义宽高）

**内置模板分类（17 类共 91 个模板）：**

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
cd skills/seedream5pro-image

# 设置 API Key（仅支持环境变量，不读取 .env 文件）
export ARK_API_KEY="your-api-key"

# 安装为全局工具（推荐）
uv tool install .
seedream generate --prompt "一只橘猫坐在窗台上，午后阳光" --size 2K

# 或使用 uv run 直接运行
uv run seedream generate --prompt "一只橘猫坐在窗台上，午后阳光" --size 2K

# 图生图（URL 或本地路径）
seedream generate \
    --prompt "把这只猫放在日式庭院里" \
    --images "https://example.com/cat.jpg" \
    --size 1K

# 交互编辑（启动 WebUI，支持多图预加载）
seedream webui --preload /path/to/photo1.jpg --preload /path/to/photo2.jpg
```

详细用法请参阅 [SKILL.md](skills/seedream5pro-image/SKILL.md)。

---

## 项目结构

```
xiaoka-skills/
├── skills/                  # 技能目录
│   └── seedream5pro-image/  # 图像生成技能
│       ├── SKILL.md         # 技能清单
│       ├── pyproject.toml   # 包配置
│       ├── src/seedream/    # 可安装的 Python 包
│       │   ├── cli.py       # CLI 入口（generate/session/webui）
│       │   ├── generate.py  # 核心生成逻辑
│       │   ├── session.py   # Session 管理
│       │   ├── webui.py     # 交互编辑 WebUI 后端
│       │   ├── config.py    # 配置常量
│       │   └── static/      # WebUI 前端文件
│       └── references/      # 知识库（17 类共 91 个提示词模板）
│           ├── README.md
│           ├── prompt-writing.md
│           └── <category>/
│               └── <template>.md
├── .trae/
│   ├── rules/
│   │   └── code-style.md    # Python 编码规范
│   └── specs/               # 开发规范文档
├── AGENTS.md                # AI Agent 交互指南
├── LICENSE                  # MIT 许可证
└── README.md
```

## 添加新技能

欢迎贡献新的技能包！请参考 [AGENTS.md](AGENTS.md) 中的目录结构规范，创建包含 `SKILL.md` 的技能目录。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。

Copyright © 2026 xiaoka