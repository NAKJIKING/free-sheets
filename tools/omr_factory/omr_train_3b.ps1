# 관문 2 미세조정 2차 감독기 — g2 best 에서 더 강한 사진 증강(리샘플 체인
#   포함, photo-s 1.25·확률 0.5)으로 6에폭. 끝나면 캐논 실물·모의·렌더 3종 평가.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'
Set-Location C:\Users\user\free-sheets
$LOG = 'C:\Users\user\omr_pipeline_3b.log'
$TL  = 'C:\Users\user\omr_model_3b\train_log.jsonl'
$EPOCHS = 3

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
    Log "=== 3b supervisor try=$try last_epoch=$before batch=4 photo=0.5 s=1.25 resume ==="
    cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data C:/Users/user/omr_lines3a --out C:/Users/user/omr_model_3b --epochs $EPOCHS --batch 4 --aug 0.35 --photo-aug 0.6 --photo-s 1.25 --lr 4e-5 --workers 2 --init C:/Users/user/omr_model_3a/best.pt --resume >> C:\Users\user\omr_pipeline_3b.log 2>&1"
    $rc = $LASTEXITCODE
    $after = LastEpoch
    Log "3b supervisor try=$try rc=$rc epoch $before -> $after"
    if ($rc -eq 0 -and $after -ge ($EPOCHS - 1)) { break }
    if ($after -gt $before) { $stall = 0 } else { $stall++ }
    if ($stall -ge 3) { Log "PIPELINE_FAIL no-progress x3 (epoch=$after)"; exit 3 }
    Start-Sleep -Seconds 10
}

Log '=== 3b stage5 evaluate(3a판정: 셋잇단 포함 시험셋) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3a --model C:/Users/user/omr_model_3b --out C:/Users/user/omr_gate3b --workers 2 >> C:\Users\user\omr_pipeline_3b.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_3b rc=$LASTEXITCODE"; exit 3 }
Log '=== 3b stage5b evaluate(관문1 회귀: 구데이터) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model C:/Users/user/omr_model_3b --out C:/Users/user/omr_gate1_3b --workers 2 >> C:\Users\user\omr_pipeline_3b.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g1 rc=$LASTEXITCODE"; exit 3 }
Log '=== 3b stage5c evaluate_duet(관문2 회귀: 캐논 실물 auto) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model C:/Users/user/omr_model_3b --out C:/Users/user/omr_gate2_canon_3b --auto >> C:\Users\user\omr_pipeline_3b.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2 rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
