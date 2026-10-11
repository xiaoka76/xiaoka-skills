#!/usr/bin/env bash
# 全场景视觉核验：生成 ordinary / formal-digital / formal-preprinted 样例，
# 转 PDF、逐页转 PNG，供人工按 GB/T 9704-2012 截图核对。
# 用法：bash tests/visual-audit.sh [输出目录]
set -euo pipefail

OUT="${1:-/tmp/gongwen-visual-audit}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEN="node ${SCRIPT_DIR}/../scripts/generate_gongwen_docx.mjs"
VERIFY="node ${SCRIPT_DIR}/../scripts/verify_gongwen_docx.mjs"

for bin in node soffice pdftoppm; do
  command -v "$bin" >/dev/null || { echo "缺少依赖：$bin" >&2; exit 1; }
done

mkdir -p "$OUT/samples"
cd "$OUT"

cat > samples/ordinary.md <<'EOF'
为演示普通材料版式，现将有关情况报告如下。

# 一、总体情况

上半年共承担重点任务159项，按时办结138项，按时办结率86.8%；累计办结149项，办结率93.7%。总体看，任务推进有序，基本实现时间过半、任务过半。

# 二、对策建议

1.建立未办结事项台账，实行销号管理。对未办结事项逐项明确责任处室、完成时限，办结一件、销号一件。

2.强化过程管控，推行临期预警和超时通报。对临近时限事项黄色预警，对超时事项通报批评。

3.完善任务统筹和协同机制。对涉及多处室的事项明确牵头责任，打通落实“中梗阻”。
EOF

cat > samples/formal.md <<'EOF'
各市XX局，厅机关各处室：

为进一步加强机关效能建设，现就有关事项通知如下。

# 一、总体要求

坚持目标导向、问题导向、结果导向，推动作风建设常态化、长效化，确保各项任务落地见效。

# 二、重点任务

## （一）开展问题排查

各单位要对照岗位职责全面排查问题，建立问题清单、责任清单、整改清单，实行台账式管理。

## （二）强化过程管控

1.推行临期预警。对临近办理时限的事项提前提醒承办处室和责任人。

2.严格超时通报。对超时办结事项按月通报批评，约谈承办单位主要负责人。

# 三、工作要求

各单位要于7月底前将问题清单报厅办公室，11月底前报送整改落实情况。
EOF

echo "==> 生成 ordinary"
$GEN --input samples/ordinary.md --output ordinary.docx --format ordinary \
  --title $'关于2025年上半年重点工作督查督办情况的分析简报' \
  --sender "厅督查室" --date "2025年7月10日" || true
$VERIFY --input ordinary.docx --profile ordinary

echo "==> 生成 formal digital"
$GEN --input samples/formal.md --output formal-digital.docx --format formal \
  --letterhead digital --org "XX省XX厅文件" --doc-no "X发〔2025〕12号" \
  --title "XX省XX厅关于加强机关效能建设的通知" \
  --sender "XX省XX厅" --date "2025年7月10日" \
  --cc "各市XX局，厅机关各处室" --print-org "XX省XX厅办公室" \
  --print-date "2025年7月12日印发"
$VERIFY --input formal-digital.docx --profile formal --letterhead digital

echo "==> 生成 formal preprinted"
$GEN --input samples/formal.md --output formal-preprinted.docx --format formal \
  --letterhead preprinted --doc-no "X发〔2025〕12号" \
  --title "XX省XX厅关于加强机关效能建设的通知" \
  --sender "XX省XX厅" --date "2025年7月10日" \
  --cc "各市XX局，厅机关各处室" --print-org "XX省XX厅办公室" \
  --print-date "2025年7月12日印发"
$VERIFY --input formal-preprinted.docx --profile formal --letterhead preprinted

for f in ordinary formal-digital formal-preprinted; do
  echo "==> 转换 $f"
  for attempt in 1 2 3; do
    soffice --headless --convert-to pdf --outdir . "$f.docx" >/dev/null 2>&1 || true
    [ -s "$f.pdf" ] && break
    sleep 2
  done
  if [ ! -s "$f.pdf" ]; then
    echo "警告：$f.docx 转 PDF 失败（可手工用 Word/WPS 打开核对）" >&2
    continue
  fi
  pdftoppm -png -r 110 "$f.pdf" "$f"
done

echo ""
echo "完成。请逐页核对 $OUT 下的 PNG："
echo "  - 标题字体/折行、三级层次字体（黑体/楷体/仿宋）"
echo "  - 连续 1.2.3. 条目跨页时页底不应出现异常大空白"
echo "  - 页码：默认奇右偶左（单页右空一字、双页左空一字），数字为宋体（非 Times New Roman）"
echo "  - 落款：日期右空四字、署名与其居中对齐"
echo "  - 版记（抄送/印发）以浮动表锚定版心底部；注意 LibreOffice"
echo "    可能不渲染该浮动表，需在 Word/WPS 中最终确认。"
ls -1 "$OUT"/*.png 2>/dev/null || true
