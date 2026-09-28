# 관문 3c 폴리싱(3c4) — 실물 39줄 마커 라벨 보정 반영 + 3c3 에서 3에폭
#   저LR 미세조정. 목적: 캐논 3b2 대비 +0.62%p 격차 축소·라벨 일관화.
#   채택 조건: 캐논 auto ≤ 8.47%(3c3) 이면서 판정·회귀 유지 — 아니면 폐기.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'
Set-Location C:\Users\user\free-sheets
$LOG = 'C:\Users\user\omr_pipeline_3c4.log'
$OUT = 'C:\Users\user\omr_model_3c4'
$TL  = "$OUT\train_log.jsonl"
$EPOCHS = 3
$REAL = 'C:/Users/user/omr_real_lines'
$DATA = 'C:/Users/user/omr_lines3c,' + (@($REAL) * 12 -join ',')

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

$stall = 0
$try = 0
while ($true) {
    $free = [math]::Floor((Get-PSDrive C).Free/1GB)
    if ($free -lt 5) { Log "DISK_HALT free=${free}GB"; exit 2 }
    $before = LastEpoch
    if ($before -ge ($EPOCHS - 1)) { break }
    $try++
    Log "=== 3c4 supervisor try=$try last_epoch=$before lr=4e-5 ep=$EPOCHS resume ==="
    cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data $DATA --out $OUT --epochs $EPOCHS --batch 4 --aug 0.35 --photo-aug 0.5 --photo-s 1.25 --lr 4e-5 --workers 2 --init-partial C:/Users/user/omr_model_3c3/best.pt --resume >> $LOG 2>&1"
    $rc = $LASTEXITCODE
    $after = LastEpoch
    Log "3c4 supervisor try=$try rc=$rc epoch $before -> $after"
    if ($rc -eq 0 -and $after -ge ($EPOCHS - 1)) { break }
    if ($after -gt $before) { $stall = 0 } else { $stall++ }
    if ($stall -ge 3) { Log "PIPELINE_FAIL no-progress x3 (epoch=$after)"; exit 3 }
    Start-Sleep -Seconds 10
}

Log '=== 3c4 stage5 eval_3c(3c 판정: 마커×판독기 + 셈여림) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\eval_3c.py --data C:/Users/user/omr_lines3c --model $OUT --tempo-head C:/Users/user/omr_tempo_head --out C:/Users/user/omr_gate3c_4 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_3c rc=$LASTEXITCODE"; exit 3 }
Log '=== 3c4 stage5b evaluate(3c 시험셋 전체 NER) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3c --model $OUT --out C:/Users/user/omr_gate3c_full_4 --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_full rc=$LASTEXITCODE"; exit 3 }
Log '=== 3c4 stage5c eval_structure(3b 구조 회귀 + 전개 곡 추적 지표) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\eval_structure.py --data C:/Users/user/omr_lines3b --model $OUT --out C:/Users/user/omr_gate3b_struct_3c4 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_struct rc=$LASTEXITCODE"; exit 3 }
Log '=== 3c4 stage5d evaluate(셋잇단 회귀: 3a 시험셋) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3a --model $OUT --out C:/Users/user/omr_gate3a_3c4 --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_3a rc=$LASTEXITCODE"; exit 3 }
Log '=== 3c4 stage5e evaluate(관문1 회귀: 구데이터) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model $OUT --out C:/Users/user/omr_gate1_3c4 --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g1 rc=$LASTEXITCODE"; exit 3 }
Log '=== 3c4 stage5f evaluate_duet(관문2 회귀: 캐논 실물 auto) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model $OUT --out C:/Users/user/omr_gate2_canon_3c4 --auto >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2 rc=$LASTEXITCODE"; exit 3 }
Log '=== 3c4 stage5g evaluate_photo(모의 v2) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_photo.py --photos C:/Users/user/omr_photo_mock2 --model $OUT --out C:/Users/user/omr_gate2_mock2_3c4 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_mock rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
