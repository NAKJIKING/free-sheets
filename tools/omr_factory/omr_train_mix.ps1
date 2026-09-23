# 관문 3a 재시도 감독기 — 구(omr_lines)·신(omr_lines3a) 혼합 학습.
#   구 코퍼스는 신 코퍼스에 전부 포함돼 있으므로(43,523줄 동일 확인) 혼합의
#   실효는 구 분포 2:1 과표집 — 셋잇단 비중 14.4%→7.7% 희석으로 실물 회귀
#   (길이 오독으로 새는 셋잇단 토큰)를 누르는 게 목적이다.
#   레시피는 3a와 동일(g4 부분 이식, photo 0.5 s1.25, lr 1e-4), 에폭만
#   5로 조정(78,078줄×5 ≈ 3a의 45k×8 표본 노출량).
#   끝나면 4종 평가: 셋잇단 / 관문1 / 캐논 실물(auto·켬·끔) / 모의 v2.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'
Set-Location C:\Users\user\free-sheets
$LOG = 'C:\Users\user\omr_pipeline_mix.log'
$TL  = 'C:\Users\user\omr_model_mix\train_log.jsonl'
$EPOCHS = 5

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
    Log "=== mix supervisor try=$try last_epoch=$before batch=4 photo=0.5 s=1.25 resume ==="
    cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data C:/Users/user/omr_lines,C:/Users/user/omr_lines3a --out C:/Users/user/omr_model_mix --epochs $EPOCHS --batch 4 --aug 0.35 --photo-aug 0.5 --photo-s 1.25 --lr 1e-4 --workers 2 --init-partial C:/Users/user/omr_model_g4/best.pt --resume >> C:\Users\user\omr_pipeline_mix.log 2>&1"
    $rc = $LASTEXITCODE
    $after = LastEpoch
    Log "mix supervisor try=$try rc=$rc epoch $before -> $after"
    if ($rc -eq 0 -and $after -ge ($EPOCHS - 1)) { break }
    if ($after -gt $before) { $stall = 0 } else { $stall++ }
    if ($stall -ge 3) { Log "PIPELINE_FAIL no-progress x3 (epoch=$after)"; exit 3 }
    Start-Sleep -Seconds 10
}

Log '=== mix stage5 evaluate(셋잇단: 3a 시험셋) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3a --model C:/Users/user/omr_model_mix --out C:/Users/user/omr_gate3a_mix --workers 2 >> C:\Users\user\omr_pipeline_mix.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_3a rc=$LASTEXITCODE"; exit 3 }
Log '=== mix stage5b evaluate(관문1 회귀: 구데이터) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model C:/Users/user/omr_model_mix --out C:/Users/user/omr_gate1_mix --workers 2 >> C:\Users\user\omr_pipeline_mix.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g1 rc=$LASTEXITCODE"; exit 3 }
Log '=== mix stage5c evaluate_duet(관문2 회귀: 캐논 실물 auto) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model C:/Users/user/omr_model_mix --out C:/Users/user/omr_gate2_canon_mix --auto >> C:\Users\user\omr_pipeline_mix.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2 rc=$LASTEXITCODE"; exit 3 }
Log '=== mix stage5d evaluate_duet(캐논 실물 보정 켬) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model C:/Users/user/omr_model_mix --out C:/Users/user/omr_gate2_canon_mix_on >> C:\Users\user\omr_pipeline_mix.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2on rc=$LASTEXITCODE"; exit 3 }
Log '=== mix stage5e evaluate_duet(캐논 실물 보정 끔) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model C:/Users/user/omr_model_mix --out C:/Users/user/omr_gate2_canon_mix_off --no-correct >> C:\Users\user\omr_pipeline_mix.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2off rc=$LASTEXITCODE"; exit 3 }
Log '=== mix stage5f evaluate_photo(모의 v2) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_photo.py --photos C:/Users/user/omr_photo_mock2 --model C:/Users/user/omr_model_mix --out C:/Users/user/omr_gate2_mock2_mix >> C:\Users\user\omr_pipeline_mix.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_mock rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
