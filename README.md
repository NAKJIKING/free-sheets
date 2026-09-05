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
- `grade_levels.py` — 난이도 등급(`level`) 자동 분류. 특징값 캐시는
  `level_features.json` (아래 '난이도 등급' 절)
- `raw/original/` — **내 악보함이 직접 조판한 초급 단선율 악보** (한글 제목·계이름,
  LilyPond 소스는 `tools/original_src/`; 아래 '직접 조판 초급판' 절)
- `tools/mutopia_ly/` — Mutopia 의 LilyPond 소스를 직접 컴파일해 PDF·MIDI 를 만드는
  일괄 도구 (mutopiaproject.org 가 막힌 환경에서 GitHub 소스로 수집)
- `blocked_session_tunes.txt` — 작곡가가 특정되는 세션 튠 제외 목록
- `blocked_pdmx_composers.txt` — PD 판정을 통과하지 못한 PDMX 작곡가 표기
- `저작권_조사보고서.md` — 소스별 라이선스 조건 및 법적 근거 조사 보고서

## 직접 조판 초급판 (source = original)

초등 저학년용으로 유명한 주제 선율을 **한 줄 악보 + 한글 계이름**으로 직접
조판한 것. 원곡 선율은 모두 퍼블릭 도메인이고 조판은 우리 것이라 라이선스가
깨끗하다 — 원본 음표를 Mutopia 의 PD 판본에서 뽑은 곡은 CC0, CC BY-SA 판본에서
뽑은 곡(도나우·즐거운 농부·신세계 라르고)은 같은 CC BY-SA 로 표기한다.

- 소스: `tools/original_src/<id>.ly` (LilyPond 2.24). 렌더는
  `lilypond -o out <id>.ly` → PDF·MIDI, 썸네일은 PyMuPDF 로 1쪽을 340×480 WebP.
- 생성기: `tools/original_src/melody_sheet.py` — Mutopia 소스를 컴파일한 MIDI 에서
  선율 트랙을 뽑아(최고음 단선율화, 1/16 양자화, 꾸밈음 제거, 마디 분할·붙임줄,
  조성별 임시표 철자) 한글 제목·계이름이 붙은 .ly 를 만든다. 곡별 설정은
  `cfg1.json`(트랙·마디 범위·조옮김·못갖춘마디), 카탈로그 항목은 `originals_meta.py`.
- 카탈로그: `source: "original"`, `instrument: "Piano"`(오른손·리코더·멜로디언 겸용),
  `alias` 에 한글 제목, `level` 은 만들 때 정한 값을 `grade_levels.py` 가 그대로 둔다.
- 검수: 렌더 PNG 를 눈으로 원본과 대조했다. 원본이 복잡해 자동 축약이 깨진 곡
  (G선상의 아리아)은 싣지 않았다.

### 악기별 · 언어별 판

같은 선율을 **9개 악기**(피아노·리코더·바이올린·플루트·클라리넷·트럼펫·
알토색소폰·첼로·기타)로 옮겨 조·음역·조옮김 기보를 악기에 맞춘다. 클라리넷·
트럼펫은 B♭, 알토색소폰은 E♭ 이조 기보라 악보에 적힌 음을 불면 실음이 맞고,
미디는 실음으로 울린다. 조는 `inst_sheet.choose_shift` 가 음역 이탈·임시표 수·
음역 중심·그 악기가 편한 조를 점수로 따져 고른다.

악보에 인쇄되는 **큰 제목은 원제로 고정**하고, 그 아래 작은 줄(그 나라 말 제목 ·
곡 정보)과 악기 이름만 **8개 언어**(한국어·영어·독일어·프랑스어·스페인어·
포르투갈어·인도네시아어·중국어)로 따로 찍는다. 카탈로그 항목의 `langs`
(언어 코드 → 파일 경로)에 한국어 외 판의 경로가 들어 있고, 앱은 지금 언어에
맞는 파일을 받는다(없으면 `file`). **언어를 더해도 앱을 고칠 필요가 없다.**

 · 파일 경로: 한국어판 `raw/original/<악기>/<id>.pdf`,
   그 밖 `raw/original/<악기>/<언어>/<id>.pdf`
 · 미디·썸네일은 언어와 무관하므로 악기당 하나(`mids/original/<악기>/<id>.mid`)
 · 폰트는 나눔고딕 한 벌(한글+유럽문자) — 한 장 45KB. 중국어판만 한자 폰트
   때문에 210KB 다.
 · 제목 번역은 `tools/original_src/i18n.json`. 나라마다 통용되는 제목을 쓴다
   (Für Elise 는 독·프·스 그대로, 중국만 致爱丽丝).
 · 전체 다시 만들기: `python3 tools/original_src/build_all.py --write`
   (74곡 × 9악기 × 8언어 = 5,328장, 4코어 30분)

## 난이도 등급 (level)

앱의 무료 라이브러리 화면은 악기 칩 아래에 **초급 · 중급 · 고급** 칩을
두고, 곡마다 작은 등급 배지를 붙인다. 그 값이 `catalog.json` 의 `level`
이다 — `1` 초급(초등 1~3학년), `2` 중급(초등 4~6학년), `3` 고급(중학
이상). 판단 근거가 없는 곡은 `level` 이 없고(미분류) 앱에서는 등급 칩
'전체'에서만 보인다.

`grade_levels.py` 가 매 실행마다 전부 새로 계산한다(멱등). 판정 순서:

1. **작곡가·작품번호·제목 규칙** — 교육 과정에서 자리가 정해진 곡들.
   바이엘·체르니 100번(Op.139/599/821)·안나 막달레나 소품 → 초급,
   부르크뮐러 25(Op.100)·클레멘티·쿨라우 소나티네·바흐 인벤션·슈만
   유겐트 앨범 → 중급, 쇼팽·리스트·베토벤 소나타·협주곡·에튀드·
   현악사중주 → 고급. 규칙은 스크립트 안 `rule_level()` 에 코드로 있다.
2. **미디 특징값 점수** — 초당 타건 수·16분음표 비율·화음 두께·음역·
   조 밖 음(임시표) 비율·길이·옥타브 도약을 악기군(건반/기타/선율
   악기/가곡/찬송가/민속곡)마다 다른 기준으로 더해 세 단계로 자른다.
   선율 악기는 반주 트랙을 빼고 독주 트랙만 본다.
3. **작곡가 성향 기본값** — 미디가 없으면 비르투오소 작곡가 고급, 교재
   작곡가 중급, 전통곡 초급.

미디 특징값은 `level_features.json` 에 캐시해 두어, 미디 파일이 이
저장소에 없는 곡(2권 `free-sheets-2`)도 CI 에서 같은 결과가 난다.
2권 미디를 새로 넣었으면 `python3 grade_levels.py --mids <free-sheets-2 클론>`
으로 한 번 계산해 캐시를 갱신한다. 규칙을 고친 뒤에는
`python3 grade_levels.py --dry --sample 8` 로 악기·등급별 표본을 먼저 보고
커밋한다. 수집 워크플로들은 커밋 직전에 이 스크립트를 돌려 새 곡에도
등급이 붙게 한다.

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
  composers whose works are unambiguously out of copyright. Uploader-typed
  "Traditional"/"Anonymous" is **not** accepted as evidence — sampling found
  modern arrangements filed under it. Per-song license strings come from the
  uploader's MuseScore declaration, which we do not independently verify.
  https://github.com/pnlong/PDMX
- **Internet Archive** — scans of 19th–early-20th-century method books
  and editions marked public domain. Composer attributions are checked
  against each item's own `creator` metadata (first-listed author), because
  searching by a name also returns editions that person merely edited.
  https://archive.org

## 저작권 정책 / Takedown

퍼블릭 도메인 판별은 한국·EU(사후 70년)와 미국(1930년 이전 발행)
기준을 함께 적용합니다. 2026-07 전수 점검에서 권리 관계를 확인할 수
없는 곡을 모두 제외했습니다 — **18,093 → 11,153곡**.

 · 작곡가가 표기된 현대 세션 튠 1,715곡 (전통곡이 아니다)
 · 업로더가 'Traditional'·'Anonymous' 라고만 적은 곡 4,749곡
   (표본에서 현대 편곡·팝 편곡이 나왔다 — 표기는 증거가 아니다)
 · 작곡가 이름을 문자열 부분일치로 찾다 통과한 곡 713곡
   ('dont know'→Jakob Dont, 'Lalo Schifrin'→Édouard Lalo)
 · 악보가 아닌 학술 자료 46곡 · 편곡자 권리가 남은 판본 · 사후
   70년 미경과 작곡가의 곡 · 원본 메타데이터로 작곡가를 확인하지
   못한 교본 104곡

점검 규칙은 이름 목록이 아니라 **코드**로 남겨 두어 이후 수집분에도
자동으로 적용되고, `check_catalog.py` 가 규칙 누수를 CI에서 막습니다
(목록만 있고 검증이 없던 시절 52건 중 13건이 그대로 실려 있었습니다).

권리자로서 이의가 있는 곡이 있다면 GitHub 이슈로 곡 제목과 근거를
알려주세요. 확인 즉시 카탈로그와 저장소에서 내리겠습니다.
If you are a rights holder and believe a score here infringes your
copyright, please open a GitHub issue — we will remove it promptly.

## 입문 단선율 2차분 (2026-09-05, source = original)

기존 74곡에 더해 **24곡**을 같은 방식으로 조판했다. 딥서치로 카탈로그
12,663곡을 훑어 "선율만 뽑으면 입문이 되는 곡" 1,011개를 추린 뒤,
한국에서 통하는 유명 선율과 입문 교재 수록곡만 남긴 것이다.

- 유명 선율: 캉캉 · 기쁘다 구주 오셨네 · 어메이징 그레이스 · 내 주를 가까이 ·
  만세 반석 · 그 첫 성탄 · 올드 랭 사인 · 수오 간 · 물은 넓어라 ·
  캠프타운 경마 · 켄터키 옛집 · 짐노페디 2번 · 베토벤 론도/호숫가에서
- 입문 교재: 바이엘 Op.101 · 구를리트 소나티네 · 레이너글 알레그로 ·
  스트레아보그 회전목마 왈츠 · 스핀들러 무언가 · 베어 5월에 ·
  체르니 Op.139 No.1·No.2, 100번 소품 · 바흐 폴로네즈 BWV Anh.117a
- 원본은 전부 CC0·퍼블릭도메인(PDMX / Open Hymnal / The Session / Mutopia)
  이라 조판본도 CC0. CC BY-SA 원본은 쓰지 않았다.
- 설정·메타는 `tools/original_src/cfg_new2026.json`, `meta_new2026.json`,
  번역은 `i18n.json` 에 합쳐 넣었다.

### 이번에 고친 도구 문제 (다음 사람이 또 밟지 않도록)

- **경로 하드코딩** — `melody_sheet.LP` 가 특정 세션의 스크래치패드 경로,
  `FS` 가 `/home/user/free-sheets` 로 박혀 있어 다른 PC 에서 못 돌았다.
  이제 `LILYPOND`/`FREE_SHEETS_ROOT` 환경변수 → `PATH` → 파일 위치 순으로 찾는다.
- **미디 상대경로** — 설정의 `midi` 가 상대경로면 저장소 루트 기준으로 푼다
  (`melody_sheet._midi_path`). 예전엔 실행 위치에 따라 실패했다.
- **선율 트랙 오선택** — `auto_theme.pick_track` 이 화성 비율 높은 트랙을
  뒤로 밀어 반주(베이스)를 선율로 잡는 일이 있었다(짐노페디 2번은 평균
  음고 40, 체르니 Op.139-1 은 왼손). 선율 추출이 이미 화음의 윗음만
  가져가므로 그 벌점을 없애고 '평균 음고가 가장 높은 트랙'으로 바꿨다.
- **`--only` + `--write` 가 카탈로그를 지우던 것** — original 항목을 통째로
  비우고 다시 채워서, 몇 곡만 빌드하면 나머지 자체 조판 곡이 목록에서
  사라졌다(파일은 남아 눈치채기 어렵다). 이제 빌드한 곡의 항목만 교체한다.

### 렌더 환경

LilyPond 2.24.4 가 필요하다(템플릿이 `\version "2.24.4"`). 우분투 apt 판은
2.24.3 이라 거부당한다 — GitLab 릴리스의 정적 바이너리를 쓸 것:
`https://gitlab.com/lilypond/lilypond/-/releases/v2.24.4/downloads/lilypond-2.24.4-linux-x86_64.tar.gz`
썸네일에는 PyMuPDF(`pip install pymupdf`)와 Pillow 가 필요하다.
