# free-sheets — My Sheet Music 무료 악보 라이브러리

**내 악보함(My Sheet Music)** 앱의 무료 악보 라이브러리입니다.
모든 악보는 저작권이 만료되었거나(퍼블릭 도메인) 재배포가 허용된
자유 라이선스(CC0, CC BY, CC BY-SA 등)로 배포되는 곡만 수록합니다.

## 구성

- `catalog.json` — 전체 곡 목록 (제목·작곡가·악기·라이선스·출처 URL)
- `raw/mutopia/<악기>/` — [Mutopia Project](https://www.mutopiaproject.org)
  수집분 (퍼블릭 도메인 / CC 라이선스, 곡별 라이선스는 카탈로그와 악보 하단 표기 참조)
- `raw/openscore_lieder/` — [OpenScore Lieder Corpus](https://github.com/OpenScore/Lieder)
  수집분 (**CC0** — 조건 없는 퍼블릭 도메인 헌정)
- `collect.py`, `collect_lieder.py` — 자동 수집 스크립트 (GitHub Actions로 실행)
- `저작권_조사보고서.md` — 소스별 라이선스 조건 및 법적 근거 조사 보고서

## 라이선스 / 저작자표시

- 이 저장소의 **악보 파일들**은 각 곡의 원 라이선스를 따릅니다.
  곡별 라이선스와 출처는 `catalog.json`에 기록되어 있으며,
  CC BY / CC BY-SA 곡은 악보 하단의 원 조판자 표기를 보존합니다.
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
- **PDMX** (Long et al., ISMIR/IEEE) — large-scale dataset of
  public-domain/CC0-marked MuseScore scores; we use only the
  `no_license_conflict` subset, further restricted to composers whose
  works are unambiguously out of copyright (or traditional tunes).
  https://github.com/pnlong/PDMX
- **Internet Archive** — scans of 19th–early-20th-century method books
  and editions marked public domain. https://archive.org

## 저작권 정책 / Takedown

퍼블릭 도메인 판별은 한국(사후 70년)·미국(1930년 이전 발행) 기준을
함께 적용하며, 2026-07 전수 점검에서 저작권 존속이 확인·의심되는
곡(현대 작곡 세션 튠, 오표기된 영화·팝 편곡 등)은 `sanitize_catalog.py`
의 차단 목록으로 영구 제외했습니다.

권리자로서 이의가 있는 곡이 있다면 GitHub 이슈로 곡 제목과 근거를
알려주세요. 확인 즉시 카탈로그와 저장소에서 내리겠습니다.
If you are a rights holder and believe a score here infringes your
copyright, please open a GitHub issue — we will remove it promptly.
