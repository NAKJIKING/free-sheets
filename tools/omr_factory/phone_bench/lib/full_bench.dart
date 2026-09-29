// [사진 한 장 전체] 측정 v4 — 검출(켬/끔) isolate 2개 병렬 → 조기 결정 →
// 인식된 줄부터 점진 표시. 폰 메모리(RSS)도 기록.
// v4: 곡 무관 규칙 — 기대 보표 수(14, 캐논 상수) 제거. 조기 결정은
// **켬/끔 검출 줄 수 차 ≤2 + 켬 신뢰도 ≥0.9975** (캐논 53장 반분 교차:
// 미학습 절반 +0.106%p·생략 38%, 비캐논 실물 43장 +0.129%p·생략 35%).
// 상수 점검: 남은 튜닝 상수는 Tc/Tn 과 conf 박빙폭 0.002 뿐(곡 무관 신호).
// adb 자동실행(route /full)이면 내장 A·B 를 돌리고 결과를 logcat 에 남긴다.
import 'dart:async';
import 'dart:convert';
import 'dart:io' show ProcessInfo;
import 'dart:isolate';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:image_picker/image_picker.dart';
import 'package:onnxruntime/onnxruntime.dart';

import 'pipeline/gray.dart';
import 'pipeline/photo_prep.dart';
import 'pipeline/prep.dart' as prep;

const _earlyConf = 0.9975; // 캐논 53장 반분 교차 튜닝(미학습 절반 검증)
const _earlyDiff = 2;      // |켬 검출 줄 − 끔 검출 줄| 허용 — 곡 무관 신호

class LineOut {
  LineOut(this.w, this.data);
  final int w;
  final Float32List data; // 160×w
}

class SideOut {
  SideOut(this.name, this.ms, this.lines);
  final String name; // 'on' | 'off'
  final int ms;
  final List<LineOut> lines;
}

// ── isolate: 한쪽 경로 검출+정규화 ──
void _sideEntry(List<Object> args) {
  final jpeg = args[0] as Uint8List;
  final side = args[1] as String;
  final progress = args[2] as SendPort;
  final result = args[3] as SendPort;
  final sw = Stopwatch()..start();
  final photo = decodeGray(jpeg);
  final crops = extractLines(photo, correct: side == 'on');
  final lines = <Object>[];
  for (var i = 0; i < crops.length; i++) {
    progress.send('$side ${i + 1}/${crops.length}');
    final t = prep.normalizePhoto(crops[i].gray, gapHint: crops[i].gap);
    lines.add([t.w, t.data]);
  }
  result.send([side, sw.elapsedMilliseconds, lines]);
}

Future<SideOut> _runSide(
    Uint8List jpeg, String side, void Function(String) onProgress) async {
  final prog = ReceivePort();
  final res = ReceivePort();
  prog.listen((m) => onProgress(m as String));
  await Isolate.spawn(_sideEntry, [jpeg, side, prog.sendPort, res.sendPort]);
  final raw = await res.first as List;
  prog.close();
  return SideOut(
      raw[0] as String,
      raw[1] as int,
      (raw[2] as List)
          .map((l) => LineOut((l as List)[0] as int, l[1] as Float32List))
          .toList());
}

class _Decoded {
  double conf = 0;
  int nonempty = 0;
  final ids = <List<int>>[];
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
  String liveLines = '';
  String footer = '';
  bool running = false;
  OrtSession? _session;
  List<int>? _pitch;

  static const _pyRef = {
    '내장 사진 A': '파이썬 기준(190137): 켬 14줄 선택, NER 0.2%',
    '내장 사진 B': '파이썬 기준(190104): 끔 16줄 선택, NER 0.5%',
    '카메라': '파이썬 기준 없음(새 사진)',
  };

  @override
  void initState() {
    super.initState();
    if (widget.autorun) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _runAll());
    }
  }

  Future<void> _runAll() async {
    await _runAsset('A');
    await _runAsset('B');
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

  int _notesOf(List<int> ids) {
    var n = 0;
    for (final k in ids) {
      if (_pitch![k - 1] > 0) n++;
    }
    return n;
  }

  Future<_Decoded> _decodeSide(SideOut s, String label) async {
    final d = _Decoded();
    var confSum = 0.0;
    var frameSum = 0;
    for (var i = 0; i < s.lines.length; i++) {
      setState(() => status = '인식 중($label) ${i + 1}/${s.lines.length}줄');
      final li = s.lines[i];
      final input =
          OrtValueTensor.createTensorWithDataList(li.data, [1, 1, 160, li.w]);
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
      d.ids.add(ids);
      if (ids.isNotEmpty) d.nonempty++;
      for (final f in use) {
        final row = (f as List).cast<double>();
        var mx = row[0];
        for (final x in row) {
          if (x > mx) mx = x;
        }
        var se = 0.0;
        for (final x in row) {
          se += math.exp(x - mx);
        }
        confSum += 1.0 / se;
      }
      frameSum += use.length;
      for (final o in outs) {
        o?.release();
      }
      // ③ 인식된 줄부터 화면에 먼저 표시
      setState(() => liveLines += '  줄 ${i + 1}: 음표 ${_notesOf(ids)}개\n');
    }
    d.conf = frameSum == 0 ? 0.0 : confSum / frameSum;
    return d;
  }

  Future<void> _runBytes(String name, Uint8List jpeg) async {
    setState(() {
      running = true;
      liveLines = '';
      status = '모델 준비…';
      footer = _pyRef[name] ?? '';
    });
    try {
      await _ensureSession();
      final total = Stopwatch()..start();
      var rssPeak = ProcessInfo.currentRss;
      void mem() {
        final r = ProcessInfo.currentRss;
        if (r > rssPeak) rssPeak = r;
      }

      setState(() => status = '검출 중(켬·끔 병렬)…');
      // ④ 켬/끔 검출을 isolate 2개로 병렬
      final results = await Future.wait([
        _runSide(jpeg, 'on', (m) {
          mem();
          if (mounted) setState(() => status = '검출·정규화 $m');
        }),
        _runSide(jpeg, 'off', (m) => mem()),
      ]);
      mem();
      final on = results[0], off = results[1];
      // ① 조기 결정(곡 무관): 켬을 먼저 인식하고, 두 검출이 구조적으로
      // 일치(줄 수 차 ≤_earlyDiff)하며 켬이 확신이면 끔 인식을 생략.
      final first = on;
      final second = off;
      final countAgree =
          (on.lines.length - off.lines.length).abs() <= _earlyDiff;
      final infer = Stopwatch()..start();
      setState(() =>
          liveLines = '[${first.name == 'on' ? '보정 켬' : '보정 끔'} 인식]\n');
      final dFirst = await _decodeSide(first, first.name == 'on' ? '켬' : '끔');
      mem();
      _Decoded picked;
      String pickName;
      var skipped = false;
      if (countAgree && dFirst.conf >= _earlyConf) {
        picked = dFirst;
        pickName = first.name;
        skipped = true;
      } else {
        setState(() => liveLines +=
            '[${second.name == 'on' ? '보정 켬' : '보정 끔'} 인식]\n');
        final dSecond =
            await _decodeSide(second, second.name == 'on' ? '켬' : '끔');
        mem();
        final onD = first.name == 'on' ? dFirst : dSecond;
        final offD = first.name == 'on' ? dSecond : dFirst;
        // 박빙(0.002)이면 비어있지 않은 줄이 많은 쪽 — 기대 줄 수(곡 상수)
        // 를 쓰지 않는 곡 무관 동률 규칙.
        if ((onD.conf - offD.conf).abs() > 0.002) {
          pickName = onD.conf >= offD.conf ? 'on' : 'off';
        } else if (onD.nonempty != offD.nonempty) {
          pickName = onD.nonempty > offD.nonempty ? 'on' : 'off';
        } else {
          pickName = onD.conf >= offD.conf ? 'on' : 'off';
        }
        picked = pickName == 'on' ? onD : offD;
      }
      final inferMs = infer.elapsedMilliseconds;
      var notes = 0;
      for (final l in picked.ids) {
        notes += _notesOf(l);
      }
      final totalMs = total.elapsedMilliseconds;
      final rssMb = (rssPeak / (1 << 20)).round();
      final buf = StringBuffer()
        ..writeln('[$name] 전체 ${(totalMs / 1000).toStringAsFixed(1)}초')
        ..writeln(
            '  검출(켬∥끔)  ${(math.max(on.ms, off.ms) / 1000).toStringAsFixed(1)}초 '
            '(켬 ${on.lines.length}줄·끔 ${off.lines.length}줄)')
        ..writeln('  인식        ${(inferMs / 1000).toStringAsFixed(1)}초 '
            '${skipped ? "— 조기 결정, ${second.name == 'on' ? '켬' : '끔'} 건너뜀" : "(양쪽)"}')
        ..writeln(
            '  선택 ${pickName == 'on' ? '보정 켬' : '보정 끔'} / 음표 $notes개')
        ..writeln('  메모리 최고  $rssMb MB');
      debugPrint('OMRBENCH_RESULT ${jsonEncode({
            'name': name,
            'totalMs': totalMs,
            'onMs': on.ms,
            'offMs': off.ms,
            'onLines': on.lines.length,
            'offLines': off.lines.length,
            'inferMs': inferMs,
            'skipped': skipped,
            'pick': pickName,
            'notes': notes,
            'rssPeakMb': rssMb,
          })}');
      setState(() {
        report = buf.toString() + report;
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
    final path = which == 'A'
        ? 'assets/photos/photo_a.jpg'
        : 'assets/photos/photo_b.jpg';
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
      appBar: AppBar(title: const Text('사진 한 장 전체 측정 v4')),
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
                child: Text('$report\n$liveLines',
                    style: const TextStyle(
                        fontFamily: 'monospace', fontSize: 16, height: 1.4)),
              ),
            ),
            Text(footer,
                style: const TextStyle(fontSize: 13, color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}
