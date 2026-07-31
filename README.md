# free-sheets — My Sheet Music 무료 악보 라이브러리

**내 악보함(My Sheet Music)** 앱의 무료 악보 라이브러리입니다.
저작권이 만료됐거나(퍼블릭 도메인) 재배포가 허용된 자유 라이선스
(CC0, CC BY, CC BY-SA, ODbL 등)로 공개된 악보만 담는 것이 원칙입니다.

다만 `catalog.json`의 `license` 값은 **원 출처가 표기한 값을 그대로
옮긴 것**이며, 저장소가 곡마다 권리 관계를 검증했다는 보증이 아닙니다.
출처가 잘못 표기해 넘어온 곡이 섞일 수 있어 정기 점검
(`sanitize_catalog.py`)으로 걸러내고 있으며, 남은 오표기는 아래
Takedown 절차로 즉시 내립니다.

## 구성

- `catalog.json` — 전체 곡 목록 (제목·작곡가·악기·라이선스·출처 URL)
- `raw/mutopia/<악기>/` — [Mutopia Project](https://www.mutopiaproject.org)
  수집분 (퍼블릭 도메인 / CC 라이선스, 곡별 라이선스는 카탈로그와 악보 하단 표기 참조)
- `raw/openscore_lieder/` — [OpenScore Lieder Corpus](https://github.com/OpenScore/Lieder)
  수집분 (**CC0** — 조건 없는 퍼블릭 도메인 헌정)
- `collect.py`, `collect_lieder.py` — 자동 수집 스크립트 (GitHub Actions로 실행)
- `sanitize_catalog.py` — 저작권·품질 점검 필터 (병합 뒤 항상 실행)
- `blocked_session_tunes.txt` — 작곡가가 특정되는 세션 튠 제외 목록
- `blocked_pdmx_composers.txt` — PD 판정을 통과하지 못한 PDMX 작곡가 표기
- `저작권_조사보고서.md` — 소스별 라이선스 조건 및 법적 근거 조사 보고서

## 라이선스 / 저작자표시

- 이 저장소의 **악보 파일들**은 각 곡의 원 라이선스를 따릅니다.
  곡별 라이선스와 출처는 `catalog.json`에 기록되어 있으며,
  CC BY / CC BY-SA 곡은 악보 하단의 원 조판자 표기를 보존합니다.
  Mutopia 곡은 악보에 인쇄된 표기를 읽어 곡마다 PD / CC BY / CC BY-SA를
  따로 적어 두었습니다.
- **The Session** 유래 곡(`thesession`)의 선율 자체는 전통곡이지만,
  튠 데이터는 ODbL 1.0 데이터베이스에서 왔습니다 —
  *Tune data from thesession.org, © The Session contributors,
  licensed under ODbL 1.0.* 여기서 파생된 목록도 같은 조건으로 씁니다.
- 수집 스크립트(`*.py`)는 MIT 라이선스입니다.

## Sources & Credits

- **Mutopia Project** — thousands of freely redistributable editions,
  typeset by volunteers. Each piece's license is printed on the score itself.
  https://www.mutopiaproject.org
- **OpenScore Lieder Corpus** / **OpenScore String Quartets** — songs and
  quartets transcribed by contributors and professionally proofread,
  released under CC0. https://openscore.cc
- **The Session** — community database of traditional Irish tunes.
  Tune data © The Session contributors, made available under the
  [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
  Our derived tune list (the `thesession` rows of `catalog.json`) is
  likewise available under ODbL. https://thesession.org
- **Open Hymnal Project** — public-domain Christian hymns, ABC/MIDI
  editions. http://openhymnal.org
- **PDMX** — *PDMX: A Large-Scale Public Domain MusicXML Dataset for
  Symbolic Music Processing* (Phillip Long, Zachary Novack, Taylor
  Berg-Kirkpatrick, Julian McAuley). Dataset released under **CC BY 4.0**
  via Zenodo (DOI [10.5281/zenodo.13763756](https://doi.org/10.5281/zenodo.13763756));
  we use only the `no_license_conflict` subset, further restricted to
  composers whose works are unambiguously out of copyright (or traditional
  tunes). Per-song license strings come from the uploader's MuseScore
  declaration, which we do not independently verify.
  https://github.com/pnlong/PDMX
- **Internet Archive** — scans of 19th–early-20th-century method books
  and editions marked public domain. https://archive.org

## 저작권 정책 / Takedown

퍼블릭 도메인 판별은 한국·EU(사후 70년)와 미국(1930년 이전 발행)
기준을 함께 적용합니다. 2026-07 전수 점검에서 저작권 존속이
확인·의심되는 곡은 `sanitize_catalog.py`로 영구 제외했습니다 —
작곡가가 표기된 현대 세션 튠 1,715곡, 오표기된 영화·팝 편곡,
학술 논문 스캔 등 악보가 아닌 자료, 편곡자 권리가 남은 판본,
사후 70년이 지나지 않은 작곡가의 곡 등 총 2,031곡(18,093 → 16,062).
점검 규칙은 이름 목록이 아니라 코드로 남겨 두어 이후 수집분에도
자동으로 적용됩니다.

권리자로서 이의가 있는 곡이 있다면 GitHub 이슈로 곡 제목과 근거를
알려주세요. 확인 즉시 카탈로그와 저장소에서 내리겠습니다.
If you are a rights holder and believe a score here infringes your
copyright, please open a GitHub issue — we will remove it promptly.
