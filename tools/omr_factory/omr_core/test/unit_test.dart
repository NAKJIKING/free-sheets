// 단위 시험 — 외부 파일 없이 도는 것들.
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:omr_core/omr_core.dart';
import 'package:test/test.dart';

Tok n(int p, int d, [bool tie = false]) => Tok(p, d, tie);
const rs = Tok(repStart, 0, false), re = Tok(repEnd, 0, false);
const v1 = Tok(volta1, 0, false), v2 = Tok(volta2, 0, false);

void main() {
  group('CTC', () {
    test('그리디: blank·중복 접기, 신뢰도', () {
      // T=4, C=3: 프레임별 최대 = 1,1,0,2 → [1,2]
      final lg = Float32List.fromList(
          [0, 5, 0, 0, 5, 0, 5, 0, 0, 0, 0, 5]);
      final d = greedyDecode(lg, 3, 16);
      expect(d.ids, [1, 2]);
      expect(d.frames, 4);
      final p = 1 / (1 + 2 * math.exp(-5));
      expect(d.conf, closeTo(p, 1e-6));
    });
    test('유효 프레임은 입력 폭/4', () {
      final lg = Float32List.fromList([0, 5, 0, 0, 0, 5]);
      expect(greedyDecode(lg, 3, 4).ids, [1]); // 4~/4 = 1프레임
    });
  });

  group('전개(unfold_tokens 대응)', () {
    test('구조 없음', () => expect(unfoldTokens([n(60, 12)]), [n(60, 12)]));
    test('|: body :|', () {
      expect(unfoldTokens([n(60, 12), rs, n(62, 12), re, n(64, 12)]),
          [n(60, 12), n(62, 12), n(62, 12), n(64, 12)]);
    });
    test('1·2번 괄호', () {
      expect(
          unfoldTokens([rs, n(60, 12), v1, n(62, 12), re, v2, n(64, 12)]),
          [n(60, 12), n(62, 12), n(60, 12), n(64, 12)]);
    });
  });

  group('음표 변환', () {
    test('붙임줄 병합·쉼표 전진·셈여림 세기', () {
      final s = buildScore([
        [n(60, 12, true), n(60, 6), n(0, 12), const Tok(dynF, 0, false), n(62, 12)],
      ]);
      expect(s, [const ScoreNote(0, 18, 60, 80), const ScoreNote(30, 12, 62, 100)]);
    });
    test('붙임줄 사슬 중간의 기호는 병합을 끊지 않는다', () {
      final s = buildScore([
        [n(60, 12, true), const Tok(dynP, 0, false), n(60, 12)],
      ]);
      expect(s, [const ScoreNote(0, 24, 60, 80)]);
    });
    test('SMF 머리·빠르기·끝', () {
      final m = writeMidi([const ScoreNote(0, 12, 60, 80)], bpm: 120);
      expect(String.fromCharCodes(m.sublist(0, 4)), 'MThd');
      expect(m.sublist(8, 14), [0, 0, 0, 1, 1, 0xe0]);
      // 500000µs = 07 A1 20
      expect(m.sublist(22, 29), [0, 0xff, 0x51, 3, 0x07, 0xa1, 0x20]);
      expect(m.sublist(m.length - 3), [0xff, 0x2f, 0]);
    });
  });

  group('가짜 줄', () {
    ScanLine line(int notes, double sq) => ScanLine(
        decode: LineDecode(List.filled(math.max(notes, 0), 1), 0.99, 10),
        toks: List.filled(notes, n(60, 12)),
        w: 400,
        sq: sq,
        cy: 0,
        gap: 12);
    test('빈 줄·음표≤2 & 약한 오선은 제거, 짧은 정상 줄은 유지', () {
      final ls = [line(0, 0.5), line(30, 0.5), line(30, 0.5), line(1, 0.6), line(2, 0.1)];
      expect(ghostMask(ls), [true, false, false, false, true]);
    });
  });

  group('WAV 청크', () {
    Uint8List wav() {
      final b = BytesBuilder()
        ..add('RIFF'.codeUnits)
        ..add([0, 0, 0, 0])
        ..add('WAVEfmt '.codeUnits)
        ..add([16, 0, 0, 0, 1, 0, 1, 0, 0x44, 0xac, 0, 0, 0x88, 0x58, 1, 0, 2, 0, 16, 0])
        ..add('data'.codeUnits)
        ..add([4, 0, 0, 0, 1, 2, 3, 4]);
      final w = b.takeBytes();
      ByteData.sublistView(w).setUint32(4, w.length - 8, Endian.little);
      return w;
    }

    test('넣기·꺼내기·바꿔넣기·빼기', () {
      final base = wav();
      final midi = Uint8List.fromList([1, 2, 3]); // 홀수 길이 → 정렬 바이트
      final e = embedScan(base, ScanPayload(midi, {'bpm': 90}));
      expect(ByteData.sublistView(e).getUint32(4, Endian.little), e.length - 8);
      final p = extractScan(e)!;
      expect(p.midi, midi);
      expect(p.meta['bpm'], 90);
      final e2 = embedScan(e, ScanPayload(Uint8List(0), {'v': 2}));
      expect(extractScan(e2)!.meta['v'], 2);
      expect(stripScan(e2), base);
      expect(extractScan(base), isNull);
    });
  });
}
