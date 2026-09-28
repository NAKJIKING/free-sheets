// prep.py 대응 — 국소 이진화·오선 찾기·사진 줄 정규화 (순수 다트).
import 'dart:math' as math;
import 'dart:typed_data';

import 'gray.dart';
import 'kernels.dart';

const interline = 12.0;
const normHeight = 160;
const minW = 32, maxW = 4096;

/// gray(1=밝음) → 잉크=1 이진배열. 국소 평균보다 k 어두우면 잉크.
GrayF32 localBinarize(GrayF32 gray, {int win = 31, double k = 0.12}) {
  final mean = boxBlur(gray, math.max(3, win ~/ 2));
  final out = GrayF32(gray.w, gray.h);
  for (var i = 0; i < gray.data.length; i++) {
    out.data[i] = gray.data[i] < mean.data[i] - k ? 1.0 : 0.0;
  }
  return out;
}

class Staff {
  Staff(this.cy, this.gap);
  final double cy;
  final double gap;
}

/// prep.find_staff 정합 — 잉크배열의 행 프로파일에서 고른 5줄.
Staff? findStaff(GrayF32 a, {bool soft = false}) {
  final h = a.h, w = a.w;
  final prof = Float64List(h);
  var pmax = 0.0;
  for (var y = 0; y < h; y++) {
    var s = 0.0;
    for (var x = 0; x < w; x++) {
      s += a.data[y * w + x];
    }
    prof[y] = s;
    if (s > pmax) pmax = s;
  }
  if (pmax <= 0) return null;
  final thr = soft
      ? math.max(pmax * 0.35, w * 0.22)
      : math.max(pmax * 0.45, w * 0.5);
  final bands = <double>[];
  var i = 0;
  while (i < h) {
    if (prof[i] >= thr) {
      var j = i;
      while (j + 1 < h && prof[j + 1] >= thr) {
        j++;
      }
      bands.add((i + j) / 2.0);
      i = j + 1;
    } else {
      i++;
    }
  }
  if (bands.length < 5) return null;
  Staff? best;
  double? score;
  for (var k2 = 0; k2 + 4 < bands.length; k2++) {
    final g = List.generate(4, (m) => bands[k2 + m + 1] - bands[k2 + m]);
    final mean = g.reduce((x, y) => x + y) / 4;
    if (mean <= 1.0) continue;
    final varr =
        g.map((x) => (x - mean) * (x - mean)).reduce((x, y) => x + y) / 4;
    final s = varr / (mean * mean);
    if (score == null || s < score) {
      score = s;
      best = Staff(bands[k2 + 2], mean);
    }
  }
  if (best == null || score! > (soft ? 0.12 : 0.05)) return null;
  return best;
}

/// 간격을 알 때 오선 중심 — 다섯 빗살 응답 최대 행(크롭 중앙 ±2.5칸).
double combCenter(GrayF32 ink, double gap) {
  final h = ink.h, w = ink.w;
  final prof = Float64List(h);
  for (var y = 0; y < h; y++) {
    var s = 0.0;
    for (var x = 0; x < w; x++) {
      s += ink.data[y * w + x];
    }
    prof[y] = s;
  }
  final sm = conv3(prof);
  final acc = Float64List(h);
  for (var y = 0; y < h; y++) {
    var s = 0.0;
    for (var m = -2; m <= 2; m++) {
      s += interpAt(sm, y + m * gap);
    }
    acc[y] = s;
  }
  final mid = h / 2.0;
  var lo = math.max(0, (mid - 2.5 * gap).toInt());
  var hi = math.min(h, (mid + 2.5 * gap).toInt() + 1);
  if (hi <= lo) {
    lo = 0;
    hi = h;
  }
  var bestY = lo;
  for (var y = lo; y < hi; y++) {
    if (acc[y] > acc[bestY]) bestY = y;
  }
  return bestY.toDouble();
}

/// prep.normalize_photo 정합 — 사진 줄 크롭(gray 1=밝음) → (160, W) 잉크.
GrayF32 normalizePhoto(GrayF32 gray, {double? gapHint}) {
  final ink = localBinarize(gray);
  var st = findStaff(ink, soft: true);
  if (gapHint != null &&
      (st == null || !(0.75 * gapHint <= st.gap && st.gap <= 1.33 * gapHint))) {
    st = Staff(combCenter(ink, gapHint), gapHint);
  }
  double scale, cy;
  if (st == null) {
    scale = normHeight / math.max(1, gray.h);
    cy = gray.h / 2.0;
  } else {
    cy = st.cy;
    scale = interline / st.gap;
  }
  // a = clip(1-g), 리사이즈는 uint8 왕복(파이썬이 그렇게 한다) 정합:
  // Image.fromarray((a*255).astype(uint8)).resize(...)/255
  final a8 = GrayF32(gray.w, gray.h);
  for (var i = 0; i < gray.data.length; i++) {
    var v = 1.0 - gray.data[i];
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    a8.data[i] = (v * 255).floor() / 255.0; // astype(uint8) = 내림
  }
  final w = math.max(minW, math.min(maxW, (gray.w * scale).round()));
  final h = math.max(1, (gray.h * scale).round());
  final b = resizeBilinear(a8, w, h);
  final out = GrayF32(w, normHeight);
  final top = (cy * scale - normHeight / 2.0).round();
  final src0 = math.max(0, top), dst0 = math.max(0, -top);
  final n = math.min(h - src0, normHeight - dst0);
  for (var y = 0; y < n; y++) {
    for (var x = 0; x < w; x++) {
      out.data[(dst0 + y) * w + x] = b.data[(src0 + y) * w + x];
    }
  }
  // (H,W) 배치: out 은 폭 w 기준으로 이미 (160,w) — data 배열은 행별로
  // dst0 행 이전은 0 으로 남는다(파이썬 zeros 와 동일).
  return GrayF32.of(w, normHeight, out.data);
}
