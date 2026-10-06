// OMR 폰 속도 시험 앱 — FP32 ONNX 30줄 추론 벤치 (다트 포팅 판단 자료).
// 화면 캡처 한 장으로 보고 가능하게 결과를 한 화면에 크게 표시한다.
import 'dart:convert';
import 'dart:typed_data';


import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:onnxruntime/onnxruntime.dart';

import 'full_bench.dart';

void main() => runApp(const BenchApp());

class BenchApp extends StatelessWidget {
  const BenchApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'OMR 폰 벤치',
        theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
        home: WidgetsBinding.instance.platformDispatcher.defaultRouteName ==
                '/full'
            ? const FullBenchPage(autorun: true)
            : const BenchPage(),
      );
}

class LineItem {
  LineItem(this.name, this.src, this.h, this.w, this.ref, this.data);
  final String name;
  final String src;
  final int h;
  final int w;
  final List<int> ref;
  final Float32List data;
}

class ConfigResult {
  ConfigResult(this.name);
  final String name;
  double loadMs = 0; // 세션 생성
  double firstMs = 0; // 첫 추론(그래프 준비 포함)
  List<double> perLine = [];
  int match = 0;
  String? error;

  double get mean =>
      perLine.isEmpty ? 0 : perLine.reduce((a, b) => a + b) / perLine.length;
  double get worst =>
      perLine.isEmpty ? 0 : perLine.reduce((a, b) => a > b ? a : b);
}

class BenchPage extends StatefulWidget {
  const BenchPage({super.key});
  @override
  State<BenchPage> createState() => _BenchPageState();
}

class _BenchPageState extends State<BenchPage> {
  String status = '대기 — [측정 시작]을 누르세요';
  String device = '';
  bool running = false;
  List<ConfigResult> results = [];

  Future<List<LineItem>> _loadLines() async {
    final meta = jsonDecode(
        await rootBundle.loadString('assets/lines/meta.json'));
    final items = <LineItem>[];
    for (final m in (meta['lines'] as List)) {
      final bd = await rootBundle.load('assets/lines/${m['file']}');
      final f32 = bd.buffer.asFloat32List(
          bd.offsetInBytes, bd.lengthInBytes ~/ 4);
      items.add(LineItem(m['file'], m['src'], m['h'], m['w'],
          (m['ref'] as List).cast<int>(), Float32List.fromList(f32)));
    }
    return items;
  }

  List<int> _greedy(List frames) {
    final ids = <int>[];
    var prev = 0;
    for (final f in frames) {
      final row = (f as List).cast<double>();
      var am = 0;
      var best = row[0];
      for (var c = 1; c < row.length; c++) {
        if (row[c] > best) {
          best = row[c];
          am = c;
        }
      }
      if (am != prev && am != 0) ids.add(am);
      prev = am;
    }
    return ids;
  }

  bool _same(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  Future<ConfigResult> _runConfig(String name, Uint8List model,
      List<LineItem> lines, OrtSessionOptions opts) async {
    final r = ConfigResult(name);
    OrtSession? session;
    try {
      final sw = Stopwatch()..start();
      session = OrtSession.fromBuffer(model, opts);
      r.loadMs = sw.elapsedMicroseconds / 1000.0;

      OrtValue? runOne(LineItem li, ConfigResult r, bool timed) {
        final input = OrtValueTensor.createTensorWithDataList(
            li.data, [1, 1, li.h, li.w]);
        final ro = OrtRunOptions();
        final sw2 = Stopwatch()..start();
        final outs = session!.run(ro, {'x': input});
        final dt = sw2.elapsedMicroseconds / 1000.0;
        if (timed) r.perLine.add(dt);
        input.release();
        ro.release();
        for (var i = 1; i < outs.length; i++) {
          outs[i]?.release();
        }
        return outs[0];
      }

      // 첫 추론(그래프 준비 포함) + 준비 운전 3회
      final swf = Stopwatch()..start();
      runOne(lines[0], r, false)?.release();
      r.firstMs = swf.elapsedMicroseconds / 1000.0;
      for (var k = 0; k < 2; k++) {
        runOne(lines[0], r, false)?.release();
      }
      // 본 측정 30줄
      for (var i = 0; i < lines.length; i++) {
        final out = runOne(lines[i], r, true);
        final v = out?.value as List?;
        if (v != null && _same(_greedy(v[0] as List), lines[i].ref)) {
          r.match++;
        }
        out?.release();
        setState(() => status = '$name: ${i + 1}/${lines.length}');
        await Future<void>.delayed(Duration.zero);
      }
    } catch (e) {
      r.error = '$e';
    } finally {
      session?.release();
    }
    return r;
  }

  Future<void> _start() async {
    setState(() {
      running = true;
      results = [];
      status = '모델·시험줄 로딩…';
    });
    try {
      final info = await DeviceInfoPlugin().androidInfo;
      device = '${info.manufacturer} ${info.model} (SDK ${info.version.sdkInt})';
    } catch (_) {
      device = '기기 정보 없음';
    }
    try {
      OrtEnv.instance.init();
      final model = (await rootBundle.load('assets/model/omr_crnn_fp32.onnx'))
          .buffer
          .asUint8List();
      final lines = await _loadLines();

      final cpu = await _runConfig('CPU 기본', model, lines,
          OrtSessionOptions()..setIntraOpNumThreads(2));
      setState(() => results = [cpu]);

      final xo = OrtSessionOptions()..setIntraOpNumThreads(2);
      ConfigResult xr;
      try {
        xo.appendXnnpackProvider();
        xr = await _runConfig('XNNPACK', model, lines, xo);
      } catch (e) {
        xr = ConfigResult('XNNPACK')..error = '$e';
      }
      setState(() {
        results = [cpu, xr];
        status = '완료';
      });
    } catch (e) {
      setState(() => status = '오류: $e');
    } finally {
      setState(() => running = false);
    }
  }

  String _fmt(ConfigResult r) {
    if (r.error != null) {
      return '[${r.name}] 오류\n${r.error}\n';
    }
    return '[${r.name}]\n'
        '  모델 로딩  ${r.loadMs.toStringAsFixed(0)} ms\n'
        '  첫 추론    ${r.firstMs.toStringAsFixed(0)} ms\n'
        '  평균       ${r.mean.toStringAsFixed(1)} ms/줄\n'
        '  최악       ${r.worst.toStringAsFixed(1)} ms\n'
        '  정답 일치  ${r.match}/30\n';
  }

  @override
  Widget build(BuildContext context) {
    final body = StringBuffer();
    body.writeln('기기: $device');
    body.writeln('모델: omr_crnn_fp32.onnx (관문 채택본 3c4)');
    body.writeln('시험: 엘리제 20줄 + 캐논 실물 10줄');
    body.writeln('PC 기준(ORT CPU): 평균 114.7 / 최악 144.1 ms');
    body.writeln('');
    for (final r in results) {
      body.writeln(_fmt(r));
    }
    return Scaffold(
      appBar: AppBar(title: const Text('OMR 폰 속도 시험 v5')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            FilledButton(
              onPressed: running ? null : _start,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Text(running ? status : '측정 시작',
                    style: const TextStyle(fontSize: 22)),
              ),
            ),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: running
                  ? null
                  : () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => const FullBenchPage())),
              child: const Padding(
                padding: EdgeInsets.all(10),
                child: Text('사진 한 장 전체 측정', style: TextStyle(fontSize: 18)),
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: SingleChildScrollView(
                child: Text(
                  results.isEmpty ? status : body.toString(),
                  style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 17,
                      height: 1.45,
                      fontFeatures: [FontFeature.tabularFigures()]),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
