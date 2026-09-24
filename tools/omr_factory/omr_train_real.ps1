# 실물 포함 미세조정 감독기 — 관문 2 실물 간극 해소 본선.
#   데이터: omr_lines3a + 실물 코퍼스(omr_real_lines) ×12 과표집.
#   ch2 best 에서 lr 5e-5·4에폭, photo-aug 0.5(합성 줄만 — real 줄은 증강 없음).
#   best.pt 는 **실물 검증 NER**(val 시트 04·07·14 촬영본)로 고른다.
#   끝나면 4종 평가: 셋잇단 / 관문1 / 캐논 실물 auto / 모의 v2.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'
Set-Location C:\Users\user\free-sheets
$LOG = 'C:\Users\user\omr_pipeline_real.log'
$OUT = 'C:\Users\user\omr_model_real'
$TL  = "$OUT\train_log.jsonl"
$EPOCHS = 4
$REAL = 'C:/Users/user/omr_real_lines'
$DATA = 'C:/Users/user/omr_lines3a,' + (@($REAL) * 12 -join ',')

function LastEpoch {
    if (-not (Test-Path $TL)) { return -1 }
    $line = Get-Content $TL -Tail 1
    if (-not $line) { return -1 }
    try { return ([int](($line | ConvertFrom-Json).epoch)) } catch { return -1 }
}
function Log($m) {
    $s = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $m`r`n"
    [System.IO.File]::AppendAllText($LOG, $s, (New-Object System.Text.UTF8Encoding($false)))
}

# 어휘를 ch2 것으로 고정 — 과표집 카운트가 정렬 순서를 흔들면 --init 행 매핑이
# 어긋난다. --resume 이 기존 vocab.json 을 읽는 성질을 이용해 미리 복사.
New-Item -ItemType Directory -Force $OUT | Out-Null
if (-not (Test-Path "$OUT\vocab.json")) {
    Copy-Item C:\Users\user\omr_model_ch2\vocab.json "$OUT\vocab.json"
}

$stall = 0
$try = 0
while ($true) {
    $free = [math]::Floor((Get-PSDrive C).Free/1GB)
    if ($free -lt 5) { Log "DISK_HALT free=${free}GB"; exit 2 }
    $before = LastEpoch
    if ($before -ge ($EPOCHS - 1)) { break }
    $try++
    Log "=== real supervisor try=$try last_epoch=$before lr=5e-5 ep=$EPOCHS resume ==="
    cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data $DATA --out $OUT --epochs $EPOCHS --batch 4 --aug 0.35 --photo-aug 0.5 --photo-s 1.25 --lr 5e-5 --workers 2 --init C:/Users/user/omr_model_ch2/best.pt --resume >> $LOG 2>&1"
    $rc = $LASTEXITCODE
    $after = LastEpoch
    Log "real supervisor try=$try rc=$rc epoch $before -> $after"
    if ($rc -eq 0 -and $after -ge ($EPOCHS - 1)) { break }
    if ($after -gt $before) { $stall = 0 } else { $stall++ }
    if ($stall -ge 3) { Log "PIPELINE_FAIL no-progress x3 (epoch=$after)"; exit 3 }
    Start-Sleep -Seconds 10
}

Log '=== real stage5 evaluate(셋잇단: 3a 시험셋) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3a --model $OUT --out C:/Users/user/omr_gate3a_real --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_3a rc=$LASTEXITCODE"; exit 3 }
Log '=== real stage5b evaluate(관문1 회귀: 구데이터) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model $OUT --out C:/Users/user/omr_gate1_real --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g1 rc=$LASTEXITCODE"; exit 3 }
Log '=== real stage5c evaluate_duet(관문2: 캐논 실물 auto) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model $OUT --out C:/Users/user/omr_gate2_canon_real --auto >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2 rc=$LASTEXITCODE"; exit 3 }
Log '=== real stage5d evaluate_photo(모의 v2) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_photo.py --photos C:/Users/user/omr_photo_mock2 --model $OUT --out C:/Users/user/omr_gate2_mock2_real >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_mock rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
