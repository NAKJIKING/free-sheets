# omr_phone_bench — 폰 속도 시험 앱 (다트 포팅 판단 자료)

FP32 ONNX(관문 채택본 omr_model_3c4)를 폰에서 돌려 한 줄 추론 속도와
파이썬 디코드 일치를 재는 **독립** Flutter 앱. 실제 앱(sheet_music_app)과
무관하고 스토어에 올리지 않는다(디버그 서명).

- 화면: [측정 시작] 버튼 → 준비 운전 3회 → 30줄 순차 추론 → 모델 로딩·
  첫 추론·평균·최악·정답 일치(30줄)·기기 모델명을 한 화면에 표시.
- CPU 기본과 XNNPACK 두 세션을 나란히 측정(가속 오류 시 문구 표시).
- 시험줄: 엘리제 20 + 캐논 실물 10 — 파이썬 전처리 완료 텐서(.bin
  float32 LE, 160×W)와 파이썬 ORT 정답 디코드(meta.json)를 자산으로 내장.

## 재현 (모델·텐서·APK 는 저장소에 없다 — 커밋 금지)

```powershell
flutter create --platforms android --org com.omr --project-name omr_phone_bench C:/Users/me/omr_phone_bench
# 이 폴더의 pubspec.yaml, lib/main.dart 로 덮어쓰기
# 자산 생성(30줄 텐서 + 정답 + PC 기준): 
python make_bench_set.py     # → C:/Users/me/omr_phone_bench_assets
# assets/model/  ← omr_crnn_fp32.onnx, vocab.json
# assets/lines/  ← line_*.bin, meta.json
flutter build apk --release
```

빌드 함정 2개(실측, Flutter 3.44 / onnxruntime 1.4.1):
1. app/build.gradle.kts 에서 `minSdk = 24` 로 올릴 것.
2. onnxruntime 플러그인이 compileSdk 33 으로 굳어 있어 androidx(34+ 요구)와
   AAR 메타데이터 충돌 — **pub 캐시의 플러그인 gradle 을 직접 패치**해야
   한다: `%LOCALAPPDATA%/Pub/Cache/hosted/pub.dev/onnxruntime-1.4.1/android/
   build.gradle` 의 `compileSdkVersion 33` → `36`. (루트 gradle 의
   subprojects 오버라이드로는 안 먹힘을 확인.)

APK 배포: H:/내 드라이브/GPT/omr_phone_bench/ (크기·해시는 진행일지).
