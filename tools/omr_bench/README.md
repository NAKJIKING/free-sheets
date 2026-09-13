# OMR 성능 측정 도구

인쇄·스캔 악보를 인식해 연주/반주하게 만드는 장기 과제의 **1단계 — 실력표 만들기**용.
"어떤 종류의 악보를 몇 점으로 읽는가"를 재서, 이후 모든 결정의 근거로 삼는다.
(배경과 계획은 `sheet_music_app/OMR_연구.md` 참조 — project-all 저장소)

## 왜 우리가 채점을 할 수 있는가

라이브러리에 **악보 PDF 와 정답 MIDI 를 둘 다 가진 곡이 약 7,000개** 있다.
둘은 같은 원본에서 나왔으므로 서로 어긋나지 않는다. 인식기를 악보에 돌려
그 MIDI 와 대조하면 **정답이 있는 채점**이 된다.

## 순서

```bash
# 1) 표본 뽑기 — 출처·성부 두께·쪽수로 고르게
python3 tools/omr_bench/pick_sample.py --n 300 -o tools/omr_bench/sample.json

# 2) 인식기 준비 (Audiveris 5.11.0, root 불필요 — JRE 내장이라 시스템 자바 무관)
curl -sSL -O https://github.com/Audiveris/audiveris/releases/download/5.11.0/Audiveris-5.11.0-ubuntu24.04-x86_64.deb
dpkg-deb -x Audiveris-*.deb av
mkdir -p tessdata && curl -sSL -o tessdata/eng.traineddata \
  https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/eng.traineddata
#   ⚠ tessdata_fast 는 안 된다 — Audiveris 가 legacy 엔진을 요구한다.
#   ⚠ 음표만 잴 거면 tessdata 없이도 된다(TEXTS 단계만 건너뜀).

# 3) 표본 PDF 를 한 폴더에 모아 한 번에 돌린다 (JVM 을 한 번만 띄워야 빠르다)
python3 - <<'PY'
import json,os,shutil
s=json.load(open('tools/omr_bench/sample.json')); os.makedirs('/tmp/omr_in',exist_ok=True)
for e in s: shutil.copy(e['file'], '/tmp/omr_in/'+os.path.basename(e['file']))
PY
JAVA_TOOL_OPTIONS= TESSDATA_PREFIX=$PWD/tessdata \
  ./av/opt/audiveris/bin/Audiveris -batch -export -swap -output /tmp/omr_out /tmp/omr_in/*.pdf

# 4) 채점
python3 tools/omr_bench/score_omr.py --sample tools/omr_bench/sample.json \
  --pred /tmp/omr_out -o tools/omr_bench/result.json
```

필요한 파이썬 패키지: `mido`, `music21`.

## 알고 들어가야 할 함정 (전부 실제로 겪은 것)

| 함정 | 증상 | 처리 |
|---|---|---|
| **카탈로그의 `instrument` 는 짜임새가 아니다** | 'Cello' 로 적힌 곡이 실제로는 5성부. 단선율만 재려다 합주곡만 재게 된다 | 성부 두께를 **MIDI 에서 직접** 잰다(`pick_sample.max_polyphony`) |
| **다악장** | Audiveris 가 한 PDF 를 `.mvt1`·`.mvt2` 로 쪼갠다. 악장 하나를 전곡과 대조하면 참담한 점수 | 악장을 이어 붙여 대조 |
| **다성부** | 성부를 한 줄로 눌러 순서 비교하면 작은 어긋남에 오류가 폭발 | **단선율만 편집거리로 채점**, 다성부는 개수·박자만 |
| **반복(도돌이표)** | MIDI 는 펼쳐 기록, 악보는 한 번만 인쇄 → 절반이 '빠뜨림'으로 잡힘 | `expandRepeats()` 와 AABB 등 흔한 구조 중 가장 맞는 것 |
| **정답이 악보와 범위가 다름** | 악보엔 일부만, MIDI 는 전곡 | 자동으로 '대조 불가'로 빼고 따로 센다 |
| **해상도** | 80DPI 이미지는 Audiveris 가 하드 실패(interline 7px) | PDF 를 직접 넣으면 Audiveris 가 알아서 300DPI 로 읽는다 |

## 채점 지표

- **NER** = Levenshtein(정답 음높이 순서, 인식 음높이 순서) / 정답 길이.
  **DTW 를 쓰지 말 것** — 삽입·삭제를 표현하지 못해 누락 음표를 은폐한다.
- **박자 안 맞는 마디 비율** — 정답이 없어도 되는 검사. 마디 안 음표 길이 합이
  박자와 다르면 뭔가 잘못 읽은 것이다. 못갖춘마디·끝마디는 제외한다.
  단선율 첼로 2.8% vs 플루트 3중주 29.2% 처럼 난이도를 잘 갈라낸다.

## 지금까지의 실측 (2026-09-09, 소표본)

| 입력 | 엔진 | 결과 |
|---|---|---|
| 우리 조판 단선율 300DPI 10장(712음) | Audiveris 5.11.0 | NER 0.0014, 9/10 무오류 |
| 같은 10장을 폰 사진처럼 열화 | Audiveris 5.11.0 | NER 0.0223, 5/10 무오류 |
| 진짜 출판 단선율 12곡 | Audiveris 5.11.0 | **7/12 무오류, 중앙 NER 0.000** |
| 우리 조판 단선율 10장 | homr 0.7.0 | 이음줄 정규화 후 NER 0.000 (AGPL) |
| 우리 조판 단선율 1장 | oemer 0.1.8 | NER 0.914 — 6분30초/장, **사용 불가** |

**깨끗한 단선율 인쇄 악보는 이미 무료 소프트웨어가 사실상 완벽하게 읽는다.**

## 실패 원인 규명 (2026-09-13, 실측 완결)

단선율 93곡 채점에서 '나쁨(>15%)'으로 남은 곡들의 원인을 세 가설로 좁혀
전부 실험했다. 반복 구조 탓(기각 — 순환 반복 대조 0/14 개선), 꾸밈음
탓(기각 — 실패곡 꾸밈표 중앙 2개뿐), 그리고:

**확정 — 특이 박자표를 잘못 읽고, 마디 검열이 음표를 버린다.**

| 박자 | 잘 읽음(≤5%) | 못 읽음(>15%) |
|---|---|---|
| 2/4·3/4 | 4곡 | 0곡 |
| 4/4 | 16곡 | 2곡 |
| 6/8 | 7곡 | 2곡 |
| **9/8** | 1곡 | **3곡** |
| **3/2** | 0곡 | **2곡 (전패)** |

메커니즘 (Dusty Miller 3/2 로 실증):
- 첫째 단(박자표 있음): 6박짜리 마디에서 **정확히 절반(3박)만** 남김 —
  Audiveris 의 리듬 검증이 '마디에 넘치는' 음표를 스스로 제외한다.
- 둘째 단(박자표는 첫 단에만 인쇄되므로 없음): **24음 전부 완벽.**
- 페이지를 오선 단별로 잘라 넣는 실험: 대조군 3곡은 0.000 유지(자르기
  무해), Cam Ye O'er Frae France 0.51→0.16 등 일부 개선, 그러나 박자표가
  포함된 첫 단은 여전히 검열됨 — 배치 문제가 아니라 박자표 문제.

**우리 계획에 주는 뜻**: 우리가 만들 CTC 방식은 오선 한 줄을 순서대로
읽을 뿐 '마디가 박자에 맞는가'를 강제하지 않는다 — 이 실패 모드가
구조적으로 없다. 또한 2단계(미디 없는 곡 채우기)의 품질 체에
**박자표(3/2·9/8 등 특이 박자)를 위험 신호로** 넣을 수 있다.

우리 과제는 정확도를 새로 발명하는 것이 아니라, 같은 정확도를
**앱에 넣을 수 있는 크기·라이선스로** 다시 만드는 것이다
(Audiveris·homr 은 AGPL 이라 앱에 못 넣고, 자바 200MB·14초/장이라 폰에서도 못 돈다).
