# omr_factory — 4단계(자체 인식 모델) 데이터 공장

목표: **Audiveris 수준의 우리 자체 악보 인식 모델** (사장님 승인 2026-09-18
"쭉쭉 해보자"). 폰에서 도는 줄 단위 CTC 모델 — 상세 설계는
`project-all/sheet_music_app/OMR_연구.md`.

> ⚠ **2026-09-18 갱신 — 코퍼스가 바뀌었다.** 사장님 지시로 학습 코퍼스를
> 자체 조판 .ly 에서 **라이브러리 미디 전체(7,336개 → 단선율 4,261곡)** 로
> 옮겼다. 아래 ① 은 그대로 유효하지만 저장소의 `all_out` 에는 24곡 × 9악기
> 밖에 없고 **엘리제의 .ly 가 없다**. 현재 쓰는 것은 ② 다.
> 경위·수치·실행법은 **`진행일지.md`** 를 볼 것.

## ① make_lines.py — 줄 단위 학습쌍 생성기 (완성·검증됨)

우리 조판 원본 252곡(.ly)의 멜로디를 4마디씩 끊고 12개 조로 옮겨,
**한 줄짜리 악보 PNG(300DPI) + 정답 미디** 쌍을 찍는다.

- 페이지를 잘라내는 게 아니라 **처음부터 한 줄로 조판** — 이미지와
  정답이 어긋날 수 없다(전체 페이지 자르기의 줄-정답 정렬 문제 원천 차단).
- `\transposition`(악기 조옮김)은 떼고 렌더 → 미디 = 보이는 음
  (채점기와 같은 규칙. 안 떼면 색소폰 등에서 정답이 −9 어긋난다).
- 붙임줄(~)이 청크 경계를 넘으면 다음 마디를 흡수 — 음이 안 갈라짐.
- 빠르기표는 첫 청크에만(실제 악보 관례). 보표 크기 20~26 변주
  (곡·청크·조 해시로 결정 — 난수 없이 재현 가능).
- 검증(2026-09-18): 3곡×3조 + 2곡×2조 전수 — 렌더 실패 0,
  모든 청크에서 +3/−2/+5 반음이 미디에 정확히 반영, 이미지 육안 확인.

```bash
# 연기 시험 (곡 3, 조 3)
python3 tools/omr_factory/make_lines.py --out /tmp/lines --limit 3 --keys 0,3,-2
# 전체: 252곡 × ~8청크 × 12조 ≈ 24,000쌍, 이미지 ~1.2GB
python3 tools/omr_factory/make_lines.py --out DIR
```

⚠ 전체 실행은 개발 컨테이너에서 하지 말 것(디스크·세션 수명) —
깃허브 액션/집PC/캐글에서. LILYPOND 환경변수로 바이너리 지정 가능.

## 다음 단계 (순서)

1. 전체 생성 실행 + 캐글 데이터셋 업로드 (사장님: 캐글 무료 계정 필요)
2. 사진 증강은 학습 시점에(기하→잉크→종이→조명→광학→센서→JPEG 마지막,
   ScoreAug 질감 — 연구 문서의 실측 순서)
3. CTC 모델 학습(캐글 무료 GPU) → **1차 관문: 깨끗한 렌더 95%**,
   시험곡 = 엘리제를 위하여(단선율 A부분), 서버 시연과 같은 청음 비교
4. 통과 후: 실사 폰사진 50장 시험 → ONNX 양자화 → 앱 탑재


## ② 라이브러리 미디 공장 + 학습 일습 (2026-09-18, 현재 주력)

`lib_lines.py` / `make_lib_lines.py` / `prep.py` / `cache.py` / `dataset.py` /
`model.py` / `train.py` / `split.py` / `evaluate.py`.
전체 실행 순서와 주의사항은 `진행일지.md` 에 있다. 요약:

```bash
export LILYPOND='C:/Users/cocok/tools/lilypond-2.24.4/bin/lilypond.exe'
python tools/omr_factory/make_lib_lines.py --out DIR --keys 3 --max-chunks 6
python tools/omr_factory/split.py   --data DIR      # 곡 단위 분할, 엘리제=시험
python tools/omr_factory/cache.py   --data DIR      # 오선 정규화 캐시
python tools/omr_factory/train.py   --data DIR --out MODEL --epochs 40
python tools/omr_factory/evaluate.py --data DIR --model MODEL --out GATE1
```
