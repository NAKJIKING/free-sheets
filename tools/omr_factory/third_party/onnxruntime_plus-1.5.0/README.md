<p align="center"><img width="50%" src="https://github.com/microsoft/onnxruntime/raw/main/docs/images/ONNX_Runtime_logo_dark.png" /></p>

# onnxruntime_plus
[![pub package](https://img.shields.io/pub/v/onnxruntime_plus.svg)](https://pub.dev/packages/onnxruntime_plus)

## Fork Status

This package is a fork of the original [`onnxruntime`](https://pub.dev/packages/onnxruntime) Flutter plugin.
It is kept mainly to ship Apple packaging fixes, especially iOS Swift Package Manager support,
and related compatibility updates that are not available in the older package.

Maintenance is best-effort and focused on keeping the package usable for current projects,
not on broad feature development.

## Overview

Flutter plugin for ONNX Runtime via `dart:ffi` with iOS Swift Package Manager support and cross-platform Dart bindings.

| **Platform**      | Android       | iOS | Linux | macOS | Windows |
|-------------------|---------------|-----|-------|-------|---------|
| **Compatibility** | API level 24+ | *   | *     | *     | *       |
| **Architecture**  | arm32/arm64   | *   | *     | *     | *       |

*: [Consistent with Flutter](https://docs.flutter.dev/reference/supported-platforms)

## Key Features

* Multi-platform Support for Android, iOS, Linux, macOS, Windows, and Web(Coming soon).
* Flexibility to use any Onnx Model.
* Acceleration using multi-threading.
* Similar structure as OnnxRuntime Java and C# API.
* Inference speed is not slower than native Android/iOS Apps built using the Java/Objective-C API.
* Run inference in different isolates to prevent jank in UI thread.

## Android 16 KB page size

Since version 1.5.0 the bundled Android runtime is ONNX Runtime 1.22.0, whose
`libonnxruntime.so` is linked with 16 KB ELF segment alignment. That is what
Google Play requires of apps targeting Android 15 and above, and what devices
running a 16 KB page size need in order to map the library at all.

The 16 KB binaries are built against API 24, so this package raises its
`minSdkVersion` from 21 to 24. Set `minSdkVersion 24` (or higher) in your app's
`android/app/build.gradle` if it is still on a lower value.

## Getting Started

In your flutter project add the dependency:

```yml
dependencies:
  ...
  onnxruntime_plus: x.y.z
```

## Usage example

### Import

```dart
import 'package:onnxruntime_plus/onnxruntime_plus.dart';
```

### Initializing environment

```dart
OrtEnv.instance.init();
```

### Creating the Session

```dart
final sessionOptions = OrtSessionOptions();
const assetFileName = 'assets/models/test.onnx';
final rawAssetFile = await rootBundle.load(assetFileName);
final bytes = rawAssetFile.buffer.asUint8List();
final session = OrtSession.fromBuffer(bytes, sessionOptions!);
```

### Performing inference

```dart
final shape = [1, 2, 3];
final inputOrt = OrtValueTensor.createTensorWithDataList(data, shape);
final inputs = {'input': inputOrt};
final runOptions = OrtRunOptions();
final outputs = await _session?.runAsync(runOptions, inputs);
inputOrt.release();
runOptions.release();
outputs?.forEach((element) {
  element?.release();
});
```

### Releasing environment

```dart
OrtEnv.instance.release();
```

## Apple packaging

For iOS, this package supports both CocoaPods fallback and Swift Package Manager integration.
The Swift package uses the official ONNX Runtime iOS binary archive published by Microsoft.
This fork also keeps Apple package metadata in sync for newer Flutter package-manager expectations.

