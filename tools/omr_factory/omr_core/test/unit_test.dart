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

  group('파트 SMF', () {
    test('1파트 = writeMidi 와 같은 바이트, 2파트 = 형식 1·트랙 2·채널 0/1', () {
      final a = [const ScoreNote(0, 12, 60, 80)];
      final b = [const ScoreNote(0, 24, 55, 80)];
      expect(writeMidiParts([a], bpm: 100), writeMidi(a, bpm: 100));
      final m = writeMidiParts([a, b], bpm: 100);
      expect(m.sublist(8, 14), [0, 1, 0, 2, 1, 0xe0]);
      // 둘째 트랙에는 빠르기 메타가 없고 채널 1 로 연주
      final second = m.lastIndexOf(0x4d); // 'M' of last MTrk
      expect(String.fromCharCodes(m.sublist(second, second + 4)), 'MTrk');
      expect(m.sublist(second + 8, second + 11), [0x00, 0xc1, 0]);
      expect(m.sublist(second + 11, second + 15), [0x00, 0x91, 55, 80]);
    });
  });

  group('파트 나누기', () {
    ScanLine at(double cy) => ScanLine(
        decode: LineDecode([1], 0.99, 10),
        toks: [n(60, 12)],
        w: 400,
        sq: 1,
        cy: cy,
        gap: 10);
    test('간격이 고르면 1파트', () {
      expect(groupParts([for (var i = 0; i < 8; i++) at(100.0 + 100 * i)]).k, 1);
    });
    test('작은·큰 교대면 2파트, 빠진 보표는 자리 추정 + 쉼표 채움', () {
      // 단 안 100, 단 사이 250(단 간격 350) — 둘째 단의 아래 보표 누락
      final ls = [at(0), at(100), at(350), at(700), at(800)];
      final g = groupParts(ls);
      expect(g.k, 2);
      expect(g.systems[1], [(0, 2)]);
      final pt = partTokens(ls, g);
      expect(pt[1][1], const Tok(0, 12, false)); // 빠진 자리는 그 단 길이 쉼표
    });
  });

  group('긴 변 축소', () {
    test('작으면 그대로, 크면 비율 유지·8비트 값', () {
      final g = GrayF32(300, 400);
      for (var i = 0; i < g.data.length; i++) {
        g.data[i] = (i % 256) / 255.0;
      }
      expect(identical(capLongSide(g, null), g), isTrue);
      expect(identical(capLongSide(g, 400), g), isTrue);
      final r = capLongSide(g, 200);
      expect([r.w, r.h], [150, 200]);
      for (final v in r.data) {
        expect((v * 255 - (v * 255).round()).abs(), lessThan(1e-3));
      }
      final wide = capLongSide(GrayF32(1000, 30), 500);
      expect([wide.w, wide.h], [500, 15]);
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
