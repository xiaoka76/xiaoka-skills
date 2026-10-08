#!/usr/bin/env bash
# 一键跑 seedream-image 的全部验收（零成本：不调用真实 API）
set -u
cd "$(dirname "$0")"
fail=0
for f in verify_tags.py verify_cli.py verify_mark.py; do
    echo "════════ $f ════════"
    python3 "$f" || fail=1
done
echo
[ "$fail" = 0 ] && echo "✅ 全部通过" || echo "❌ 有失败项"
exit $fail
