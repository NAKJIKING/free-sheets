# 저장소에 포함한 onnxruntime_plus 1.5.0 (앱 탑재 S3 — 사장님 결정 2026-10-07)

pub.dev 에 의존하지 않는다(관리자 1인·작은 포크). 앱·벤치는 이 폴더를 **path 의존성**으로 쓴다.

## 원본

- 패키지: pub.dev `onnxruntime_plus` **1.5.0** (2026-07-27)
- 출처: https://pub.dev/api/archives/onnxruntime_plus-1.5.0.tar.gz
- 원본 아카이브 sha256: `05323f4f72c701416deba8db94f5e576f6853ca6f8d97d628ed9190eee6d77d8`
  (pub.dev API archive_sha256 과 일치 확인, 38,201,960바이트)
- 저장소: https://github.com/almasumdev/onnxruntime_plus — gtbluesky/onnxruntime_flutter
  (pub `onnxruntime` 1.4.1, MIT)의 포크. 퍼블리셔 `almasum.dev`(pub.dev 인증).
- 라이선스: **MIT** (LICENSE 동봉 — 저작권 표기 "Copyright (c) 2023 gtbluesky" 원문 그대로)
- 포함된 ONNX Runtime: 안드로이드 `jniLibs/{arm64-v8a,armeabi-v7a}/libonnxruntime.so`
  **1.22.0**, ELF LOAD 정렬 **0x4000(16KB)** — Google Play 16KB 페이지 요건 충족.
  iOS 는 CocoaPods `onnxruntime-objc 1.15.1`(podspec 그대로 — iOS 탑재 시 재검토).

## 바꾼 것 (전부)

1. **`android/build.gradle` compileSdkVersion 33 → 36** — androidx(exifinterface 1.4.1 등)가
   compileSdk 34 이상을 요구해 AAR 메타데이터 검사에서 빌드 실패(새 PUB_CACHE 실측).
   ```diff
   -    compileSdkVersion 33
   +    compileSdkVersion 36
   ```
2. **`pubspec.yaml` 플랫폼 목록에서 macos·windows·linux 제거** — 앱은 안드로이드·iOS 만.
   데스크톱 바이너리·example 폴더는 포함하지 않았다.
   ```diff
          ios:
            ffiPlugin: true
   -      macos:
   -        ffiPlugin: true
   -      windows:
   -        ffiPlugin: true
   -      linux:
   -        ffiPlugin: true
   ```
그 외 파일(lib·src·ios·android 바이너리)은 원본과 바이트 동일(diff -r·cmp 확인).

## 검증

- 새 빈 PUB_CACHE + 벤치 앱 새 사본에서 `flutter pub get` → `flutter build apk --release` 성공.
- 폰 실측(사장님, 2026-10-07): 30줄 시험 **정답 일치 30/30** (ORT 1.22.0).

## 쓰는 법

```yaml
dependencies:
  onnxruntime_plus:
    path: <저장소 기준 상대경로>/tools/omr_factory/third_party/onnxruntime_plus-1.5.0
```
Dart: `import 'package:onnxruntime_plus/onnxruntime_plus.dart';` (API 는 onnxruntime 1.4.1 과 같다)
