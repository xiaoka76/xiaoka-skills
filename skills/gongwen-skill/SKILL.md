---
name: gongwen-skill
display_name: 公文排版
display_name_en: Gongwen Document Formatting
description: 把中文正式材料整理成可直接交付的公文 DOCX：按 GB/T 9704-2012 处理版心、字体、标题层级、文号、页码、附件与版记；普通稿不误用红头，正式发文支持预印红头纸套打或完整电子红头，并保留 Word/WPS 可更新目录。
description_zh: 按 GB/T 9704-2012 将中文正式材料整理为可直接交付的公文 DOCX，覆盖版心、字体、标题层级、文号、页码、附件、版记及预印红头纸套打，并保留 Word/WPS 可更新目录。
description_en: Generate Chinese official DOCX under GB/T 9704-2012 with page layout, typography, headings, document numbers, page numbers, attachments, colophon, preprinted letterhead, and Word/WPS TOC support.
version: 2.1.0
author: 谁是专家
---

> **来源**：本技能复制自 [mizzlelover/gongwen-gbt9704-skill](https://github.com/mizzlelover/gongwen-gbt9704-skill)（作者「谁是专家」，MIT License，Copyright © 2026 mizzlelover，见同目录 [LICENSE](LICENSE)），快照 v2.0.0（2026-10-11 纳入本仓库）。本副本的改动：技能名改为 `gongwen-skill`；DOCX 打包与读包改用内置 `scripts/zip.mjs`（基于 Node 自带 `node:zlib`），不再依赖外部 `zip`/`unzip`；PDF→PNG 改用内置 `scripts/pdf2png.mjs` 与 `vendor/pdfium`（PDFium WebAssembly，BSD-3-Clause），不再依赖 poppler；其余内容与原版一致。

# 公文版式工具

## 标准依据与边界

GB/T 9704-2012《党政机关公文格式》现行，2025-05-30 复审继续有效。其适用于党政机关制发公文；其他机关、单位可以参照执行。

先读 `references/gbt9704-2012-summary.md`；需要逐项复核时再读 `references/gbt9704-audit-matrix.md` 和 `references/formal-checklist.md`。标准规定纸张、版面、要素编排和印制装订要求。

## 工具定位

本工具只处理排版，不判断单位身份、授权状态或后续盖章方式。它会根据用户明确选择的版式模式应用对应的排版规则，不因“正式”“国企”“报告”或仅提供机构名称而擅自使用红头。

生成器可输出 A4、156mm×225mm 版心、三号仿宋正文、小标宋二号标题、四级标题层次、两字缩进，页码默认单页右、双页左（也可显式选择居中）。四级标题均写入 Word/WPS 标题样式和大纲级别，便于后续插入、更新目录；文章总标题使用独立“公文标题”样式，不进入目录。上行文的文号和签发人在同一行编排，左右各空一字；信函、命令（令）、纪要和横排表格使用各自专用版式；电子联合行文可重复传入 `--joint-org`；主办机关在前，联署机关名称分行排列；输入含“文件”时将“文件”置右并按联署名称上下居中；分离装订附件可加 `--attachment-detached`；重复传入 `--attachment-file` 时必须同时提供与附件顺序、标题一致的 `--attachment-note`，附件会另页生成并保持页码连续。版记会锚定最后一页版心底部，正式页码按版心下边缘下7mm的位置生成。正式版头的份号、密级、紧急程度和电子机关标志全部在正常文档流内以精确行高锚定：机关标志上边缘恒为版心顶下 35mm，左上字段占行也不会把机关标志或预印红头留白向下推移；版头不使用浮动框（w:framePr）和 VML，红色分隔线用段落底边框绘制，Word/WPS/LibreOffice 与在线预览中的纵向位置一致，不会出现标志、文号与红线重叠。只有传入密级而未传入份号时，首行会保留空位，密级仍从第二行开始。

`references/formal-checklist.md` 是可选的版式复核清单。涉及印章或签名章时，使用者可在 Word/WPS 中插入已取得的图片或完成实体盖章；本生成器不内置印章图像。

## 生成打印稿

```bash
node scripts/generate_gongwen_docx.mjs --input source.md --output output.docx --format ordinary --title "文档标题"
```

普通材料使用 `--format ordinary`，不绘制红头；页码默认同样按 GB/T 9704-2012 7.3.5 编排为单页居右、双页居左（4 号半角宋体阿拉伯数字，距版心下边缘 7mm），确需居中页码时显式传 `--page-number center`。正式发文须显式使用 `--format formal`；其默认 `--letterhead preprinted`，即首面预留红头纸区域、不在 DOCX 中重绘纸上已有的红色机关标志和红线。`--doc-no` 等本次需打印的黑色变量仍可保留。只有明确要求完整电子版时使用 `--letterhead digital`。完整电子红头的机关标志按标准推荐使用小标宋体，标题按标准使用小标宋体；生成器会在缺失时明确警告并记录实际替代字体，需要硬性阻止替代输出时加 `--require-standard-fonts`。红线下标题按28磅版心网格空二行。

```bash
# 预印红头纸套打；72mm 是默认机关标志区域起点，可按实际纸样调为 37—130mm
node scripts/generate_gongwen_docx.mjs --input source.md --output output.docx --format formal --letterhead preprinted --letterhead-reserve-mm 72 --org "发文机关名称" --doc-no "单位发〔2026〕1号" --title "文档标题" --sender "落款单位" --date "2026年9月9日"

# 完整电子红头版，仅在明确要求时使用
node scripts/generate_gongwen_docx.mjs --input source.md --output output.docx --format formal --letterhead digital --org "发文机关名称" --doc-no "单位发〔2026〕1号" --title "文档标题"
```

落款默认按 GB/T 9704-2012 7.3.5.1 处理：成文日期右空四字，发文机关署名在日期之上、以日期为准居中（传入 `--sender` 和 `--date` 即自动对齐）。需要模拟盖章或签名章时可显式传 `--seal-mode seal`（署名与日期均右空四字、右端对齐，供印章下压成文日期）或 `--seal-mode signed`（须同时传 `--signer-title`、`--signer`）。

本工具不包含简报、信息专报等非正式文种的红色刊头版式（刊头名称、期数、编发单位、报送线、刊尾版记）。这类材料可用 `--format ordinary` 生成符合版心与字体规范的底稿，再在 Word/WPS 中手工补刊头，不要用 `--format formal` 把简报套成法定公文红头。

`letter`、`command`、`minutes`、`horizontal-table` 分别对应信函、命令（令）、纪要和横排表格格式；需要时显式传入 `--format` 和相应字段。横排表格会生成横向A4页面和225mm表格，单双页表头在订口/切口的朝向仍需目标 Word/WPS 模板核对。联合行文使用 `--joint-org`，主办机关在前、联署机关名称分行排列；输入含“文件”时将“文件”置右并按联署名称上下居中；附件不能与正文一起装订时使用 `--attachment-detached`，附件首行会补排文号和附件序号。`command` 会要求机关标志以“命令”或“令”结尾；信函中的份号、密级和紧急程度会在第一条双线下按标准顺序编排，联合行文和机关专用信函模板仍需目标软件核对。除信函格式不排页码外，所有格式默认单双页页码（`standard`：单页居右空一字、双页居左空一字）；`center` 为居中页码、`none` 为无页码，均需显式传入。

附件可重复传入 `--attachment-file attachment.md`。附件 Markdown 的首个一级标题会作为附件标题，第一页第一行写“附件1”（后续文件递增），第三行写标题，随后排正文；附件说明通过 `--attachment-note` 提供，工具会统一为“附件：”并去除末尾标点，同时拒绝顺序或标题与附件文件不一致的输入。复杂横排附件、不能与正文一起装订的附件和机关专用模板仍需在目标 Word/WPS 中核对。

正式版式的 `--doc-no` 采用“单位发〔2026〕1号”这类标准写法；`--date`、`--print-date` 采用“2026年9月9日”，月份和日期不补零。明显不符合这两类规则的输入会被拒绝，避免把错误字段排成看似规范的文件。

Markdown 标题优先按序数识别：`一、`、`（一）`、`1.`、`（1）`；序数缺失时才按 Markdown 层级映射。正文、四级标题均左空二字，回行顶格。注意 `1.` 开头的段落按国标三级层次处理（仿宋三号、写入大纲级别），可以连续多条并在条目间正常分页；不要把长篇正文拆成以 `1.` 开头的段落，否则整段都会进入标题大纲。长标题在二号字下超过约 20 个全角字时，生成器会给出折行警告；可在 `--title` 中直接传入真实换行符手动均衡分行，避免自动折行出现孤字行。标题字体在运行机器缺失时会明确报告并使用可见替代字体；打开文件时仍须确认目标 Office/WPS 的实际字体，不把普通宋体视作小标宋的等价替代。

层次标题的尾标点按排版形式区分：标题独立成行（单独成段的 `一、`、`（一）` 等）时，行尾不加标点，引号、书名号等自身闭合符号除外；标题与正文同段（段首式，如 `（一）标题。正文……`）时，标题句末加句号再与正文连接。生成器不自动增删该标点，须由源稿按此规则写好。以四位年份加点开头的行（如 `2013.09—2016.06　某某大学`）按日期处理为普通正文，不会被误判为 `1.` 三级标题或有序列表，年月标点与原文保持一致。

## 验证

```bash
# 以下 PDF/PNG 步骤为可选，只有 docx→PDF 需要 LibreOffice；缺失时跳过不影响生成与校验
soffice --headless --convert-to pdf --outdir /tmp output.docx
node scripts/verify_gongwen_docx.mjs --input output.docx --profile formal --letterhead preprinted
# 目标电脑必须装有标准小标宋体和仿宋体时，再加严格字体校验
node scripts/verify_gongwen_docx.mjs --input output.docx --profile formal --letterhead digital --require-standard-fonts
# PDF 逐页转 PNG（内置 PDFium，不需要 poppler），供目视或截图核对
node scripts/pdf2png.mjs --input /tmp/output.pdf --prefix /tmp/output --dpi 110
# 逐场景生成 DOCX、PDF 和 PNG，人工按截图核对版式
bash tests/visual-audit.sh /tmp/gongwen-visual-audit
```

校验器会先读包并逐部件校验长度与 CRC，同时检查本地头与中央目录是否一致（覆盖 `unzip -t` 的主要检查项），再核对版式要素。

`pdf2png.mjs` 内置 PDFium 的 WebAssembly 构建（`vendor/pdfium/`，与 Chrome 同一渲染引擎），任何平台只要有 Node 就能把 PDF 转成 PNG，不需要安装 poppler；`--engine poppler` 可改用系统的 `pdftoppm`，`--dpi` 默认 110。

全条款视觉证据和未自动化边界见[GB/T 9704-2012 全条款视觉核验记录](references/gbt9704-visual-audit.md)和[全条款截图证据矩阵](references/gbt9704-screenshot-evidence.md)。横排表格的单双页表头方向、实体印章、纸张和装订不能只由 DOCX 生成器证明。

校验器核验生成器可检查的版式要素，并按 `ordinary`、`formal`、`letter`、`command`、`minutes`、`horizontal-table` 选择校验档案，包括页码 PAGE 域数字必须为宋体系字体（不能是 Times New Roman）。输出后仍须在目标 Word/WPS 与实际打印条件下检查首页正文、分页、附件、表格、页码、红头纸套打和装订。已知渲染差异：版记（抄送、印发机关和日期）以浮动表锚定最后一页版心底部，**LibreOffice 转 PDF 时可能不显示该浮动表**，Word/WPS 正常；因此看到 PDF 里版记缺失时，以 Word/WPS 实际打开效果为准。

## 没有 LibreOffice 时：向用户索取 PDF 再核验

生成和结构校验只需要 Node；只有“转成 PDF 看效果”需要 LibreOffice。当系统里找不到 `soffice` 命令，或 `bash tests/visual-audit.sh` 提示“已跳过 PDF/PNG”时，按下面处理：

1. 先照常完成生成与结构校验，把校验器的 PASS/FAIL 结果如实汇报，**不要因为不能转 PDF 就中断整个流程**。
2. 主动提示用户：本机没有 LibreOffice，无法自动把 DOCX 转成 PDF；请用 Word 或 WPS 打开这份 DOCX，另存或导出为 PDF 后回传。
3. 收到 PDF 后先用内置渲染器转成图片，再逐页核对：
   ```bash
   node scripts/pdf2png.mjs --input 用户回传的.pdf --prefix /tmp/check --dpi 110
   ```
   重点项：
   - 版头：份号、密级、紧急程度、机关标志上边缘距版心顶 35 mm、文号位置、红色分隔线在文号下 4 mm；
   - 标题：二号小标宋、折行有无孤字行、标题下空二行；
   - 层次：一级黑体、二级楷体、三级及以下仿宋，正文首行缩进二字、回行顶格；
   - 页码：单页居右、双页居左，4 号宋体数字，距版心下边缘 7 mm；
   - 版记：锚定最后一页版心底部，分隔线为黑色；
   - 附件：另页起排，附件序号与标题位置正确，页码连续。
4. 结论里注明“本机未做 PDF 渲染，版式依据用户回传的 PDF 核对”。Word/WPS 导出的 PDF 比 LibreOffice 预览更接近最终交付效果，但不能替代实体打印和装订检查。
5. 用户无法提供 PDF 时，只报告结构校验结论，并明确写“未做目视核验”，不要凭空描述版面效果。

## 输出说明

- 版式检查通过后，可写“已按 GB/T 9704-2012 的相关版式参数生成”。
- 使用者可按实际用途决定是否采用 `formal-checklist.md` 逐项复核。
