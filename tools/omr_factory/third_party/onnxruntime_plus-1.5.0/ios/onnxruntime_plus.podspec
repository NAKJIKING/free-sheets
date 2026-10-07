#
# To learn more about a Podspec see http://guides.cocoapods.org/syntax/podspec.html.
# Run `pod lib lint onnxruntime_plus.podspec` to validate before publishing.
#
Pod::Spec.new do |s|
  s.name             = 'onnxruntime_plus'
  s.version          = '1.4.3'
  s.summary          = 'Flutter FFI plugin for ONNX Runtime with iOS Swift Package Manager support.'
  s.description      = <<-DESC
Flutter FFI plugin for ONNX Runtime with iOS Swift Package Manager support.
                       DESC
  s.homepage         = 'https://github.com/almasumdev/onnxruntime_plus'
  s.license          = { :file => '../LICENSE' }
  s.author           = { 'Masum MSNR' => 'support@users.noreply.github.com' }
  s.source           = { :path => '.' }
  s.source_files     = 'onnxruntime_plus/Sources/onnxruntime_plus/**/*'
  s.dependency 'Flutter'
  s.dependency 'onnxruntime-objc', '1.15.1'
  s.platform         = :ios, '11.0'
  s.static_framework = true
  s.libraries        = 'c++'
  s.weak_frameworks  = 'CoreML'

  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
    'EXCLUDED_ARCHS[sdk=iphonesimulator*]' => 'i386',
  }
  s.swift_version = '5.0'
end