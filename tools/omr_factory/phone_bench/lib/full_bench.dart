// [사진 한 장 전체] 측정 — 사진 → 줄 검출·보정(켬/끔, isolate) → 추론 →
// 자동선택 → 음표 수까지 단계별 시간 표시. 카메라 촬영 측정 포함.
// adb 자동실행(route /full)이면 내장 사진 A 를 돌리고 결과를 logcat 에 남긴다.
import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:isolate';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:image_picker/image_picker.dart';
import 'package:onnxruntime/onnxruntime.dart';

import 'pipeline/gray.dart';
import 'pipeline/photo_prep.dart';
import 'pipeline/prep.dart' as prep;

class LineOut {
  LineOut(this.w, this.data, this.cy, this.gap, this.box);
  final int w;
  final Float32List data; // 160×w
  final double cy;
  final double gap;
  final List<int> box;
}

class SideOut {
  SideOut(this.ms, this.lines);
  final int ms;
  final List<LineOut> lines;
}

class PipeOut {
  PipeOut(this.decodeMs, this.on, this.off);
  final int decodeMs;
  final SideOut on;
  final SideOut off;
}

// ── isolate ──
void _pipeEntry(List<Object> args) {
  final jpeg = args[0] as Uint8List;
  final progress = args[1] as SendPort;
  final result = args[2] as SendPort;
  final sw = Stopwatch()..start();
  progress.send('사진 디코드 중…');
  final photo = decodeGray(jpeg);
  final decodeMs = sw.elapsedMilliseconds;
  final sides = <String, List<Object>>{};
  for (final side in ['on', 'off']) {
    progress.send(side == 'on' ? '보정·검출(켬) 중…' : '검출(끔) 중…');
    final t0 = sw.elapsedMilliseconds;
    final crops = extractLines(photo, correct: side == 'on');
    final lines = <Object>[];
    for (var i = 0; i < crops.length; i++) {
      progress.send('${side == 'on' ? '보정(켬)' : '검출(끔)'} 줄 정규화 '
          '${i + 1}/${crops.length}');
      final t = prep.normalizePhoto(crops[i].gray, gapHint: crops[i].gap);
      lines.add([
        t.w,
        t.data,
        crops[i].cy,
        crops[i].gap,
        crops[i].box,
      ]);
    }
    sides[side] = [sw.elapsedMilliseconds - t0, lines];
  }
  result.send([decodeMs, sides['on']!, sides['off']!]);
}

Future<PipeOut> runPipeline(
    Uint8List jpeg, void Function(String) onProgress) async {
  final prog = ReceivePort();
  final res = ReceivePort();
  prog.listen((m) => onProgress(m as String));
  await Isolate.spawn(_pipeEntry, [jpeg, prog.sendPort, res.sendPort]);
  final raw = await res.first as List;
  prog.close();
  SideOut side(List s) => SideOut(
      s[0] as int,
      (s[1] as List)
          .map((l) => LineOut(
              (l as List)[0] as int,
              l[1] as Float32List,
              l[2] as double,
              l[3] as double,
              (l[4] as List).cast<int>()))
          .toList());
  return PipeOut(raw[0] as int, side(raw[1] as List), side(raw[2] as List));
}

class FullBenchPage extends StatefulWidget {
  const FullBenchPage({super.key, this.autorun = false});
  final bool autorun;
  @override
  State<FullBenchPage> createState() => _FullBenchPageState();
}

class _FullBenchPageState extends State<FullBenchPage> {
  String status = '대기';
  String report = '';
  bool running = false;
  OrtSession? _session;
  List<int>? _pitch; // 클래스 id-1 → 음고

  @override
  void initState() {
    super.initState();
    if (widget.autorun) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _runAsset('A'));
    }
  }

  Future<void> _ensureSession() async {
    if (_session != null) return;
    OrtEnv.instance.init();
    final model = (await rootBundle.load('assets/model/omr_crnn_fp32.onnx'))
        .buffer
        .asUint8List();
    _session = OrtSession.fromBuffer(
        model, OrtSessionOptions()..setIntraOpNumThreads(2));
    final vocab = jsonDecode(
        await rootBundle.loadString('assets/model/vocab.json')) as List;
    _pitch = vocab.map((t) => (t as List)[0] as int).toList();
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

  Future<void> _runBytes(String name, Uint8List jpeg) async {
    setState(() {
      running = true;
      report = '';
      status = '모델 준비…';
    });
    try {
      await _ensureSession();
      final total = Stopwatch()..start();
      final pipe = await runPipeline(jpeg, (m) {
        if (mounted) setState(() => status = m);
      });
      // 추론(양쪽) — runAsync 로 UI 비블록
      final infer = Stopwatch()..start();
      Future<(double, int, List<List<int>>)> decodeSide(SideOut s) async {
        var confSum = 0.0;
        var frameSum = 0;
        var nonempty = 0;
        final idsList = <List<int>>[];
        for (var i = 0; i < s.lines.length; i++) {
          if (mounted) {
            setState(() => status = '인식 중 ${i + 1}/${s.lines.length}');
          }
          final li = s.lines[i];
          final input = OrtValueTensor.createTensorWithDataList(
              li.data, [1, 1, 160, li.w]);
          final ro = OrtRunOptions();
          final outs =
              await (_session!.runAsync(ro, {'x': input}) ?? Future.value([]));
          input.release();
          ro.release();
          if (outs.isEmpty || outs[0] == null) continue;
          final v = outs[0]!.value as List;
          final frames = (v[0] as List);
          final t = li.w ~/ 4;
          final use = frames.length < t ? frames : frames.sublist(0, t);
          final ids = _greedy(use);
          idsList.add(ids);
          if (ids.isNotEmpty) nonempty++;
          // 신뢰도: softmax 최대 평균
          var cs = 0.0;
          for (final f in use) {
            final row = (f as List).cast<double>();
            var mx = row[0];
            var se = 0.0;
            for (final x in row) {
              if (x > mx) mx = x;
            }
            for (final x in row) {
              se += math.exp(x - mx);
            }
            cs += 1.0 / se;
          }
          confSum += cs;
          frameSum += use.length;
          for (final o in outs) {
            o?.release();
          }
        }
        final conf = frameSum == 0 ? 0.0 : confSum / frameSum;
        return (conf, nonempty, idsList);
      }

      final (confOn, neOn, idsOn) = await decodeSide(pipe.on);
      final (confOff, neOff, idsOff) = await decodeSide(pipe.off);
      final inferMs = infer.elapsedMilliseconds;
      const exp = 14;
      String pick;
      if ((confOn - confOff).abs() > 0.002) {
        pick = confOn >= confOff ? 'on' : 'off';
      } else {
        final dOn = (neOn - exp).abs(), dOff = (neOff - exp).abs();
        pick = (dOn < dOff || (dOn == dOff && confOn >= confOff))
            ? 'on'
            : 'off';
      }
      final ids = pick == 'on' ? idsOn : idsOff;
      var notes = 0;
      for (final l in ids) {
        for (final k in l) {
          if (_pitch![k - 1] > 0) notes++;
        }
      }
      final totalMs = total.elapsedMilliseconds;
      final buf = StringBuffer()
        ..writeln('[$name] 전체 ${(totalMs / 1000).toStringAsFixed(1)}초')
        ..writeln('  디코드      ${pipe.decodeMs} ms')
        ..writeln('  보정·검출(켬) ${(pipe.on.ms / 1000).toStringAsFixed(1)}초 '
            '(${pipe.on.lines.length}줄)')
        ..writeln('  검출(끔)     ${(pipe.off.ms / 1000).toStringAsFixed(1)}초 '
            '(${pipe.off.lines.length}줄)')
        ..writeln('  인식(양쪽)   ${(inferMs / 1000).toStringAsFixed(1)}초')
        ..writeln('  선택 ${pick == 'on' ? '보정 켬' : '보정 끔'} / 음표 $notes개');
      debugPrint('OMRBENCH_RESULT ${jsonEncode({
            'name': name,
            'totalMs': totalMs,
            'decodeMs': pipe.decodeMs,
            'onMs': pipe.on.ms,
            'offMs': pipe.off.ms,
            'onLines': pipe.on.lines.length,
            'offLines': pipe.off.lines.length,
            'inferMs': inferMs,
            'pick': pick,
            'notes': notes,
          })}');
      setState(() {
        report += buf.toString();
        status = '완료';
      });
    } catch (e, st) {
      debugPrint('OMRBENCH_ERROR $e\n$st');
      setState(() => status = '오류: $e');
    } finally {
      setState(() => running = false);
    }
  }

  Future<void> _runAsset(String which) async {
    final path =
        which == 'A' ? 'assets/photos/photo_a.jpg' : 'assets/photos/photo_b.jpg';
    final bytes = (await rootBundle.load(path)).buffer.asUint8List();
    await _runBytes('내장 사진 $which', bytes);
  }

  Future<void> _runCamera() async {
    final x = await ImagePicker()
        .pickImage(source: ImageSource.camera, imageQuality: 95);
    if (x == null) return;
    await _runBytes('카메라', await x.readAsBytes());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('사진 한 장 전체 측정')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(children: [
              Expanded(
                  child: FilledButton(
                      onPressed: running ? null : () => _runAsset('A'),
                      child: const Text('내장 A(양호)'))),
              const SizedBox(width: 8),
              Expanded(
                  child: FilledButton(
                      onPressed: running ? null : () => _runAsset('B'),
                      child: const Text('내장 B(어려움)'))),
              const SizedBox(width: 8),
              Expanded(
                  child: FilledButton.tonal(
                      onPressed: running ? null : _runCamera,
                      child: const Text('카메라'))),
            ]),
            const SizedBox(height: 10),
            Text(status, style: const TextStyle(fontSize: 18)),
            const SizedBox(height: 10),
            Expanded(
              child: SingleChildScrollView(
                child: Text(report,
                    style: const TextStyle(
                        fontFamily: 'monospace', fontSize: 17, height: 1.45)),
              ),
            ),
            const Text('참고: PC(파이썬) 190137 = 켬 14줄 선택, NER 0.2%',
                style: TextStyle(fontSize: 13, color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}

