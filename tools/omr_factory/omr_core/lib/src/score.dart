// 토큰 → 연주 음표 → 미디(SMF). 파이썬 기준: lib_lines.unfold_tokens,
// evaluate.write_midi(붙임줄 병합·쉼표 누적), 셈여림 세기는 앱 정책(아래 표).
import 'dart:typed_data';

import 'vocab.dart';

/// 4분음표 틱(토큰 길이 단위).
const quarter = 12;

/// 미디 분해능(4분음표당 틱) — write_midi 와 같다.
const tpq = 480;

/// 셈여림 → 세기. 표기가 없으면 [defaultVel]. 크레셴도는 1차 무시.
const dynVel = {dynF: 100, dynMf: 80, dynP: 60};
const defaultVel = 80;

/// 연주 음표 하나(토큰 틱 단위, 4분=12).
class ScoreNote {
  const ScoreNote(this.start, this.dur, this.key, this.vel);
  final int start;
  final int dur;
  final int key;
  final int vel;

  @override
  bool operator ==(Object other) =>
      other is ScoreNote &&
      other.start == start &&
      other.dur == dur &&
      other.key == key &&
      other.vel == vel;
  @override
  int get hashCode => Object.hash(start, dur, key, vel);
  @override
  String toString() => 'N($start+$dur k$key v$vel)';
}

/// 반복 구조 전개 (lib_lines.unfold_tokens 완역).
///   pre RS body RE post          → pre body body post
///   pre RS body V1 a1 RE V2 a2   → pre body a1 body a2
List<Tok> unfoldTokens(List<Tok> tokens) {
  final pre = <Tok>[], body = <Tok>[], a1 = <Tok>[], a2 = <Tok>[];
  final post = <Tok>[];
  var cur = pre;
  var seen = false;
  for (final t in tokens) {
    // 구조 표지는 (음고, 0, 붙임줄 없음) 정확 일치일 때만 — 파이썬과 같다.
    final isMark = t.dur == 0 && !t.tie;
    if (isMark && t.pitch == repStart) {
      cur = body;
      seen = true;
    } else if (isMark && t.pitch == volta1) {
      cur = a1;
    } else if (isMark && t.pitch == repEnd) {
      cur = post;
    } else if (isMark && t.pitch == volta2) {
      cur = a2;
    } else {
      cur.add(t);
    }
  }
  if (!seen) return List.of(tokens);
  if (a2.isNotEmpty) return [...pre, ...body, ...a1, ...body, ...a2];
  return [...pre, ...body, ...body, ...post];
}

/// 줄들(위→아래) → 연주 음표. 이어붙이기 → 전개 → 셈여림 세기 →
/// 기호 제거 → 붙임줄 병합 → 시간 배치(쉼표는 시간만 전진).
List<ScoreNote> buildScore(List<List<Tok>> lines) {
  final toks = unfoldTokens([for (final l in lines) ...l]);
  // 셈여림은 기호 제거 전에 읽어 뒤따르는 음에 붙인다.
  final seq = <(Tok, int)>[];
  var vel = defaultVel;
  for (final t in toks) {
    if (t.pitch < 0) {
      vel = dynVel[t.pitch] ?? vel;
      continue;
    }
    seq.add((t, vel));
  }
  final out = <ScoreNote>[];
  var tick = 0;
  var i = 0;
  while (i < seq.length) {
    final (t0, v) = seq[i];
    var d = t0.dur;
    var tie = t0.tie;
    i++;
    while (tie && i < seq.length && seq[i].$1.pitch == t0.pitch) {
      d += seq[i].$1.dur;
      tie = seq[i].$1.tie;
      i++;
    }
    if (t0.pitch > 0) out.add(ScoreNote(tick, d, t0.pitch, v));
    tick += d;
  }
  return out;
}

/// 전체 길이(틱) — 마지막 쉼표까지 포함하려면 토큰 합이 필요하므로 별도 계산.
int scoreLength(List<List<Tok>> lines) {
  var n = 0;
  for (final t in unfoldTokens([for (final l in lines) ...l])) {
    if (t.pitch >= 0) n += t.dur;
  }
  return n;
}

/// 틱 → 초.
double tickSeconds(int tick, double bpm) => tick / quarter * 60.0 / bpm;

void _vlq(BytesBuilder b, int v) {
  final stack = [v & 0x7f];
  v >>= 7;
  while (v > 0) {
    stack.add((v & 0x7f) | 0x80);
    v >>= 7;
  }
  for (var k = stack.length - 1; k >= 0; k--) {
    b.addByte(stack[k]);
  }
}

/// SMF(형식 0, 트랙 1) — evaluate.write_midi 와 같은 바이트 배치(세기만
/// 음표별). [totalTicks] 를 주면 끝 쉼표까지 길이를 보존한다.
Uint8List writeMidi(List<ScoreNote> notes,
    {double bpm = 90, int program = 0, int? totalTicks}) {
  final ev = BytesBuilder();
  final us = (60000000 / bpm).floor();
  ev.add([0x00, 0xff, 0x51, 0x03, (us >> 16) & 0xff, (us >> 8) & 0xff, us & 0xff]);
  ev.add([0x00, 0xc0, program]);
  const k = tpq ~/ quarter; // 40
  var at = 0; // 토큰 틱 기준 현재 위치
  for (final n in notes) {
    _vlq(ev, (n.start - at) * k);
    ev.add([0x90, n.key, n.vel]);
    _vlq(ev, n.dur * k);
    ev.add([0x80, n.key, 0]);
    at = n.start + n.dur;
  }
  _vlq(ev, ((totalTicks ?? at) - at).clamp(0, 1 << 27) * k);
  ev.add([0xff, 0x2f, 0x00]);
  final trk = ev.takeBytes();
  final b = BytesBuilder()
    ..add('MThd'.codeUnits)
    ..add(_u32(6))
    ..add([0, 0, 0, 1, tpq >> 8, tpq & 0xff])
    ..add('MTrk'.codeUnits)
    ..add(_u32(trk.length))
    ..add(trk);
  return b.takeBytes();
}

/// 파트별 SMF. 파트가 하나면 [writeMidi] 와 **같은 바이트**(형식 0 — 단선율
/// 회귀 없음). 둘 이상이면 형식 1·파트마다 트랙 하나·채널 j(타악기 채널 9 건너뜀),
/// 빠르기는 첫 트랙에만.
Uint8List writeMidiParts(List<List<ScoreNote>> parts,
    {double bpm = 90, int program = 0, List<int>? totalTicks}) {
  if (parts.length == 1) {
    return writeMidi(parts[0],
        bpm: bpm, program: program, totalTicks: totalTicks?.first);
  }
  final b = BytesBuilder()
    ..add('MThd'.codeUnits)
    ..add(_u32(6))
    ..add([0, 1, (parts.length >> 8) & 0xff, parts.length & 0xff, tpq >> 8, tpq & 0xff]);
  const k = tpq ~/ quarter;
  for (var j = 0; j < parts.length; j++) {
    final ch = j < 9 ? j : j + 1;
    final ev = BytesBuilder();
    if (j == 0) {
      final us = (60000000 / bpm).floor();
      ev.add([0x00, 0xff, 0x51, 0x03, (us >> 16) & 0xff, (us >> 8) & 0xff, us & 0xff]);
    }
    ev.add([0x00, 0xc0 | ch, program]);
    var at = 0;
    for (final n in parts[j]) {
      _vlq(ev, (n.start - at) * k);
      ev.add([0x90 | ch, n.key, n.vel]);
      _vlq(ev, n.dur * k);
      ev.add([0x80 | ch, n.key, 0]);
      at = n.start + n.dur;
    }
    final total = totalTicks?[j] ?? at;
    _vlq(ev, (total - at).clamp(0, 1 << 27) * k);
    ev.add([0xff, 0x2f, 0x00]);
    final trk = ev.takeBytes();
    b
      ..add('MTrk'.codeUnits)
      ..add(_u32(trk.length))
      ..add(trk);
  }
  return b.takeBytes();
}

List<int> _u32(int v) => [(v >> 24) & 0xff, (v >> 16) & 0xff, (v >> 8) & 0xff, v & 0xff];
