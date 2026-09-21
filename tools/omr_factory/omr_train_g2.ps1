# 관문 2 미세조정 감독기 — omr_train2.ps1 과 같은 설계(진전 기반 재시도).
#   best.pt(관문 1)에서 시작해 사진 증강(--photo-aug 0.4, 300DPI 원본 경로)으로
#   8에폭 미세조정. best.pt 선택 기준은 사진 검증 NER.
#   끝나면 ⑤ 모의 사진 평가(evaluate_photo) + 깨끗한 렌더 회귀 검사(evaluate).
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'   # 커밋 비대 방지 — 에폭마다 프로세스 교체
Set-Location C:\Users\user\free-sheets
$PY = '.venv\Scripts\python.exe'
$LOG = 'C:\Users\user\omr_pipeline_g2.log'
$TL  = 'C:\Users\user\omr_model_g2\train_log.jsonl'
$EPOCHS = 8

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
    Log "=== g2 supervisor try=$try last_epoch=$before batch=4 photo=0.4 resume ==="
    cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data C:/Users/user/omr_lines --out C:/Users/user/omr_model_g2 --epochs $EPOCHS --batch 4 --aug 0.35 --photo-aug 0.4 --lr 1e-4 --workers 2 --init C:/Users/user/omr_model/best.pt --resume >> C:\Users\user\omr_pipeline_g2.log 2>&1"
    $rc = $LASTEXITCODE
    $after = LastEpoch
    Log "g2 supervisor try=$try rc=$rc epoch $before -> $after"
    if ($rc -eq 0 -and $after -ge ($EPOCHS - 1)) { break }
    if ($after -gt $before) { $stall = 0 } else { $stall++ }
    if ($stall -ge 3) { Log "PIPELINE_FAIL no-progress x3 (epoch=$after)"; exit 3 }
    Start-Sleep -Seconds 10
}

$free = [math]::Floor((Get-PSDrive C).Free/1GB)
if ($free -lt 5) { Log "DISK_HALT free=${free}GB"; exit 2 }
Log '=== g2 stage5 evaluate_photo(mock) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_photo.py --photos C:/Users/user/omr_photo_mock --model C:/Users/user/omr_model_g2 --out C:/Users/user/omr_gate2_mock >> C:\Users\user\omr_pipeline_g2.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_photo rc=$LASTEXITCODE"; exit 3 }
Log '=== g2 stage5b evaluate(clean, 회귀 검사) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model C:/Users/user/omr_model_g2 --out C:/Users/user/omr_gate1_g2 --workers 2 >> C:\Users\user\omr_pipeline_g2.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_clean rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
