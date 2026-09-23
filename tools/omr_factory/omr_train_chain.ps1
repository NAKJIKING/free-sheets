# 관문 3a 재시도 2차 감독기 — 미세조정 체인 재적용 가설.
#   가설: g4 의 실물 강점은 g3→g4 체인(7e-5·6ep → 5e-5·5ep, photo 0.5 s1.25)
#   에서 왔다. 같은 체인을 3b best 에서 재적용한다. 코퍼스는 omr_lines3a
#   (셋잇단 감독 유지 — 구데이터만 쓰면 신규 토큰 95행이 억압돼 셋잇단 회귀).
#   ch1 = 3b + 7e-5·6ep / ch2 = ch1 + 5e-5·5ep. 끝나면 4종 평가:
#   셋잇단 / 관문1 / 캐논 실물 auto / 모의 v2.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:OMR_EPOCHS_PER_RUN = '1'
Set-Location C:\Users\user\free-sheets
$LOG = 'C:\Users\user\omr_pipeline_chain.log'

function LastEpoch($tl) {
    if (-not (Test-Path $tl)) { return -1 }
    $line = Get-Content $tl -Tail 1
    if (-not $line) { return -1 }
    try { return ([int](($line | ConvertFrom-Json).epoch)) } catch { return -1 }
}
function Log($m) {
    $s = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $m`r`n"
    [System.IO.File]::AppendAllText($LOG, $s, (New-Object System.Text.UTF8Encoding($false)))
}

function RunStage($name, $out, $epochs, $lr, $init) {
    # 어휘를 3b 것으로 고정 — --resume 이 vocab.json 을 읽으므로 미리 복사.
    New-Item -ItemType Directory -Force $out | Out-Null
    if (-not (Test-Path "$out\vocab.json")) {
        Copy-Item C:\Users\user\omr_model_3b\vocab.json "$out\vocab.json"
    }
    $tl = "$out\train_log.jsonl"
    $stall = 0
    $try = 0
    while ($true) {
        $free = [math]::Floor((Get-PSDrive C).Free/1GB)
        if ($free -lt 5) { Log "DISK_HALT free=${free}GB"; exit 2 }
        $before = LastEpoch $tl
        if ($before -ge ($epochs - 1)) { break }
        $try++
        Log "=== $name supervisor try=$try last_epoch=$before lr=$lr ep=$epochs resume ==="
        cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\train.py --data C:/Users/user/omr_lines3a --out $out --epochs $epochs --batch 4 --aug 0.35 --photo-aug 0.5 --photo-s 1.25 --lr $lr --workers 2 --init $init --resume >> $LOG 2>&1"
        $rc = $LASTEXITCODE
        $after = LastEpoch $tl
        Log "$name supervisor try=$try rc=$rc epoch $before -> $after"
        if ($rc -eq 0 -and $after -ge ($epochs - 1)) { break }
        if ($after -gt $before) { $stall = 0 } else { $stall++ }
        if ($stall -ge 3) { Log "PIPELINE_FAIL $name no-progress x3 (epoch=$after)"; exit 3 }
        Start-Sleep -Seconds 10
    }
    Log "$name STAGE_DONE"
}

RunStage 'ch1' 'C:/Users/user/omr_model_ch1' 6 '7e-5' 'C:/Users/user/omr_model_3b/best.pt'
RunStage 'ch2' 'C:/Users/user/omr_model_ch2' 5 '5e-5' 'C:/Users/user/omr_model_ch1/best.pt'

Log '=== chain stage5 evaluate(셋잇단: 3a 시험셋) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines3a --model C:/Users/user/omr_model_ch2 --out C:/Users/user/omr_gate3a_ch2 --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_3a rc=$LASTEXITCODE"; exit 3 }
Log '=== chain stage5b evaluate(관문1 회귀: 구데이터) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate.py --data C:/Users/user/omr_lines --model C:/Users/user/omr_model_ch2 --out C:/Users/user/omr_gate1_ch2 --workers 2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g1 rc=$LASTEXITCODE"; exit 3 }
Log '=== chain stage5c evaluate_duet(관문2 회귀: 캐논 실물 auto) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_duet.py --photos C:/Users/user/omr_photo_canon --truth C:/Users/user/omr_dense/truth_canon.json --model C:/Users/user/omr_model_ch2 --out C:/Users/user/omr_gate2_canon_ch2 --auto >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_g2 rc=$LASTEXITCODE"; exit 3 }
Log '=== chain stage5d evaluate_photo(모의 v2) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\evaluate_photo.py --photos C:/Users/user/omr_photo_mock2 --model C:/Users/user/omr_model_ch2 --out C:/Users/user/omr_gate2_mock2_ch2 >> $LOG 2>&1"
if ($LASTEXITCODE -ne 0) { Log "PIPELINE_FAIL eval_mock rc=$LASTEXITCODE"; exit 3 }
Log 'PIPELINE_DONE'
exit 0
