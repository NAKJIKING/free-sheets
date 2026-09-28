// 공통 프리미티브 — 파이썬(PIL·numpy) 연산과 수치 정합을 맞춘 순수 다트 커널.
//
// 핵심 정합 규약:
//  - resize BILINEAR: PIL 은 다운스케일 때 삼각 필터 콘볼루션(안티앨리어스)
//    이다. 순진한 4점 보간이 아니라 support=scale 창의 가중합으로 구현.
//  - rotate/affine/perspective BILINEAR: 출력 화소 중심 (x+0.5, y+0.5) 을
//    역매핑해 (xin-0.5, yin-0.5) 에서 4점 보간 (PIL ImagingTransform 규약).
//  - BoxBlur(r): (2r+1) 정수 상자 1회 (PIL 의 소수 반경 가장자리 가중은 생략
//    — 게이트(NER +1%p)로 흡수, 진행일지에 기록).
import 'dart:math' as math;
import 'dart:typed_data';

import 'gray.dart';

// ───────────────────────── resize (PIL 필터 방식) ─────────────────────────

class _Weights {
  _Weights(this.bounds, this.kk, this.ksize);
  final Int32List bounds; // out 픽셀마다 [시작, 개수]
  final Float64List kk;
  final int ksize;
}

_Weights _precompute(int inSize, int outSize) {
  final scale = inSize / outSize;
  final filterscale = math.max(scale, 1.0);
  final support = 1.0 * filterscale; // BILINEAR support=1
  final ksize = support.ceil() * 2 + 1;
  final bounds = Int32List(outSize * 2);
  final kk = Float64List(outSize * ksize);
  for (var xx = 0; xx < outSize; xx++) {
    final center = (xx + 0.5) * scale;
    var xmin = (center - support + 0.5).floor();
    if (xmin < 0) xmin = 0;
    var xmax = (center + support + 0.5).floor();
    if (xmax > inSize) xmax = inSize;
    var wsum = 0.0;
    var n = 0;
    for (var x = xmin; x < xmax; x++) {
      final d = (x + 0.5 - center) / filterscale;
      final wgt = d.abs() < 1.0 ? 1.0 - d.abs() : 0.0;
      kk[xx * ksize + n] = wgt;
      wsum += wgt;
      n++;
    }
    if (wsum != 0) {
      for (var i = 0; i < n; i++) {
        kk[xx * ksize + i] /= wsum;
      }
    }
    bounds[xx * 2] = xmin;
    bounds[xx * 2 + 1] = n;
  }
  return _Weights(bounds, kk, ksize);
}

/// PIL Image.resize(..., BILINEAR) 정합 리사이즈.
GrayF32 resizeBilinear(GrayF32 src, int ow, int oh) {
  if (ow == src.w && oh == src.h) return src.clone();
  final wx = _precompute(src.w, ow);
  final tmp = GrayF32(ow, src.h);
  for (var y = 0; y < src.h; y++) {
    final row = y * src.w;
    for (var x = 0; x < ow; x++) {
      final x0 = wx.bounds[x * 2];
      final n = wx.bounds[x * 2 + 1];
      var s = 0.0;
      for (var i = 0; i < n; i++) {
        s += src.data[row + x0 + i] * wx.kk[x * wx.ksize + i];
      }
      tmp.data[y * ow + x] = s;
    }
  }
  final wy = _precompute(src.h, oh);
  final out = GrayF32(ow, oh);
  for (var y = 0; y < oh; y++) {
    final y0 = wy.bounds[y * 2];
    final n = wy.bounds[y * 2 + 1];
    for (var x = 0; x < ow; x++) {
      var s = 0.0;
      for (var i = 0; i < n; i++) {
        s += tmp.data[(y0 + i) * ow + x] * wy.kk[y * wy.ksize + i];
      }
      out.data[y * ow + x] = s;
    }
  }
  return out;
}

/// PIL NEAREST 리사이즈 (마스크용).
GrayF32 resizeNearest(GrayF32 src, int ow, int oh) {
  final out = GrayF32(ow, oh);
  for (var y = 0; y < oh; y++) {
    var sy = ((y + 0.5) * src.h / oh).floor();
    if (sy >= src.h) sy = src.h - 1;
    for (var x = 0; x < ow; x++) {
      var sx = ((x + 0.5) * src.w / ow).floor();
      if (sx >= src.w) sx = src.w - 1;
      out.data[y * ow + x] = src.data[sy * src.w + sx];
    }
  }
  return out;
}

// ───────────────────── 역매핑 보간 (rotate·perspective) ─────────────────────

double _sampleBilinear(GrayF32 src, double xin, double yin, double fill) {
  final xf = xin - 0.5, yf = yin - 0.5;
  final x0 = xf.floor(), y0 = yf.floor();
  final tx = xf - x0, ty = yf - y0;
  double px(int x, int y) {
    if (x < 0 || y < 0 || x >= src.w || y >= src.h) return fill;
    return src.data[y * src.w + x];
  }

  return px(x0, y0) * (1 - tx) * (1 - ty) +
      px(x0 + 1, y0) * tx * (1 - ty) +
      px(x0, y0 + 1) * (1 - tx) * ty +
      px(x0 + 1, y0 + 1) * tx * ty;
}

/// PIL Image.rotate(deg, BILINEAR, expand, fillcolor) 정합.
/// deg 는 반시계 방향(도). expand=false 면 크기 유지·중심 회전.
GrayF32 rotate(GrayF32 src, double deg,
    {bool expand = false, double fill = 0.0}) {
  final rad = -deg * math.pi / 180.0; // 출력→입력 역매핑
  final c = math.cos(rad), s = math.sin(rad);
  int ow = src.w, oh = src.h;
  if (expand) {
    final cw = (src.w * c.abs() + src.h * s.abs()).ceil();
    final ch = (src.w * s.abs() + src.h * c.abs()).ceil();
    ow = cw;
    oh = ch;
  }
  final cx = ow / 2.0, cy = oh / 2.0;
  final icx = src.w / 2.0, icy = src.h / 2.0;
  final out = GrayF32(ow, oh);
  for (var y = 0; y < oh; y++) {
    final dy = (y + 0.5) - cy;
    for (var x = 0; x < ow; x++) {
      final dx = (x + 0.5) - cx;
      final xin = c * dx - s * dy + icx;
      final yin = s * dx + c * dy + icy;
      out.data[y * ow + x] = _sampleBilinear(src, xin, yin, fill);
    }
  }
  return out;
}

/// 8×8 선형계 풀이 (부분 피벗 가우스 소거) — _persp_coeffs 대응.
Float64List solve8(List<List<double>> aIn, List<double> bIn) {
  final n = bIn.length;
  final a = List.generate(n, (i) => List<double>.from(aIn[i]));
  final b = List<double>.from(bIn);
  for (var col = 0; col < n; col++) {
    var piv = col;
    for (var r = col + 1; r < n; r++) {
      if (a[r][col].abs() > a[piv][col].abs()) piv = r;
    }
    final t = a[col];
    a[col] = a[piv];
    a[piv] = t;
    final tb = b[col];
    b[col] = b[piv];
    b[piv] = tb;
    final d = a[col][col];
    for (var r = col + 1; r < n; r++) {
      final f = a[r][col] / d;
      for (var c2 = col; c2 < n; c2++) {
        a[r][c2] -= f * a[col][c2];
      }
      b[r] -= f * b[col];
    }
  }
  final x = Float64List(n);
  for (var r = n - 1; r >= 0; r--) {
    var s = b[r];
    for (var c2 = r + 1; c2 < n; c2++) {
      s -= a[r][c2] * x[c2];
    }
    x[r] = s / a[r][r];
  }
  return x;
}

/// PIL PERSPECTIVE 변환: 출력 (tw, th), 계수 8개 (출력→입력).
GrayF32 perspective(GrayF32 src, int tw, int th, Float64List co,
    {double fill = 1.0}) {
  final out = GrayF32(tw, th);
  for (var y = 0; y < th; y++) {
    final yy = y + 0.5;
    for (var x = 0; x < tw; x++) {
      final xx = x + 0.5;
      final d = co[6] * xx + co[7] * yy + 1.0;
      final xin = (co[0] * xx + co[1] * yy + co[2]) / d;
      final yin = (co[3] * xx + co[4] * yy + co[5]) / d;
      out.data[y * tw + x] = _sampleBilinear(src, xin, yin, fill);
    }
  }
  return out;
}

// ───────────────────── 필터 ─────────────────────

/// (2r+1) 정수 상자 흐림 — 가장자리는 창을 잘라 평균(정규화).
GrayF32 boxBlur(GrayF32 src, int r) {
  final w = src.w, h = src.h;
  final tmp = GrayF32(w, h);
  final pre = Float64List(w + 1);
  for (var y = 0; y < h; y++) {
    pre[0] = 0;
    for (var x = 0; x < w; x++) {
      pre[x + 1] = pre[x] + src.data[y * w + x];
    }
    for (var x = 0; x < w; x++) {
      final a = math.max(0, x - r), b = math.min(w - 1, x + r);
      tmp.data[y * w + x] = (pre[b + 1] - pre[a]) / (b - a + 1);
    }
  }
  final out = GrayF32(w, h);
  final col = Float64List(h + 1);
  for (var x = 0; x < w; x++) {
    col[0] = 0;
    for (var y = 0; y < h; y++) {
      col[y + 1] = col[y] + tmp.data[y * w + x];
    }
    for (var y = 0; y < h; y++) {
      final a = math.max(0, y - r), b = math.min(h - 1, y + r);
      out.data[y * w + x] = (col[b + 1] - col[a]) / (b - a + 1);
    }
  }
  return out;
}

/// 5×5 min/max 필터 (분리형) — PIL Min/MaxFilter(5) 대응(가장자리는 창 축소).
GrayF32 rankFilter5(GrayF32 src, {required bool isMax}) {
  final w = src.w, h = src.h;
  final tmp = GrayF32(w, h);
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      var v = src.data[y * w + x];
      for (var d = -2; d <= 2; d++) {
        final xx = x + d;
        if (xx < 0 || xx >= w) continue;
        final u = src.data[y * w + xx];
        if (isMax ? u > v : u < v) v = u;
      }
      tmp.data[y * w + x] = v;
    }
  }
  final out = GrayF32(w, h);
  for (var x = 0; x < w; x++) {
    for (var y = 0; y < h; y++) {
      var v = tmp.data[y * w + x];
      for (var d = -2; d <= 2; d++) {
        final yy = y + d;
        if (yy < 0 || yy >= h) continue;
        final u = tmp.data[yy * w + x];
        if (isMax ? u > v : u < v) v = u;
      }
      out.data[y * w + x] = v;
    }
  }
  return out;
}

// ───────────────────── 수치 유틸 ─────────────────────

double percentile(Float32List a, double p) {
  final s = Float32List.fromList(a)..sort();
  final idx = p / 100.0 * (s.length - 1);
  final lo = idx.floor(), hi = idx.ceil();
  if (lo == hi) return s[lo];
  return s[lo] + (s[hi] - s[lo]) * (idx - lo);
}

/// 이웃 3 이동평균 (np.convolve(ones(3)/3, 'same') 정합 — 가장자리 0 패딩).
Float64List conv3(Float64List p) {
  final n = p.length;
  final out = Float64List(n);
  for (var i = 0; i < n; i++) {
    var s = p[i];
    if (i > 0) s += p[i - 1];
    if (i + 1 < n) s += p[i + 1];
    out[i] = s / 3.0;
  }
  return out;
}

/// np.interp(x, arange(n), p, left=0, right=0) — 정수 격자 선형 보간.
double interpAt(Float64List p, double x) {
  if (x < 0 || x > p.length - 1) return 0.0;
  final i = x.floor();
  if (i >= p.length - 1) return p[p.length - 1];
  final t = x - i;
  return p[i] * (1 - t) + p[i + 1] * t;
}

/// 최소자승 다항 피팅 (차수 1·2, 선택 가중) — np.polyfit 대응.
/// 반환은 높은 차수부터 (np.polyval 규약).
Float64List polyfit(List<double> xs, List<double> ys, int deg,
    {List<double>? w}) {
  final m = deg + 1;
  final a = List.generate(m, (_) => List<double>.filled(m, 0.0));
  final b = List<double>.filled(m, 0.0);
  for (var k = 0; k < xs.length; k++) {
    final wk = w == null ? 1.0 : w[k] * w[k];
    final pw = List<double>.filled(2 * deg + 1, 0.0);
    var t = 1.0;
    for (var d = 0; d <= 2 * deg; d++) {
      pw[d] = t;
      t *= xs[k];
    }
    for (var i = 0; i < m; i++) {
      for (var j = 0; j < m; j++) {
        a[i][j] += wk * pw[i + j];
      }
      b[i] += wk * pw[i] * ys[k];
    }
  }
  // 저차→고차로 만든 정규방정식을 풀고 뒤집는다.
  final sol = solve8(a, b);
  return Float64List.fromList(sol.reversed.toList());
}

double polyval(Float64List co, double x) {
  var s = 0.0;
  for (final c in co) {
    s = s * x + c;
  }
  return s;
}
