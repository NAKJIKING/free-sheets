# 관문 3b 학습 감독기 — 도돌이·볼타 코퍼스(omr_lines3b) + 실물 코퍼스 유지.
#   omr_model_real best 에서 --init-partial(신규 구조 토큰 4행 초기화),
#   lr 7e-5·6에폭, best 는 실물 검증 NER. 끝나면 판정·회귀 평가 6종:
#   구조(eval_structure) / 3b 전체 / 셋잇단 회귀(3a 시험셋) / 관문1 / 캐논 auto / 모의 v2.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'
Set-Location C:\Users\user\free-sheets
$LOG = 'C:\Users\user\omr_pipeline_gate3b.log'
$OUT = 'C:\Users\user\omr_model_3b2'
$TL  = "$OUT\train_log.jsonl"
$EPOCHS = 6
$REAL = 'C:/Users/user/omr_real_lines'
$DATA = 'C:/Users/user/omr_lines3b,' + (@($REAL) * 12 -join ',')

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
    Log "=== gate3b supervisor try=$try last_epoch=$before lr=7e-5 ep=$EPOCHS resume ==="
    cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data $DATA --out $OUT --epochs $EPOCHS --batch 4 --aug 0.35 --photo-aug 0.5 --photo-s 1.25 --lr 7e-5 --workers 2 --init-partial C:/Users/user/omr_model_real/best.pt --resume >> $LOG 2>&1"
    $rc = $LASTEXITCODE
    $after = LastEpoch
    Log "gate3b supervisor try=$try rc=$rc epoch $before -> $after"
    if ($rc -eq 0 -and $after -ge ($EPOCHS - 1)) { break }
    if ($after -gt $before) { $stall = 0 } else { $stall++ }
    if ($stall -ge 3) { Log "PIPELINE_FAIL no-progress x3 (epoch=$after)"; exit 3 }
    Start-Sleep -Seconds 10
}

Log '=== gate3b stage5 eval_structure(3b 판정: 구조·전개) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\eval_structure.py --data C:/Users/user/omr_lines3b --model $OUT --out C:/Users/user/omr_gate3b_struct >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_struct rc=$LASTEXITCODE"; exit 3 }
Log '=== gate3b stage5b evaluate(3b 시험셋 전체 NER) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3b --model $OUT --out C:/Users/user/omr_gate3b_full --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_full rc=$LASTEXITCODE"; exit 3 }
Log '=== gate3b stage5c evaluate(셋잇단 회귀: 3a 시험셋) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3a --model $OUT --out C:/Users/user/omr_gate3a_3b2 --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_3a rc=$LASTEXITCODE"; exit 3 }
Log '=== gate3b stage5d evaluate(관문1 회귀: 구데이터) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model $OUT --out C:/Users/user/omr_gate1_3b2 --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g1 rc=$LASTEXITCODE"; exit 3 }
Log '=== gate3b stage5e evaluate_duet(관문2 회귀: 캐논 auto) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model $OUT --out C:/Users/user/omr_gate2_canon_3b2 --auto >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2 rc=$LASTEXITCODE"; exit 3 }
Log '=== gate3b stage5f evaluate_photo(모의 v2) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_photo.py --photos C:/Users/user/omr_photo_mock2 --model $OUT --out C:/Users/user/omr_gate2_mock2_3b2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_mock rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
