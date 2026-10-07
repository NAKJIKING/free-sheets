// 파이썬 기준과의 정합 — 캐논 53 + 비캐논 43장, 텐서 235줄.
// 기준값: tool/make_fixture.py → C:/Users/user/omr_core_fixture/fixture.json
// (모델·사진은 저장소 밖이라 기준 파일이 없으면 이 시험은 건너뛴다.)
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:omr_core/omr_core.dart';
import 'package:test/test.dart';

const fixturePath = 'C:/Users/user/omr_core_fixture/fixture.json';
const vocabPath = 'C:/Users/user/omr_model_3c4/vocab.json';

SideResult side(String name, Map<String, dynamic> s, Vocab v) => SideResult(name, [
      for (final l in (s['lines'] as List).cast<Map<String, dynamic>>())
        ScanLine(
          decode: LineDecode((l['ids'] as List).cast<int>(),
              (l['conf'] as num).toDouble(), l['frames'] as int),
          toks: v.tokens((l['ids'] as List).cast<int>()),
          w: l['w'] as int,
          sq: (l['sq'] as num).toDouble(),
          cy: (l['cy'] as num).toDouble(),
          gap: (l['gap'] as num).toDouble(),
        ),
    ]);

void main() {
  final f = File(fixturePath);
  if (!f.existsSync() || !File(vocabPath).existsSync()) {
    test('fixture 없음 — 건너뜀', () {}, skip: '기준 파일 없음');
    return;
  }
  final fx = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
  final vocab = Vocab.fromJsonString(File(vocabPath).readAsStringSync());
  final photos = (fx['photos'] as List).cast<Map<String, dynamic>>();

  test('선택·조기결정·가짜줄·보표쌍·음표·SMF — ${photos.length}장 파이썬 일치', () {
    var midiSame = 0;
    for (final p in photos) {
      final name = p['photo'] as String;
      final on = side('on', p['on'], vocab), off = side('off', p['off'], vocab);
      final early = earlyDecide(
          p['on']['n'] as int, p['off']['n'] as int, on.conf);
      final pick = early ? 'on' : chooseSide(on, off);
      expect(early, p['skipped'], reason: name);
      expect(pick, p['pick'], reason: name);
      final picked = pick == 'on' ? on : off;
      final gm = ghostMask(picked.lines);
      expect(gm, (p['ghost'] as List).cast<bool>(), reason: name);
      final kept = keptLines(picked.lines);
      final mono = monophony(kept, [for (final _ in kept) const HeadStats(0, 0)]);
      expect(mono.pairAlt, closeTo((p['pair_alt'] as num).toDouble(), 1e-9),
          reason: name);
      expect(mono.pairRatio, closeTo((p['pair_ratio'] as num).toDouble(), 1e-9),
          reason: name);
      final toks = [for (final l in kept) l.toks];
      final notes = buildScore(toks);
      expect(
          notes,
          [
            for (final n in (p['notes'] as List).cast<List>())
              ScoreNote(n[0] as int, n[1] as int, n[2] as int, n[3] as int),
          ],
          reason: name);
      expect(scoreLength(toks), p['total'], reason: name);
      final midi = writeMidi(notes, bpm: 90, totalTicks: scoreLength(toks));
      if (base64Encode(midi) == p['midi']) midiSame++;
    }
    expect(midiSame, photos.length, reason: 'SMF 바이트 일치');
  });

  test('staffQ·음표머리 통계 — 텐서 파이썬 일치', () {
    final dir = fx['tensor_dir'] as String;
    final ts = (fx['tensors'] as List).cast<Map<String, dynamic>>();
    var headSame = 0;
    for (final t in ts) {
      final bytes = File('$dir/${t['file']}').readAsBytesSync();
      final a = Float32List.view(Uint8List.fromList(bytes).buffer);
      final w = t['w'] as int;
      expect(staffQ(a, w), closeTo((t['sq'] as num).toDouble(), 1e-9),
          reason: t['file'] as String);
      final h = headStats(a, w);
      if (h.heads == t['heads'] && h.tall == t['tall']) headSame++;
    }
    expect(headSame, ts.length, reason: '음표머리 통계 일치 줄 수');
  });
}
