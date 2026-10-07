# omr_core — 악보 사진 인식 순수 다트 코어 (앱 탑재 S1)

내 악보함(sheet_music_app) 스캔 기능의 플랫폼 무관 부분. Flutter·onnxruntime 에
의존하지 않는다 — 추론은 앱이 `LineRecognizer` 로 주입한다. 외부 의존성은 순수
다트 `image`(JPEG 디코드·EXIF 회전) 하나. 설계: `../앱탑재_설계.md`.

| 파일 | 내용 | 파이썬 기준 |
|---|---|---|
| `src/pipeline/*` | 줄 검출·보정·정규화(폰벤치에서 정합 게이트 통과한 코드 그대로) | photo_prep·prep |
| `src/ctc.dart` | 그리디 CTC 디코드 + 줄 신뢰도 | model.greedy_decode·evaluate_duet.decode_conf |
| `src/select.dart` | 켬/끔 조기 결정·자동선택(v4), 가짜 줄 제거(v5) | phone_bench/ghost_diag.py |
| `src/monophony.dart` | 단선율 아님 경고(쌓인 음표머리·보표 쌍) | tool/poly_signals.py |
| `src/score.dart` | 반복 전개·셈여림 세기·붙임줄 병합·시간 배치·SMF | lib_lines.unfold_tokens·evaluate.write_midi(+tool/ref_score.py) |
| `src/wav_embed.dart` | 첨부 WAV 안 `omrS` 청크로 미디·토큰 보관 | — |
| `src/scanner.dart` | 사진 한 장 흐름(isolate 검출 병렬/순차 → 인식 → 선택 → 경고) | phone_bench full_bench v5 |

## 시험

```powershell
dart pub get
dart test -j 1
```

- `unit_test.dart` — 외부 파일 없이.
- `parity_test.dart` — 파이썬 기준값과 정합(캐논 53 + 비캐논 43장, 텐서 235줄).
  기준값은 저장소 밖: `python tool/make_fixture.py` → `C:/Users/user/omr_core_fixture/`
  (ghost_diag.json·vocab.json·dart_out_v5 필요). 없으면 건너뛴다.
- `scanner_test.dart` — 실제 다트 검출(사진 A) + 가짜 추론기로 흐름 점검. 사진 없으면 건너뜀.

## 보정 도구 (tool/)

- `poly_calib.py render|dump|evaluate` — 화음·2중음·피아노·함정(임시표·조표 6개·
  빠르기표·16분 겹빔) 렌더와 실물 96장으로 단선율 경고 문턱 보정.
- `make_fixture.py` — 다트 정합 기준값 생성(SMF 기준 구현은 기존 write_midi 와 바이트 일치 검사 포함).

출력물(PNG·npz·fixture)은 전부 저장소 밖 — 커밋 금지.
