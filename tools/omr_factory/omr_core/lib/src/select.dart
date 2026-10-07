// 켬/끔 선택(v4 조기 결정·자동선택) + 가짜 줄 제거(v5).
// 근거·튜닝: free-sheets tools/omr_factory/진행일지.md (2026-09-29 v4, 2026-10-06 v5).
import 'ctc.dart';
import 'vocab.dart';

/// 조기 결정: 켬 신뢰도 하한(캐논 53장 반분 교차 튜닝).
const earlyConf = 0.9975;

/// 조기 결정: |켬 검출 줄 − 끔 검출 줄| 허용(곡 무관 구조 일치 신호).
const earlyDiff = 2;

/// 자동선택 박빙 폭 — 신뢰도 차가 이 이하면 비어있지 않은 줄 수로 가른다.
const tieBand = 0.002;

/// 가짜 줄: 음표 이 수 이하이면서 …
const ghostNotes = 2;

/// … 오선 대비가 페이지 중앙값의 이 비율 미만이면 제거.
const ghostStaffQ = 0.3;

/// 인식된 줄 하나(검출 위치 + 디코드 + 오선 대비).
class ScanLine {
  ScanLine({
    required this.decode,
    required this.toks,
    required this.w,
    required this.sq,
    required this.cy,
    required this.gap,
  });
  final LineDecode decode;
  final List<Tok> toks;
  final int w; // 정규화 텐서 폭
  final double sq; // prep.staffQ
  final double cy; // 원해상도 중심 y
  final double gap; // 원해상도 오선 간격

  int get notes => toks.where((t) => t.isNote).length;
  bool get empty => decode.ids.isEmpty;
}

/// 한 경로(보정 켬 또는 끔)의 인식 결과.
class SideResult {
  SideResult(this.name, this.lines);
  final String name; // 'on' | 'off'
  final List<ScanLine> lines;

  /// 프레임 가중 평균 신뢰도.
  double get conf {
    var s = 0.0;
    var n = 0;
    for (final l in lines) {
      s += l.decode.conf * l.decode.frames;
      n += l.decode.frames;
    }
    return n == 0 ? 0.0 : s / n;
  }

  int get nonempty => lines.where((l) => !l.empty).length;
}

/// 켬을 먼저 인식한 뒤 끔 인식을 생략해도 되는가 (검출 줄 수만 필요).
bool earlyDecide(int onDetected, int offDetected, double onConf) =>
    (onDetected - offDetected).abs() <= earlyDiff && onConf >= earlyConf;

/// 양쪽을 모두 인식했을 때의 자동선택 — 'on' | 'off'.
String chooseSide(SideResult on, SideResult off) {
  final dc = on.conf - off.conf;
  if (dc.abs() > tieBand) return dc >= 0 ? 'on' : 'off';
  if (on.nonempty != off.nonempty) {
    return on.nonempty > off.nonempty ? 'on' : 'off';
  }
  return on.conf >= off.conf ? 'on' : 'off';
}

/// 가짜 줄(제목·여백 오검출) 표시 — true 면 최종 출력에서 뺀다.
/// 토큰이 없는 줄, 또는 (음표 ≤2 이고 sq < 페이지 중앙값×0.3).
List<bool> ghostMask(List<ScanLine> lines) {
  final sqs = [for (final l in lines) l.sq]..sort();
  final med = sqs.isEmpty ? 1.0 : sqs[sqs.length ~/ 2];
  return [
    for (final l in lines)
      l.empty || (l.notes <= ghostNotes && l.sq < ghostStaffQ * med),
  ];
}

/// 가짜 줄을 뺀 줄 목록(위→아래 순서 유지).
List<ScanLine> keptLines(List<ScanLine> lines) {
  final m = ghostMask(lines);
  return [
    for (var i = 0; i < lines.length; i++)
      if (!m[i]) lines[i],
  ];
}
