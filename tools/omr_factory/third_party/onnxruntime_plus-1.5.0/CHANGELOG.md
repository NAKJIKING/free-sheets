## 1.5.0

* Update the bundled Android ONNX Runtime from 1.15.1 to 1.22.0, so
  `libonnxruntime.so` is built with 16 KB ELF segment alignment.

  Google Play requires 16 KB page size support for apps targeting Android 15+,
  and the 1.15.1 binary was aligned to 4 KB. Apps shipping this package were
  rejected at upload, and on a device running 16 KB pages the loader could not
  map the library at all, so every `OrtEnv`/`OrtSession` call failed.

  1.22.0 is the newest release before the binary roughly doubles in size: it
  adds about 3.9 MB on arm64-v8a, against about 13 MB for 1.27.0. The Dart
  bindings request `GetApi(14)`, which every release from 1.14 onwards serves,
  so no regeneration was needed.

  Android only. iOS, macOS, Linux and Windows still resolve their own
  version-pinned runtimes and are unchanged.

  Note `minSdkVersion` 24, up from 21 in 1.15.1.

## 1.4.3

* Fix doc comments in `list_shape_extension.dart` so pub.dev static analysis no longer treats generic type names as HTML.
* Point the macOS Swift Package Manager artifact URL at the release-matching tag.

## 1.4.2

* Rename the package to `onnxruntime_plus`.
* Add iOS Swift Package Manager support using the official ONNX Runtime binary archive.
* Keep CocoaPods fallback support for Apple builds where Swift Package Manager is disabled.

## 1.4.1

* Fixes a memory leak when creating tensor.

## 1.4.0

* Fixes a memory leak when creating tensor.

## 1.3.0

* Attempts to support macOS, Windows and Linux.

## 1.2.0

* Compatible with Gradle8.

## 1.1.0

* Exposes some methods of input and output name.
* Adds some documentation comments.

## 1.0.0

* Initial release.
