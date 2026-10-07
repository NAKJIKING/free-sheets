# 저장소에 포함한 onnxruntime 1.4.1 (앱 탑재 S3 — pub 캐시 패치 금지 대응)

## 원본

- 패키지: pub.dev `onnxruntime` **1.4.1** (2024-03-27, 최신판 — 이후 판 없음)
- 출처: https://pub.dev/api/archives/onnxruntime-1.4.1.tar.gz
- 원본 아카이브 sha256: `e77ec05acafc135cc5fe7bcdf11b101b39f06513c9d5e9fa02cb1929f6bac72a`
  (pub.dev API 의 archive_sha256 과 일치 확인, 34,307,377바이트)
- 저장소: https://github.com/gtbluesky/onnxruntime_flutter — 라이선스 **MIT**(LICENSE 동봉)
- 포함된 ONNX Runtime: 안드로이드 `jniLibs/{arm64-v8a,armeabi-v7a}/libonnxruntime.so` (1.15.1),
  iOS 는 CocoaPods `onnxruntime-objc 1.15.1`

## 바꾼 것 (전부)

1. **`android/build.gradle` compileSdkVersion 33 → 36** — androidx(exifinterface 1.4.1 등)가
   compileSdk 34 이상을 요구해 AAR 메타데이터 검사에서 빌드가 실패한다(실측). 플러그인의
   minSdk·targetSdk·코드는 그대로.
   ```diff
   -    compileSdkVersion 33
   +    compileSdkVersion 36
   ```
2. **`pubspec.yaml` 플랫폼 목록에서 macos·windows·linux 제거** — 앱은 안드로이드·iOS 만
   쓴다. 데스크톱 바이너리(macos 45MB·linux 16MB·windows 9MB)와 example 폴더는 저장소
   크기 때문에 포함하지 않았다.
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
그 외 파일(lib·src·android 바이너리·ios podspec)은 원본과 바이트 동일.

## 쓰는 법

```yaml
dependencies:
  onnxruntime:
    path: <저장소 기준 상대경로>/tools/omr_factory/third_party/onnxruntime-1.4.1
```

## ⚠ 알려진 문제 — 16KB 페이지 정렬 미지원

동봉 `libonnxruntime.so`(ORT 1.15.1)의 ELF LOAD 정렬이 **0x1000(4KB)** 이다
(`llvm-readelf -lW`, arm64-v8a·armeabi-v7a 모두). Google Play 는 Android 15 이상을 대상으로
하는 앱·업데이트에 16KB 페이지 크기 지원을 요구하므로, 이 판으로 만든 앱은 Play 업로드에서
막히거나 경고를 받을 수 있다. 같은 계열 포크 `onnxruntime_plus` 1.5.0 은 ORT 1.22.0 으로
올려 정렬 **0x4000(16KB)** — 진행일지 2026-10-07 S3 절의 비교·권고 참고.
