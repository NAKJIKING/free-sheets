import 'dart:ffi';
import 'dart:io';
import 'package:onnxruntime_plus/src/bindings/onnxruntime_bindings_generated.dart';

final DynamicLibrary _dylib = () {
  if (Platform.isAndroid) {
    return DynamicLibrary.open('libonnxruntime.so');
  }

  if (Platform.isIOS) {
    return DynamicLibrary.process();
  }

  if (Platform.isMacOS) {
    try {
      return DynamicLibrary.open('libonnxruntime.1.15.1.dylib');
    } on ArgumentError {
      return DynamicLibrary.process();
    }
  }

  if (Platform.isWindows) {
    return DynamicLibrary.open('onnxruntime.dll');
  }

  if (Platform.isLinux) {
    return DynamicLibrary.open('libonnxruntime.so.1.15.1');
  }

  throw UnsupportedError('Unknown platform: ${Platform.operatingSystem}');
}();

/// OnnxRuntime Bindings
final onnxRuntimeBinding = OnnxRuntimeBindings(_dylib);
