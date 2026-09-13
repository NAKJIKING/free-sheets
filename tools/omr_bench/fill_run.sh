#!/bin/bash
# 2단계 인식 실행기 — 몇 번을 다시 돌려도 이어서 간다 (이미 된 곡은 건너뜀).
# 사용: AV=<Audiveris실행파일> TESS=<tessdata폴더> OUT=<출력폴더> bash fill_run.sh
AV=${AV:-/tmp/omr-baseline/av/opt/audiveris/bin/Audiveris}
TESS=${TESS:-/tmp/omr-baseline/tessdata}
OUT=${OUT:-/tmp/fill_out}
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$OUT"
python3 - <<PY > /tmp/fill_queue.txt
import json,os,re
t=json.load(open('$ROOT/tools/omr_bench/fill_targets.json'))
def pages(p):
    d=open(p,'rb').read(); m=re.findall(rb'/Count\s+(\d+)',d)
    return max((int(x) for x in m),default=1) if d.startswith(b'%PDF-') else 999
rows=sorted((os.path.getsize(os.path.join('$ROOT',e['file'])), e['file'])
            for e in t if pages(os.path.join('$ROOT',e['file']))<=10)
print('\n'.join(f for _,f in rows))
PY
n=0
while read -r rel; do
  f="$ROOT/$rel"; b=$(basename "$f" .pdf); n=$((n+1))
  ls "$OUT/$b".mxl "$OUT/$b".mvt*.mxl >/dev/null 2>&1 && continue
  JAVA_TOOL_OPTIONS= TESSDATA_PREFIX="$TESS" timeout 1200 \
    "$AV" -batch -export -swap -output "$OUT" "$f" >> /tmp/fill_run.log 2>&1 \
    || echo "$b" >> /tmp/fill_fail.txt
  echo "$n곡 시도, mxl $(ls "$OUT"/*.mxl 2>/dev/null|wc -l)개" > /tmp/fill_prog.txt
done < /tmp/fill_queue.txt
echo "완료" >> /tmp/fill_prog.txt
