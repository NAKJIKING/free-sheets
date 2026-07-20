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
- **OpenScore Lieder Corpus** — 1,300+ songs transcribed by contributors and
  professionally proofread, released under CC0. https://openscore.cc
