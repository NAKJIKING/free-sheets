// PC 정합 검증용 CLI — 사진들에 다트 파이프라인을 돌려 중간 결과를 덤프.
//   dart run tool/run_pipeline.dart <pipe_assets_dir> <out_dir>
// pipe_assets_dir: py_dump_pipeline.py 출력(pipe_manifest.json + <stem>/photo.jpg)
// out_dir: <stem>/<side>_l##.bin(float32 LE 160×W) + dart_manifest.json
import 'dart:convert';
import 'dart:io';

import 'package:omr_phone_bench/pipeline/gray.dart';
import 'package:omr_phone_bench/pipeline/photo_prep.dart';
import 'package:omr_phone_bench/pipeline/prep.dart' as prep;

void main(List<String> args) {
  final srcDir = args[0];
  final outDir = args[1];
  final man = jsonDecode(
      File('$srcDir/pipe_manifest.json').readAsStringSync());
  final results = <Map<String, dynamic>>[];
  for (final ph in (man['photos'] as List)) {
    final stem = ph['stem'] as String;
    final sw = Stopwatch()..start();
    final photo =
        decodeGray(File('$srcDir/$stem/photo.jpg').readAsBytesSync());
    final entry = <String, dynamic>{'stem': stem, 'sides': {}};
    for (final side in ['on', 'off']) {
      final t0 = sw.elapsedMilliseconds;
      final crops = extractLines(photo, correct: side == 'on');
      final lines = <Map<String, dynamic>>[];
      Directory('$outDir/$stem').createSync(recursive: true);
      for (var li = 0; li < crops.length; li++) {
        final c = crops[li];
        final tensor = prep.normalizePhoto(c.gray, gapHint: c.gap);
        final f = File('$outDir/$stem/${side}_l${li.toString().padLeft(2, '0')}.bin');
        f.writeAsBytesSync(tensor.data.buffer.asUint8List(
            tensor.data.offsetInBytes, tensor.data.lengthInBytes));
        lines.add({
          'w': tensor.w,
          'crop_w': c.gray.w,
          'crop_h': c.gray.h,
          'cy': double.parse(c.cy.toStringAsFixed(2)),
          'gap': double.parse(c.gap.toStringAsFixed(3)),
          'box': c.box,
          'sq': prep.staffQ(tensor.data, tensor.w),
        });
      }
      entry['sides'][side] = {
        'n': crops.length,
        'ms': sw.elapsedMilliseconds - t0,
        'lines': lines,
      };
      stdout.writeln('$stem $side n=${crops.length} '
          '${sw.elapsedMilliseconds - t0}ms');
    }
    results.add(entry);
  }
  File('$outDir/dart_manifest.json')
      .writeAsStringSync(jsonEncode({'photos': results}));
  stdout.writeln('done -> $outDir');
}
