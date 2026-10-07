// 사진 한 장 인식 흐름 — 폰벤치 v5 full_bench 의 순서를 앱용으로 정리.
//   디코드 → 켬·끔 검출(isolate, 병렬 또는 순차) → 켬 인식 → 조기 결정 →
//   (필요 시) 끔 인식 → 자동선택 → 가짜 줄 제거 → 단선율 경고 → 음표.
// 추론은 [LineRecognizer] 로 주입(앱: onnxruntime 세션). 이 파일은 플랫폼 무관.
import 'dart:isolate';
import 'dart:typed_data';

import 'ctc.dart';
import 'monophony.dart';
import 'parts.dart';
import 'pipeline/gray.dart';
import 'pipeline/photo_prep.dart';
import 'pipeline/prep.dart' as prep;
import 'score.dart';
import 'select.dart';
import 'vocab.dart';

/// 한 줄 추론기 — 입력 (1,1,160,w) float32, 출력 (T×C) 로짓.
abstract class LineRecognizer {
  Future<Float32List> logits(Float32List x, int w);
}

/// 실패 종류 — 앱이 한국어 안내문으로 바꾼다(설계 5절).
enum ScanFailure { badImage, noStaff, tooFewNotes }

class ScanException implements Exception {
  ScanException(this.kind, [this.detail = '']);
  final ScanFailure kind;
  final String detail;
  @override
  String toString() => 'ScanException($kind${detail.isEmpty ? '' : ': $detail'})';
}

/// 진행 알림.
sealed class ScanEvent {}

class StageEvent extends ScanEvent {
  StageEvent(this.stage);
  final String stage; // 'decode' | 'detect' | 'recognize_on' | 'recognize_off' | 'finish'
}

class LineEvent extends ScanEvent {
  LineEvent(this.side, this.index, this.total, this.notes);
  final String side;
  final int index; // 0부터
  final int total;
  final int notes;
}

/// 검출·정규화된 줄(isolate 결과 — 텐서는 이동 전송).
class DetLine {
  DetLine(this.tensor, this.w, this.cy, this.gap, this.sq, this.heads);
  final Float32List tensor;
  final int w;
  final double cy;
  final double gap;
  final double sq;
  final HeadStats heads;
}

/// 한 경로 검출(무거운 연산, isolate 안에서 돈다).
List<DetLine> detectSide(Uint8List jpeg, bool correct) {
  GrayF32 photo;
  try {
    photo = decodeGray(jpeg);
  } catch (_) {
    throw ScanException(ScanFailure.badImage);
  }
  final out = <DetLine>[];
  for (final c in extractLines(photo, correct: correct)) {
    final t = prep.normalizePhoto(c.gray, gapHint: c.gap);
    out.add(DetLine(t.data, t.w, c.cy, c.gap, prep.staffQ(t.data, t.w),
        headStats(t.data, t.w)));
  }
  return out;
}

class ScanResult {
  ScanResult({
    required this.side,
    required this.skipped,
    required this.lines,
    required this.ghost,
    required this.mono,
    required this.timings,
  });

  /// 선택된 경로 'on' | 'off'.
  final String side;

  /// 조기 결정으로 끔 인식을 건너뛰었는지.
  final bool skipped;

  /// 선택된 경로의 전체 줄(가짜 포함, 위→아래).
  final List<ScanLine> lines;

  /// lines 와 같은 길이 — true 면 가짜 줄(출력 제외).
  final List<bool> ghost;
  final MonophonyReport mono;
  final Map<String, int> timings; // ms

  List<ScanLine> get kept => [
        for (var i = 0; i < lines.length; i++)
          if (!ghost[i]) lines[i],
      ];

  int get noteCount => kept.fold(0, (s, l) => s + l.notes);

  /// 음표가 너무 적음(설계 5절 안내 대상) — 남은 줄 < 2 이거나 음표 < [minNotes].
  bool get tooFewNotes => kept.length < 2 || noteCount < minNotes;
  double get conf => SideResult(side, kept).conf;

  List<List<Tok>> get keptTokens => [for (final l in kept) l.toks];

  /// 단(시스템)·파트 나누기 — 가짜 줄을 뺀 줄 기준.
  PartGrouping get grouping => groupParts(kept);

  /// 파트 수(1 = 단선율).
  int get partCount => grouping.k;

  /// 파트별 토큰열(위 파트부터). 단선율이면 줄을 위→아래로 이은 것 하나.
  List<List<Tok>> get partTokenLists => partTokens(kept, grouping);

  /// 파트별 연주 음표.
  List<List<ScoreNote>> get partNotes =>
      [for (final p in partTokenLists) buildScore([p])];

  /// 파트별 길이(틱) — 끝 쉼표 보존용.
  List<int> get partTicks => [for (final p in partTokenLists) scoreLength([p])];

  /// 다성부 안내(경고 아님). 단선율이면 null.
  String? get partsMessage =>
      partCount >= 2 ? '$partCount성부 악보로 인식했어요. 미리듣기에서 파트를 골라 들을 수 있어요.' : null;

  /// 전체 미디 — 단선율은 형식 0(기존과 같은 바이트), 다성부는 파트별 트랙.
  Uint8List midi({double bpm = 90}) =>
      writeMidiParts(partNotes, bpm: bpm, totalTicks: partTicks);
}

/// 음표가 이보다 적으면 실패로 본다(설계 5절).
const minNotes = 8;

class Scanner {
  Scanner(this.recognizer, this.vocab);
  final LineRecognizer recognizer;
  final Vocab vocab;

  /// [parallel]: 켬·끔 검출을 isolate 2개로 동시에(램 6GB 이상 권장) —
  /// false 면 순차(최고 메모리 감소).
  Future<ScanResult> scan(Uint8List jpeg,
      {bool parallel = true, void Function(ScanEvent)? onEvent}) async {
    final sw = Stopwatch()..start();
    final tm = <String, int>{};
    onEvent?.call(StageEvent('detect'));
    List<DetLine> on, off;
    if (parallel) {
      final r = await Future.wait([
        Isolate.run(() => detectSide(jpeg, true)),
        Isolate.run(() => detectSide(jpeg, false)),
      ]);
      on = r[0];
      off = r[1];
    } else {
      on = await Isolate.run(() => detectSide(jpeg, true));
      off = await Isolate.run(() => detectSide(jpeg, false));
    }
    tm['detect'] = sw.elapsedMilliseconds;
    if (on.isEmpty && off.isEmpty) throw ScanException(ScanFailure.noStaff);

    final heads = <String, List<HeadStats>>{
      'on': [for (final d in on) d.heads],
      'off': [for (final d in off) d.heads],
    };
    onEvent?.call(StageEvent('recognize_on'));
    final rOn = await _recognize('on', on, onEvent);
    SideResult picked;
    var skipped = false;
    if (earlyDecide(on.length, off.length, rOn.conf)) {
      picked = rOn;
      skipped = true;
    } else {
      onEvent?.call(StageEvent('recognize_off'));
      final rOff = await _recognize('off', off, onEvent);
      picked = chooseSide(rOn, rOff) == 'on' ? rOn : rOff;
    }
    tm['recognize'] = sw.elapsedMilliseconds - tm['detect']!;
    onEvent?.call(StageEvent('finish'));
    final ghost = ghostMask(picked.lines);
    final keptIdx = [
      for (var i = 0; i < ghost.length; i++)
        if (!ghost[i]) i,
    ];
    final mono = monophony([for (final i in keptIdx) heads[picked.name]![i]]);
    final res = ScanResult(
        side: picked.name,
        skipped: skipped,
        lines: picked.lines,
        ghost: ghost,
        mono: mono,
        timings: tm..['total'] = sw.elapsedMilliseconds);
    if (res.kept.isEmpty) throw ScanException(ScanFailure.noStaff);
    // 음표가 적어도 결과는 돌려준다 — 앱이 '다시 찍기 / 그래도 들어보기'를 고른다.
    return res;
  }

  Future<SideResult> _recognize(
      String name, List<DetLine> det, void Function(ScanEvent)? onEvent) async {
    final lines = <ScanLine>[];
    for (var i = 0; i < det.length; i++) {
      final d = det[i];
      final lg = await recognizer.logits(d.tensor, d.w);
      final dec = greedyDecode(lg, vocab.numClasses, d.w);
      final line = ScanLine(
          decode: dec,
          toks: vocab.tokens(dec.ids),
          w: d.w,
          sq: d.sq,
          cy: d.cy,
          gap: d.gap);
      lines.add(line);
      onEvent?.call(LineEvent(name, i, det.length, line.notes));
    }
    return SideResult(name, lines);
  }
}
