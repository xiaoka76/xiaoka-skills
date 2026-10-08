# Seedream 提示词模板

本目录是 Seedream 5.0 Pro 的内置提示词模板库，共 17 类 93 个模板，覆盖 UI 样机、产品视觉、海报、插画、地图、信息图、技术架构图等场景。

## 使用方法

1. 先根据任务类型找到对应分类目录
2. 打开具体模板 `.md` 文件
3. 模板中的 `{argument name="..." default="..."}` 是需要替换的参数
4. 渲染好的 JSON 展开成自然语言 prompt 字符串，作为 `seedream draw` / `edit` 的提示词

> 模板里的 JSON **只是"提示词结构"，不是 API 请求体**；真正发给接口的是展开后的自然语言字符串。
> Seedream 5.0 Pro 对中文 prompt 支持良好，可以直接用中文写模板。

## 模板分类

| 分类 | 适用场景 |
|------|----------|
| `ui-mockups/` | UI 样机（直播、社交、聊天） |
| `product-visuals/` | 产品视觉（爆炸图、白底图、影棚图） |
| `portraits-and-characters/` | 人物/角色肖像 |
| `poster-and-campaigns/` | 海报/品牌主视觉 |
| `scenes-and-illustrations/` | 场景插画 |
| `maps/` | 地图类视觉 |
| `infographics/` | 信息图 |
| `slides-and-visual-docs/` | 幻灯片/讲解图 |
| `storyboards-and-sequences/` | 分镜/漫画/流程板 |
| `grids-and-collages/` | 网格/拼贴 |
| `branding-and-packaging/` | 品牌/包装 |
| `avatars-and-profile/` | 头像/人设 |
| `editing-workflows/` | 编辑工作流 |
| `assets-and-props/` | 素材/道具 |
| `academic-figures/` | 学术配图 |
| `technical-diagrams/` | 技术架构图 |
| `typography-and-text-layout/` | 字体/版式 |

## 方法论文档

| 文件 | 说明 |
|------|------|
| `cli-reference.md` | CLI 参数与接口细节：安装、端点套餐、各子命令完整参数表、分辨率像素表、参考图约束、图层拆分产出与还原、`mark` 绘制规则、`--optimize`、编辑模板匹配 |
| `prompt-guide.md` | 官方《Seedream 4.0-5.0 提示词指南》要点：5 条通用规则、文生图/图生图/多图输入各场景官方范例、与 5.0 pro 的差异 |
| `prompt-writing.md` | JSON 提示词模板总规范：模板怎么组织、字段怎么设计、参数如何区分必问/默认/随机 |
| `run-format.md` | 生成记录（run）的文件格式：`run.json` / `inputs/` / `outputs/` / `index.jsonl` 字段说明 |