# Seedream 提示词模板

本目录结构来自 GPT Image 2 技能，适配到 Seedream 模型使用。

## 使用方法

1. 先根据任务类型找到对应分类目录
2. 打开具体模板 `.md` 文件
3. 模板中的 `{argument name="..." default="..."}` 是需要替换的参数
4. 渲染好的 JSON 展开成自然语言 prompt 字符串，传给 `seedream_image_generate.py`

## 与 GPT Image 2 的区别

- Seedream 不需要 `background`、`moderation`、`quality` 等 GPT Image 2 特有参数
- Seedream 5.0-pro 对中文 prompt 支持良好，可以直接用中文写模板
- 模板中的 JSON 只是「提示词结构」，不是 API 请求体
- 最终传给 seedream_generate 的 `prompt` 字段是展开后的自然语言字符串

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