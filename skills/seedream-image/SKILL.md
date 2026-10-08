---
name: seedream-image
description: Seedream 5.0 Pro 专用图像生成技能。文生图 / 图生图 / 交互编辑（<point>/<bbox> 坐标精确定位）/ 图层拆分（1 底图 + 最多 16 个透明图层），支持透明背景。每次生成都会保存完整过程（提示词、参考图副本、参数、产物），可查询、可复现。内置 17 类提示词模板。使用该技能时：用户想画图、生成图片、改图、编辑图片、做海报/UI/产品图/插画/角色/地图/信息图/分镜等任何视觉内容，或需要高质量的 AI 图像生成能力，或需要把设计稿拆成可编辑图层 / 抠出透明背景素材。
license: MIT
tags: ["image-generation", "seedream-5.0-pro", "seedream", "volcengine", "text-to-image", "image-to-image", "interactive-edit", "layer-decomposition", "transparent-background", "local-save", "reproducible", "cli"]
version: 3.0.5
---

# Seedream 5.0 Pro 图像生成

模型 ID：`doubao-seedream-5-0-pro-260628`。支持文生图 / 图生图 / 交互编辑 / 图层拆分 / 透明背景。
每次生成都会在数据根目录落地一条完整记录（提示词、参考图副本、参数、产物），所以任何一张图都能追回
「它是怎么做出来的」，也能一键复现。不支持组图（`sequential_image_generation`）、流式输出、联网搜索。

> 参考文档：[`references/cli-reference.md`](references/cli-reference.md)（安装/端点/完整参数/分辨率像素表/参考图约束/`mark` 细节）
> · [`references/run-format.md`](references/run-format.md)（记录字段）
> · [`references/prompt-guide.md`](references/prompt-guide.md)（官方 5 条硬要求 + 各场景范例）
> · [`references/prompt-writing.md`](references/prompt-writing.md)（模板方法论）
> · [`references/README.md`](references/README.md)（17 类 93 个模板索引）

## 四个生成子命令

| 命令 | 用途 |
|------|------|
| `seedream draw "<提示词>"` | 文生图 |
| `seedream edit "<指令>" --images <图…>` | 图生图 / 交互编辑（`--images` 必填，最多 10 张） |
| `seedream split <图>` | 图层拆分（1 底图 + 最多 16 个透明图层） |
| `seedream cutout <图>` | 透明背景素材（恒输出 png） |

外加 `seedream mark`（标记预览 / 坐标标签）与 `seedream ls` / `show` / `replay`（记录查询与复现）。

生成子命令的关键参数（完整表与端点细节见 [`references/cli-reference.md`](references/cli-reference.md)）：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--size` / `-s` | `2K`（`split` 为 `auto`） | `1K` / `1.5K` / `2K`；draw/edit/cutout 另支持 `宽x高`，`split` 仅档位 + `auto` |
| `--format` | `jpeg`（`split` 为 `png`） | `png` / `jpeg`；`jpeg` 体积小、可直接查看与发送，要无损或透明背景时显式传 `png`；`split` 只作用于底图；**`cutout` 没有此选项** |
| `--watermark` | 关闭 | 加此开关才带水印 |
| `--optimize` | `standard` | `standard` / `fast` |
| `--timeout` / `-t` | `300` | API 超时（秒） |

### 安装与环境变量

```bash
cd skills/seedream-image && uv tool install .   # 或 uv run seedream / pip install -e .
export ARK_API_KEY="..."                            # 必填
export SEEDREAM_HOME="/path/to/data"                # 可选，记录存放根；默认 cwd/.seedream/
```

- Key 优先级：`ARK_API_KEY` > `MODEL_IMAGE_API_KEY` > `MODEL_AGENT_API_KEY`。
- Base URL 优先级：`ARK_BASE_URL` > `MODEL_IMAGE_API_BASE` > 默认 `https://ark.cn-beijing.volces.com/api/v3`。
- ⚠️ **端点按套餐区分，Key 与端点必须匹配**（agent plan 用 `/api/plan/v3`，否则 401）。

### 分辨率

- 档位 `1K` / `1.5K` / `2K`（推荐），或自定义 `宽x高`（**不可混用**；`split` 不支持自定义宽高）。
- **`1.5K` 与 `1K` 同价、画质更优**——性价比优先选 `1.5K`。
- 各档位像素值、自定义像素范围、`split` 的 `auto` 适配规则 → [`references/cli-reference.md`](references/cli-reference.md)。

## 坐标口径：agent 只写原图像素

**agent 只写原图像素标签，换算由 CLI 内部完成**——你不需要也不应关心接口要什么格式。

```
你写：  将图1<bbox>300 1240 610 1590</bbox>区域换成马克杯    ← 网格上直接读数
```

| 环节 | 口径 |
|------|------|
| agent 在 prompt 里写的坐标标签 | **原图像素**（零心算） |
| `mark` 的输入 / 网格刻度 / 输出标签、`split` 的 `prompt_fragment` | **原图像素**，可直接粘进 prompt |
| `show` / `ls` / 命令输出 | **只有像素** |
| `run.json` | `prompt`＝像素（**复用用这个**）· `prompt_sent`＝换算后（**仅供审计，勿当输入**） |

> 坐标只有一种形态：**原图像素**。唯一例外是 `run.json.prompt_sent`（已换算的请求原文，只为事后审计）。
> 把 `prompt_sent` 的内容再当像素粘回去 = 静默落到错误区域；要复用就用 `prompt` 或直接 `seedream replay`。

### 标签校验（`edit` / `split` 在本地先拦）

| 检查项 | 处理 |
|--------|------|
| 标签名/结构可疑（`<box>`、未闭合 `<bbox>`） | **提示**正确写法，继续执行 |
| 坐标个数不对 / 含小数·单位·百分号 / 超出图片范围 / 多图未标归属 / 有标签却无参考图 | **报错中止** |
| 用逗号等分隔符、框写反 | 自动兼容 + 提示 |
| 框的宽或高为 0 | 提示（模型可能无法定位） |

归属由**紧邻标签前面**的「图N」决定；只有 1 张参考图时可省略；多张未标明 → 报错；参考图是网络 URL
（读不到尺寸）→ 报错并提示改用本地路径。

## 标记预览（`mark`）→ 编辑（`edit`）

先出网格读像素坐标、再画框核对、然后把标签写进编辑指令：

```bash
seedream mark photo.png                                # 1) 出网格图，读像素坐标
seedream mark photo.png --box 820,520,1180,860:手部     # 2) 画框核对（偏了就改数字重跑）
seedream edit "把图1<bbox>332 310 478 512</bbox>区域换成白瓷马克杯，保持其他部分不变" --images photo.png
```

- 坐标一律写**像素**：`--point x,y[:标签]` / `--box x1,y1,x2,y2[:标签]`；成品标签也是像素，直接粘。
- ⚠️ **预览图不能当 `--images` 传**（带留白与刻度，会污染输入）；要传标记图就加 `--plain`。
- 传标记图做输入时，prompt **必须写「移除所有标记」**，否则画上去的框有概率被画进结果。
- 方法优先级：① 纯提示词 → ③ 坐标/框选（标记不进图，最稳）→ ④ 标记图（最直观，有污染风险）。
  > 更稳的做法：**先 `seedream split`** 让模型自己圈定区域、给出可直接用的 `<bbox>` 标签，再拿去编辑
  > （手画框容易偏）。

网格绘制规则、标签自动避让、`--max-edge` 降档、`--json` 字段 → [`references/cli-reference.md`](references/cli-reference.md)。

## 图层拆分（`split`）与透明背景（`cutout`）

```bash
seedream split ./poster.png                                              # 自动全拆（不给 -p）
seedream split ./poster.png -p "拆出人物、标题文字和右下角装饰图标"        # 自然语言指定对象
seedream split ./poster.png -p "人物 <bbox>347 305 642 997</bbox>、标题 <bbox>180 64 812 198</bbox>"  # 坐标圈定区域
seedream cutout ./product.png                                            # 抠出主体，恒输出 png
```

**`split` 约束**（均有本地预检：会拦下并给可执行建议、**不会自动改图**）：

- 仅 **1 张**输入图；格式仅 `png` / `jpeg`；总像素 `[512×512, 6000×6000]`（下限比普通图生图严格得多）
- `--size` 默认 `auto`，仅支持 `1K`/`1.5K`/`2K`/`auto`，**不支持自定义宽x高**
- `-p` 可省略（自动识别主要元素）；`--format` **只控制底图格式**，图层恒为 png
- 任一图层失败 → **整体报错**，不支持部分成功；超过 16 个图层可能丢信息
- 每次请求**预扣 17 IPM**（按最大 17 张预留，图片生成完按实际数量返还）

**`cutout` 约束**：仅 1 张**带透明通道**的输入图（`jpg`/`jpeg` 无 alpha，本地拦下；URL 交给 API 判断）；
输出**恒为 png**，CLI 不提供 `--format`。

图层产出的 `z_index` 叠放顺序、两套坐标（`bbox_base`+`bbox_base_size` 还原用 / `bbox_pixel`+`prompt_fragment`
写 prompt 用）、重组公式 → [`references/run-format.md`](references/run-format.md) 与
[`references/cli-reference.md`](references/cli-reference.md)。

## 生成记录与复用（`ls` / `show` / `replay`）

```bash
seedream ls [-n N] [--all] [--json]     # 列出历史任务（最新在前）
seedream show [<id>|last] [--json]      # 看一条任务的完整记录（提示词 / 参考图 / 产物）
seedream replay [<id>|last] [--run]     # 默认只预演、不消耗额度；确认后加 --run 真跑
```

- 记录落在数据根目录（`$SEEDREAM_HOME`，默认 `cwd/.seedream/`）的 `runs/<run_id>/`：
  `run.json`（唯一真相）+ `inputs/`（参考图副本，sha256 命名，可寻址）+ `outputs/`（产物）。
- 产物格式：`draw` / `edit` 默认 **`jpeg`**（体积小，下载完可直接查看、直接发送）；要无损再加 `--format png`。
  `split` 底图默认 `png`（图层恒为透明白底 png），`cutout` 恒为 png。
- ⚠️ **`run.json.prompt` 是原始像素提示词（复用用这个）；`prompt_sent` 是换算后的实际请求（仅供审计，勿当输入）**。
- **失败的任务同样保存了输入**（`status=error`），可直接 `replay` 或改参数重跑。
- 「改上次那张图」：`seedream show last` 看清原提示词与输入 → 再用
  `seedream edit "…" --images <该任务 inputs/ 里的副本>` 继续加工。
- 不要直接 Read 产物（二进制图片）或记录文件——用 `show --json` / `ls --json`。

字段全表见 [`references/run-format.md`](references/run-format.md)。

## Agent 使用规范（强制）

> Seedream 是提示词驱动模型：**"主体 + 行为 + 环境"必须写全**，美学元素用**精准的风格词**补充。
> 官方口径（5.0 一代）：模型理解力更强，**简洁精确的提示通常优于重复堆叠华丽复杂的词汇**——
> 要写"画面信息"，不堆"形容词"。反过来，**只写一个词**（"一只猫"）同样是错的：
> 缺的不是形容词，是信息。

**文生图（无参考图）：**

1. **必须查模板**：按意图在 `references/` 的 17 类模板中找最接近的一个，读它的 JSON 结构与参数策略
   （`must-ask` / `defaultable` / `randomizable`）；缺失的核心信息先向用户确认（每次 2-3 个问题）。
2. **展开为丰富 prompt**：必须覆盖 **主体 / 场景 / 风格 / 光影 / 构图 / 质量** 6 个维度，
   中文 ≤ 300 字、英文 ≤ 600 词。
   - ❌ 禁止：用户说"画一只猫" → 直接 `seedream draw "一只可爱的猫"`（一句话敷衍）。
   - ✅ 示例：`"黄昏时分的赛博朋克茶馆，雨水顺着发光霓虹窗流下。屋内银发少女坐在窗边捧热茶，
     窗外全息龙形灯笼在雨街漂浮。暖黄灯光自右侧打入，湿地面反着霓虹，中景构图。"`
3. **找不到完全匹配的模板**：取最接近的作骨架，仍按 6 维度展开，不得退化为一句话。
4. 至少先读 [`references/prompt-guide.md`](references/prompt-guide.md)（官方 5 条硬要求：连贯自然语言 /
   写明用途 / 精准风格词 / 文字加双引号 / 编辑时显式声明保持不变的部分）与
   [`references/prompt-writing.md`](references/prompt-writing.md)（模板方法论）。

**图生图 / 编辑（有参考图）：**

5. **prompt 应简洁明确**，用「图1」「图2」指代参考图，让模型从参考图提取视觉特征；
   多图输入写清各图各自承担什么。
   - ❌ **禁止编造参考图中不存在的细节**（如凭文件名猜"粉色长发、红色眼瞳"）。
   - ✅ `"将图1的角色替换为图2的角色，保留图1的穿搭"` / `"把图1的A换成B"`。

**图层拆分**：不走上面 1-5 条，按 `split` 的三种 `-p` 写法（省略 / 自然语言指定对象 / `<bbox>` 圈定区域）。

编辑场景的模板匹配表（"换成/去掉/换背景…" → 对应模板）见 [`references/cli-reference.md`](references/cli-reference.md)。

## 参考图约束（本地预检）

单张参考图：格式 `jpeg`/`png`/`webp`/`bmp`/`tiff`/`gif`/`heic`/`heif`；宽高均 **> 14px**；
宽高比 `[1/16, 16]`；≤ **30MB**；总像素 `[196, 3600万]`。图片生成场景最多 **10 张**。

超限时**本地拦下并给出可执行的缩放建议（不会自动改图）**。完整约束表与各档位像素值见
[`references/cli-reference.md`](references/cli-reference.md)。
