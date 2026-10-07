// 화음(한 박자에 여러 음) 징후 — 결과 화면 경고용. 파이썬 기준:
// omr_core/tool/poly_signals.py (head_mask·head_blobs·head_stats). 보정 근거는
// 진행일지 2026-10-07 S1 절. 보표 쌍(2중주 등)은 경고가 아니라 파트 나누기
// 대상이다 — parts.dart(사장님 지적 10-07: 2중주의 각 보표는 단선율).
//
// 모델은 화음을 한 음으로 확신 있게 읽는다(렌더 실측: 3화음 줄 신뢰도 0.988,
// 피아노 0.999) — 토큰만으로는 화음을 알 수 없어서 **이미지 신호**를 쓴다.
//  쌓인 음표머리: 오선 행 제거 → 빈 머리 속 채우기 → 열기 7 로 기둥·빔·
//     덧줄·임시표 획을 지운 뒤, 음표머리 폭(12~22px) 덩어리 중 높이 24px
//     (2칸) 이상인 것의 비율. 한계: 빈 머리(2분·온음표) 화음·2도 화음은 약하다.
import 'dart:math' as math;
import 'dart:typed_data';

/// 쌓인 머리 비율 문턱 — 이 이상이면 "여러 음이 겹친 곳" 경고.
/// 보정(진행일지 S1): 렌더 3화음 1.00·2중음 0.22 / 단선율 함정 0~0.01,
/// 실물 96장 오탐 1장(가혹 촬영 0.105).
const stackedFracWarn = 0.08;

/// 쌓였다고 보는 머리 덩어리 높이(px, 정규화 텐서 기준 = 2칸).
const stackedPx = 24;

/// 채울 구멍(빈 머리 속) 크기 상한.
const holeMaxPx = 60, holeMaxH = 8;

/// 머리 덩어리 조건: 최소 높이, 폭 범위(임시표 8~9px·빔은 제외).
const headMinH = 8, headMinW = 12, headMaxW = 22;

/// 줄 앞 음자리표·조표(최대 7개)·박자표·빠르기표 구간(px)은 뺀다.
const headSkipPx = 160;

/// 정규화 텐서의 오선 행(간격 12, 중앙 80).
const staffRows = [56, 68, 80, 92, 104];

/// 줄 하나의 음표머리 통계.
class HeadStats {
  const HeadStats(this.heads, this.tall);
  final int heads; // 머리 덩어리 수
  final int tall; // 그중 높이 ≥ stackedPx
}

final _f32 = Float32List(1);
double _fr(double v) {
  _f32[0] = v;
  return _f32[0];
}

Uint8List _filt(Uint8List m, int h, int w, int k, bool isMax) {
  final r = k ~/ 2;
  var cur = m;
  // 분리형, 가장자리는 창을 안쪽으로 줄인다(파이썬 np.take 복제와 동일).
  for (final horiz in [false, true]) {
    final out = Uint8List(h * w);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        var v = cur[y * w + x];
        for (var d = 1; d <= r; d++) {
          int a, b;
          if (horiz) {
            a = cur[y * w + math.min(w - 1, x + d)];
            b = cur[y * w + math.max(0, x - d)];
          } else {
            a = cur[math.min(h - 1, y + d) * w + x];
            b = cur[math.max(0, y - d) * w + x];
          }
          v = isMax ? math.max(v, math.max(a, b)) : math.min(v, math.min(a, b));
        }
        out[y * w + x] = v;
      }
    }
    cur = out;
  }
  return cur;
}

/// np.median(float32) 과 같은 값 — 짝수 개면 float32 (a+b)/2.
double _median32(Float32List a) {
  final s = Float32List.fromList(a)..sort();
  final n = s.length;
  if (n == 0) return 0;
  if (n.isOdd) return s[n ~/ 2];
  return _fr(_fr(s[n ~/ 2 - 1] + s[n ~/ 2]) / 2);
}

/// 4-연결 성분 순회 — 성분마다 (y0, x0, y1, x1, 화소 목록) 콜백.
void _components(Uint8List m, int h, int w,
    void Function(int y0, int x0, int y1, int x1, List<int> px) f) {
  final seen = Uint8List(h * w);
  final stack = <int>[];
  for (var i = 0; i < h * w; i++) {
    if (m[i] == 0 || seen[i] != 0) continue;
    seen[i] = 1;
    stack.add(i);
    final px = <int>[];
    var y0 = h, x0 = w, y1 = -1, x1 = -1;
    while (stack.isNotEmpty) {
      final p = stack.removeLast();
      px.add(p);
      final y = p ~/ w, x = p % w;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      void push(int q) {
        if (m[q] != 0 && seen[q] == 0) {
          seen[q] = 1;
          stack.add(q);
        }
      }

      if (y > 0) push(p - w);
      if (y < h - 1) push(p + w);
      if (x > 0) push(p - 1);
      if (x < w - 1) push(p + 1);
    }
    f(y0, x0, y1, x1, px);
  }
}

/// 음표머리만 남긴 마스크(poly_signals.head_mask 와 같은 식).
Uint8List headMask(Float32List a, int w, {int h = 160}) {
  final med = _median32(a);
  final m = Uint8List(h * w);
  for (var i = 0; i < m.length; i++) {
    m[i] = _fr(a[i] - med) > 0.3 ? 1 : 0;
  }
  // 오선 행(±1) 중 바로 위·아래가 빈 열의 화소 제거
  for (final r in staffRows) {
    final top = r - 1, bot = r + 1;
    if (top - 1 < 0 || bot + 1 >= h) continue;
    for (var x = 0; x < w; x++) {
      if (m[(top - 1) * w + x] == 0 && m[(bot + 1) * w + x] == 0) {
        for (var y = top; y <= bot; y++) {
          m[y * w + x] = 0;
        }
      }
    }
  }
  // 닫힌 구멍(테두리에 닿지 않는 200px 미만 배경 성분) 채우기
  final inv = Uint8List(h * w);
  for (var i = 0; i < inv.length; i++) {
    inv[i] = 1 - m[i];
  }
  _components(inv, h, w, (y0, x0, y1, x1, px) {
    // 빈 머리 속 크기만(높이 ≤8px, 60px 미만) — 덜 지워진 오선과 획 사이
    // 틈까지 메우면 단선율 사진에서 큰 덩어리가 생긴다(실측 174720).
    if (y0 > 0 &&
        x0 > 0 &&
        y1 < h - 1 &&
        x1 < w - 1 &&
        px.length < holeMaxPx &&
        y1 - y0 + 1 <= holeMaxH) {
      for (final p in px) {
        m[p] = 1;
      }
    }
  });
  return _filt(_filt(m, h, w, 7, false), h, w, 7, true); // 열기 7
}

/// 정규화 텐서(160×w) → 음표머리 통계.
HeadStats headStats(Float32List a, int w, {int h = 160}) {
  final m = headMask(a, w, h: h);
  var heads = 0, tall = 0;
  _components(m, h, w, (y0, x0, y1, x1, px) {
    final bh = y1 - y0 + 1, bw = x1 - x0 + 1;
    if (x0 < headSkipPx || bh < headMinH || bw < headMinW || bw > headMaxW) {
      return;
    }
    heads++;
    if (bh >= stackedPx) tall++;
  });
  return HeadStats(heads, tall);
}

/// 페이지 단위 판정.
class MonophonyReport {
  const MonophonyReport(this.stackedFrac);
  final double stackedFrac;

  /// 경고를 띄울지 — 쌓인 음표머리(진짜 화음)일 때만.
  bool get warn => stackedFrac >= stackedFracWarn;

  /// 결과 화면 경고 문구(없으면 null).
  String? get message => warn
      ? '한 박자에 여러 음이 겹친 곳(화음)이 보여요. 한 줄 선율만 인식하므로 '
          '겹친 음은 하나만 들려요.'
      : null;
}

/// [heads]: 가짜 줄을 뺀 줄들의 음표머리 통계.
MonophonyReport monophony(List<HeadStats> heads) {
  var n = 0, tall = 0;
  for (final h in heads) {
    n += h.heads;
    tall += h.tall;
  }
  return MonophonyReport(n == 0 ? 0.0 : tall / n);
}