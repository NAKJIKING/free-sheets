# ④학습 감독기 v2 — 진전 기반 재시도. 커밋 비대로 인한 주기적 크래시를 전제로 설계.
#   에폭이 전진하는 한 무한 재시작(--resume, 프로세스 교체로 커밋 리셋).
#   3회 연속 무진전 또는 디스크 5GB 미만이면 중단. 40에폭 도달 시 ⑤평가.
#   파이썬 출력은 cmd 경유로 리다이렉트한다 — PS5.1 의 >> 는 UTF-16 을 써서 로그를 깨뜨린다.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'   # 커밋 비대 방지 — 2에폭마다 프로세스 교체(train.py 참고)
Set-Location C:\Users\user\free-sheets
$PY = '.venv\Scripts\python.exe'
$LOG = 'C:\Users\user\omr_pipeline.log'
$TL  = 'C:\Users\user\omr_model\train_log.jsonl'

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
    if ($before -ge 39) { break }
    $try++
    Log "=== stage4 supervisor try=$try last_epoch=$before batch=4 workers=2 resume ==="
    cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data C:/Users/user/omr_lines --out C:/Users/user/omr_model --epochs 40 --batch 4 --aug 0.35 --workers 2 --resume >> C:\Users\user\omr_pipeline.log 2>&1"
    $rc = $LASTEXITCODE
    $after = LastEpoch
    Log "supervisor try=$try rc=$rc epoch $before -> $after"
    if ($rc -eq 0 -and $after -ge 39) { break }
    if ($after -gt $before) { $stall = 0 } else { $stall++ }
    if ($stall -ge 3) { Log "PIPELINE_FAIL no-progress x3 (epoch=$after)"; exit 3 }
    Start-Sleep -Seconds 10
}

$free = [math]::Floor((Get-PSDrive C).Free/1GB)
if ($free -lt 5) { Log "DISK_HALT free=${free}GB"; exit 2 }
Log '=== stage5 evaluate ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model C:/Users/user/omr_model --out C:/Users/user/omr_gate1 --workers 2 >> C:\Users\user\omr_pipeline.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
