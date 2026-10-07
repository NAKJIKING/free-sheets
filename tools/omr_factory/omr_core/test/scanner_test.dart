// Scanner 흐름 점검 — 실제 다트 검출(사진 A, 190137) + 가짜 추론기.
// 추론 정확도가 아니라 배선(병렬/순차 검출·조기 결정·가짜 줄·경고·이벤트)을 본다.
import 'dart:io';
import 'dart:typed_data';

import 'package:omr_core/omr_core.dart';
import 'package:test/test.dart';

const photoA = 'C:/Users/user/omr_phone_bench_assets/pipe/20260921_190137/photo.jpg';

/// 프레임마다 (음표 클래스, blank) 를 번갈아 내는 확신 높은 로짓.
class FakeRecognizer implements LineRecognizer {
  FakeRecognizer(this.numClasses, this.noteClass);
  final int numClasses;
  final int noteClass;
  int calls = 0;
  @override
  Future<Float32List> logits(Float32List x, int w) async {
    calls++;
    final t = w ~/ 4;
    final out = Float32List(t * numClasses);
    for (var f = 0; f < t; f++) {
      out[f * numClasses + (f.isEven ? noteClass : 0)] = 20;
    }
    return out;
  }
}

void main() {
  if (!File(photoA).existsSync()) {
    test('사진 없음 — 건너뜀', () {}, skip: '사진 A 없음');
    return;
  }
  // 작은 어휘: 1 = (72, 3, 0) 음표 하나.
  final vocab = Vocab([const Tok(72, 3, false)]);

  for (final parallel in [true, false]) {
    test('사진 A — ${parallel ? '병렬' : '순차'} 검출, 조기 결정', () async {
      final rec = FakeRecognizer(vocab.numClasses, 1);
      final events = <ScanEvent>[];
      final r = await Scanner(rec, vocab).scan(
          File(photoA).readAsBytesSync(),
          parallel: parallel,
          onEvent: events.add);
      // 확신 1.0 + 켬/끔 줄 수 차 ≤2(켬 14·끔 12) → 끔 인식 생략
      expect(r.side, 'on');
      expect(r.skipped, isTrue);
      expect(r.lines.length, 14);
      expect(rec.calls, 14);
      expect(r.ghost.where((g) => g), isEmpty);
      expect(r.noteCount, greaterThan(100));
      expect(r.tooFewNotes, isFalse);
      // 캐논은 2중주 — 보표 쌍 경고가 떠야 한다
      expect(r.mono.pairedStaves, isTrue, reason: '${r.mono.pairAlt} ${r.mono.pairRatio}');
      expect(events.whereType<LineEvent>().length, 14);
      expect(r.notes, isNotEmpty);
      expect(r.timings['total'], greaterThan(0));
    }, timeout: const Timeout(Duration(minutes: 3)));
  }

  test('깨진 이미지 → badImage', () async {
    final s = Scanner(FakeRecognizer(2, 1), vocab);
    await expectLater(s.scan(Uint8List.fromList([1, 2, 3])),
        throwsA(isA<ScanException>().having((e) => e.kind, 'kind', ScanFailure.badImage)));
  });
}
