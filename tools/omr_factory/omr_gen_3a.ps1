# 관문 3a 코퍼스 재생성 감독 스크립트 — 셋잇단 수용판을 omr_lines3a 로.
#   생성 → cache → split 까지 이어서 돌리고 단계마다 로그를 남긴다.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:LILYPOND = 'C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\LilyPond.LilyPond_Microsoft.Winget.Source_8wekyb3d8bbwe\lilypond-2.24.4\bin\lilypond.exe'
Set-Location C:\Users\user\free-sheets
$LOG = 'C:\Users\user\omr_gen_3a.log'
function Log($m) {
    $s = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $m`r`n"
    [System.IO.File]::AppendAllText($LOG, $s, (New-Object System.Text.UTF8Encoding($false)))
}
Log '=== 3a stage1 make_lib_lines (jobs 10) ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\make_lib_lines.py --out C:/Users/user/omr_lines3a --keys 3 --max-chunks 6 --jobs 10 >> C:\Users\user\omr_gen_3a.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "GEN_FAIL rc=$LASTEXITCODE"; exit 1 }
Log '=== 3a stage2 split ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\split.py --data C:/Users/user/omr_lines3a >> C:\Users\user\omr_gen_3a.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "SPLIT_FAIL rc=$LASTEXITCODE"; exit 1 }
Log '=== 3a stage3 cache ==='
cmd /c ".venv\Scripts\python.exe -u tools\omr_factory\cache.py --data C:/Users/user/omr_lines3a --jobs 10 >> C:\Users\user\omr_gen_3a.log 2>&1"
if ($LASTEXITCODE -ne 0) { Log "CACHE_FAIL rc=$LASTEXITCODE"; exit 1 }
Log 'GEN_DONE'
exit 0
