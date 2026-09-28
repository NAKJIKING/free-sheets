// photo_prep.py 대응 — 사진 → 줄 크롭 (순수 다트).
// 파이썬은 단계마다 PIL uint8 로 재양자화된다 — 정합을 위해 같은 자리에서
// 양자화를 미러링한다(astype=내림, PIL 보간 내부=반올림).
import 'dart:math' as math;
import 'dart:typed_data';

import 'gray.dart';
import 'kernels.dart';
import 'prep.dart' as prep;

const workW = 1400;

GrayF32 _quantFloor(GrayF32 g) {
  final o = GrayF32(g.w, g.h);
  for (var i = 0; i < g.data.length; i++) {
    var v = g.data[i];
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    o.data[i] = (v * 255).floor() / 255.0;
  }
  return o;
}

GrayF32 _quantRound(GrayF32 g) {
  final o = GrayF32(g.w, g.h);
  for (var i = 0; i < g.data.length; i++) {
    var v = g.data[i];
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    o.data[i] = (v * 255).round() / 255.0;
  }
  return o;
}

// ───────────────────── ① 종이 검출·원근 보정 ─────────────────────

List<List<double>>? findPaper(GrayF32 img, {int workWp = 800}) {
  final w = img.w, h = img.h;
  final f = math.max(1.0, w / workWp);
  final g = resizeBilinear(img, w ~/ f, h ~/ f);
  final lo = percentile(g.data, 8), hi = percentile(g.data, 92);
  if (hi - lo < 0.25) return null;
  final gw = g.w, gh = g.h;
  var mask = Uint8List(gw * gh);
  final thr = (lo + hi) / 2.0;
  for (var i = 0; i < mask.length; i++) {
    mask[i] = g.data[i] >= thr ? 1 : 0;
  }
  // 닫힘 흉내: Min(5) 뒤 Max(5)
  GrayF32 mF() {
    final m = GrayF32(gw, gh);
    for (var i = 0; i < mask.length; i++) {
      m.data[i] = mask[i].toDouble();
    }
    return m;
  }

  var mm = rankFilter5(mF(), isMax: false);
  mm = rankFilter5(mm, isMax: true);
  for (var i = 0; i < mask.length; i++) {
    mask[i] = mm.data[i] > 0.5 ? 1 : 0;
  }
  // 무게중심 연결성분만 (저해상 400px BFS)
  var any = false;
  var sy = 0.0, sx = 0.0, cnt = 0;
  for (var y = 0; y < gh; y++) {
    for (var x = 0; x < gw; x++) {
      if (mask[y * gw + x] != 0) {
        any = true;
        sy += y;
        sx += x;
        cnt++;
      }
    }
  }
  if (any) {
    final f2 = math.max(1, gw ~/ 400);
    final sw = gw ~/ f2, sh = gh ~/ f2;
    final small = Uint8List(sw * sh);
    {
      final mimg = mF();
      final sm = resizeNearest(mimg, sw, sh);
      for (var i = 0; i < small.length; i++) {
        small[i] = sm.data[i] > 0.5 ? 1 : 0;
      }
    }
    var cy = (sy / cnt).toInt() ~/ f2;
    var cx = (sx / cnt).toInt() ~/ f2;
    cy = cy.clamp(0, sh - 1);
    cx = cx.clamp(0, sw - 1);
    if (small[cy * sw + cx] == 0) {
      var bd = 1 << 30;
      var by = -1, bx = -1;
      for (var y = 0; y < sh; y++) {
        for (var x = 0; x < sw; x++) {
          if (small[y * sw + x] != 0) {
            final d = (y - cy) * (y - cy) + (x - cx) * (x - cx);
            if (d < bd) {
              bd = d;
              by = y;
              bx = x;
            }
          }
        }
      }
      if (by < 0) return null;
      cy = by;
      cx = bx;
    }
    final comp = Uint8List(sw * sh);
    final qy = Int32List(sw * sh);
    final qx = Int32List(sw * sh);
    var qh = 0, qt = 0;
    comp[cy * sw + cx] = 1;
    qy[qt] = cy;
    qx[qt] = cx;
    qt++;
    // BFS — 파이썬은 MaxFilter(5) 반복이라 대각 2칸까지 이웃으로 본다.
    while (qh < qt) {
      final y0 = qy[qh], x0 = qx[qh];
      qh++;
      for (var dy = -2; dy <= 2; dy++) {
        for (var dx = -2; dx <= 2; dx++) {
          final ny = y0 + dy, nx = x0 + dx;
          if (ny < 0 || nx < 0 || ny >= sh || nx >= sw) continue;
          final idx = ny * sw + nx;
          if (small[idx] != 0 && comp[idx] == 0) {
            comp[idx] = 1;
            qy[qt] = ny;
            qx[qt] = nx;
            qt++;
          }
        }
      }
    }
    final compBig = GrayF32(sw, sh);
    for (var i = 0; i < comp.length; i++) {
      compBig.data[i] = comp[i].toDouble();
    }
    final cb = resizeNearest(compBig, gw, gh);
    for (var i = 0; i < mask.length; i++) {
      if (cb.data[i] < 0.5) mask[i] = 0;
    }
  }
  var msum = 0;
  for (final v in mask) {
    msum += v;
  }
  final frac = msum / mask.length;
  if (frac < 0.18 || frac > 0.93) return null;
  // 극점 4귀퉁이
  var minS = 1 << 30, maxS = -(1 << 30), minD = 1 << 30, maxD = -(1 << 30);
  final corners = List.generate(4, (_) => [0.0, 0.0]);
  for (var y = 0; y < gh; y++) {
    for (var x = 0; x < gw; x++) {
      if (mask[y * gw + x] == 0) continue;
      final s = x + y, d = x - y;
      if (s < minS) {
        minS = s;
        corners[0] = [x.toDouble(), y.toDouble()];
      }
      if (d > maxD) {
        maxD = d;
        corners[1] = [x.toDouble(), y.toDouble()];
      }
      if (s > maxS) {
        maxS = s;
        corners[2] = [x.toDouble(), y.toDouble()];
      }
      if (d < minD) {
        minD = d;
        corners[3] = [x.toDouble(), y.toDouble()];
      }
    }
  }
  // 검증들 (photo_prep.find_paper 그대로)
  final q = corners;
  final el = List.generate(4, (i) {
    final a = q[i], b = q[(i + 1) % 4];
    return math.sqrt((b[0] - a[0]) * (b[0] - a[0]) +
        (b[1] - a[1]) * (b[1] - a[1]));
  });
  if (math.max(el[0], el[2]) > 1.5 * math.min(el[0], el[2]) ||
      math.max(el[1], el[3]) > 1.5 * math.min(el[1], el[3])) {
    return null;
  }
  var area = 0.0;
  for (var i = 0; i < 4; i++) {
    area += q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1];
  }
  area = area.abs() * 0.5;
  if (!(0.18 * gh * gw <= area && area <= 0.97 * gh * gw)) return null;
  if (!(msum / math.max(1.0, area) >= 0.75 &&
      msum / math.max(1.0, area) <= 1.25)) {
    return null;
  }
  // inside 밀도 검증
  var insideCnt = 0, insideMask = 0, outMaskCnt = 0, outCnt = 0;
  final tol = -2.0 * (gw + gh);
  for (var y = 0; y < gh; y++) {
    for (var x = 0; x < gw; x++) {
      var ins = true;
      for (var i = 0; i < 4; i++) {
        final ax = q[i][0], ay = q[i][1];
        final bx = q[(i + 1) % 4][0], by = q[(i + 1) % 4][1];
        if ((bx - ax) * (y - ay) - (by - ay) * (x - ax) < tol) {
          ins = false;
          break;
        }
      }
      final mv = mask[y * gw + x];
      if (ins) {
        insideCnt++;
        insideMask += mv;
      } else {
        outCnt++;
        outMaskCnt += mv;
      }
    }
  }
  final insideFrac = insideCnt / (gw * gh);
  if (insideFrac < 0.999 && outCnt > 0 && outMaskCnt / outCnt > 0.35) {
    return null;
  }
  if (insideCnt > 0 && insideMask / insideCnt < 0.80) return null;
  return q.map((c) => [c[0] * f, c[1] * f]).toList();
}

GrayF32 cropPaper(GrayF32 img) {
  final q = findPaper(img);
  if (q == null) return img;
  double hyp(List<double> a, List<double> b) =>
      math.sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]));
  final tw = ((hyp(q[1], q[0]) + hyp(q[2], q[3])) / 2).round();
  final th = ((hyp(q[3], q[0]) + hyp(q[2], q[1])) / 2).round();
  if (tw < 200 || th < 200) return img;
  final dst = [
    [0.0, 0.0],
    [tw.toDouble(), 0.0],
    [tw.toDouble(), th.toDouble()],
    [0.0, th.toDouble()],
  ];
  final a = <List<double>>[];
  final b = <double>[];
  for (var i = 0; i < 4; i++) {
    final xX = dst[i][0], yY = dst[i][1];
    final x = q[i][0], y = q[i][1];
    a.add([xX, yY, 1, 0, 0, 0, -x * xX, -x * yY]);
    a.add([0, 0, 0, xX, yY, 1, -y * xX, -y * yY]);
    b.add(x);
    b.add(y);
  }
  final co = solve8(a, b);
  return _quantRound(perspective(img, tw, th, co, fill: 1.0));
}

// ───────────────────── ② 조명 평탄화 ─────────────────────

GrayF32 flattenIllum(GrayF32 img, {int cell = 24}) {
  final w = img.w, h = img.h;
  final sw = math.max(2, w ~/ cell), sh = math.max(2, h ~/ cell);
  var small = resizeBilinear(_quantFloor(img), sw, sh);
  small = rankFilter5(small, isMax: true);
  small = boxBlur(small, 2);
  // 파이썬은 BICUBIC 확대 — bilinear 로 대체(배경은 저주파라 차이 미미,
  // 게이트로 흡수. 진행일지 기록).
  final bg = resizeBilinear(small, w, h);
  final out = GrayF32(w, h);
  for (var i = 0; i < out.data.length; i++) {
    var v = img.data[i] / math.max(bg.data[i], 0.18);
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    out.data[i] = v;
  }
  return _quantFloor(out);
}

// ───────────────────── 기울기·오선계 ─────────────────────

class InkSmall {
  InkSmall(this.ink, this.f);
  final GrayF32 ink;
  final double f;
}

InkSmall inkSmall(GrayF32 img, {int ww = workW}) {
  final f = math.max(1.0, img.w / ww);
  final small = resizeBilinear(img, img.w ~/ f, img.h ~/ f);
  return InkSmall(prep.localBinarize(small, win: 25, k: 0.10), f);
}

double deskewAngle(GrayF32 ink, {double lo = -20, double hi = 20}) {
  double sharp(double deg) {
    final r = rotate(ink, deg, fill: 0.0);
    var best = 0.0;
    final prof = Float64List(r.h);
    var mean = 0.0;
    for (var y = 0; y < r.h; y++) {
      var s = 0.0;
      for (var x = 0; x < r.w; x++) {
        s += r.data[y * r.w + x];
      }
      // PIL 은 uint8 이미지 회전 — 255 배 스케일 정합은 분산 비교라 무관.
      prof[y] = s;
      mean += s;
    }
    mean /= r.h;
    for (var y = 0; y < r.h; y++) {
      best += (prof[y] - mean) * (prof[y] - mean);
    }
    return best / r.h;
  }

  double bestOf(double a, double b, double step) {
    var bd = a;
    var bs = sharp(a);
    for (var d = a + step; d <= b + 1e-9; d += step) {
      final s = sharp(d);
      if (s > bs) {
        bs = s;
        bd = d;
      }
    }
    return bd;
  }

  final coarse = bestOf(lo, hi, 1.5);
  final mid = bestOf(coarse - 1.5, coarse + 1.5, 0.5);
  return bestOf(mid - 0.5, mid + 0.5, 0.1);
}

class SystemLine {
  SystemLine(this.y, this.gap, [this.score = 0]);
  final double y;
  final double gap;
  final double score;
}

Float64List _rowProf(GrayF32 ink) {
  final prof = Float64List(ink.h);
  for (var y = 0; y < ink.h; y++) {
    var s = 0.0;
    for (var x = 0; x < ink.w; x++) {
      s += ink.data[y * ink.w + x];
    }
    prof[y] = s;
  }
  return prof;
}

List<SystemLine> findSystems(GrayF32 ink,
    {double minGap = 6,
    double maxGap = 40,
    int maxSystems = 16,
    double tapFrac = 0.12,
    double floorFrac = 0.16}) {
  final h = ink.h, w = ink.w;
  var prof = _rowProf(ink);
  var pmax = 0.0;
  for (final v in prof) {
    if (v > pmax) pmax = v;
  }
  if (pmax <= 0) return [];
  prof = conv3(prof);
  final gaps = <double>[];
  for (var g = minGap; g <= maxGap + 1e-9; g += 0.5) {
    gaps.add(g);
  }
  final resp = List.generate(gaps.length, (_) => Float64List(h));
  for (var gi = 0; gi < gaps.length; gi++) {
    final g = gaps[gi];
    for (var y = 0; y < h; y++) {
      var mn = double.infinity;
      var sum = 0.0;
      for (var m = -2; m <= 2; m++) {
        final t = interpAt(prof, y + m * g);
        sum += t;
        if (t < mn) mn = t;
      }
      resp[gi][y] = mn >= w * tapFrac ? sum : 0.0;
    }
  }
  final floor = 5.0 * w * floorFrac;
  final out = <SystemLine>[];
  final r = List.generate(gaps.length, (i) => Float64List.fromList(resp[i]));
  while (out.length < maxSystems) {
    var bg = 0, by = 0;
    var bv = -1.0;
    for (var gi = 0; gi < gaps.length; gi++) {
      for (var y = 0; y < h; y++) {
        if (r[gi][y] > bv) {
          bv = r[gi][y];
          bg = gi;
          by = y;
        }
      }
    }
    if (bv < floor) break;
    final g = gaps[bg];
    out.add(SystemLine(by.toDouble(), g, bv));
    final y0 = math.max(0, (by - 3.5 * g).toInt());
    final y1 = math.min(h, (by + 3.5 * g).toInt() + 1);
    for (var gi = 0; gi < gaps.length; gi++) {
      for (var y = y0; y < y1; y++) {
        r[gi][y] = 0.0;
      }
    }
  }
  if (out.length >= 2) {
    var refG = out[0].gap;
    var refS = out[0].score;
    for (final s in out) {
      if (s.score > refS) {
        refS = s.score;
        refG = s.gap;
      }
    }
    out.removeWhere((s) => !(0.72 * refG <= s.gap && s.gap <= 1.38 * refG));
  }
  out.sort((a, b) => a.y.compareTo(b.y));
  return out;
}

double combResp(GrayF32 ink, double y, double gap) {
  final prof = conv3(_rowProf(ink));
  var acc = 0.0;
  for (var m = -2; m <= 2; m++) {
    acc += interpAt(prof, y + m * gap);
  }
  return acc;
}

GrayF32 _cols(GrayF32 g, int x0, int x1) => g.crop(x0, 0, x1, g.h);

List<SystemLine> findSystemsMulti(GrayF32 ink) {
  final w = ink.w;
  final out = List<SystemLine>.from(findSystems(ink));
  for (final half in [_cols(ink, 0, w ~/ 2), _cols(ink, w ~/ 2, w)]) {
    for (final s in findSystems(half)) {
      if (out.every(
          (o) => (s.y - o.y).abs() > 5.5 * math.max(s.gap, o.gap))) {
        out.add(s);
      }
    }
  }
  out.sort((a, b) => a.y.compareTo(b.y));
  return out;
}

double _median(List<double> xs) {
  final s = List<double>.from(xs)..sort();
  return s[s.length ~/ 2];
}

List<SystemLine> fillMissing(GrayF32 ink, List<SystemLine> systems) {
  if (systems.length < 2) return systems;
  final h = ink.h;
  final ref = _median(systems.map((s) => s.gap).toList());
  final ys = systems.map((s) => s.y).toList();
  final diffs = <double>[];
  for (var i = 0; i + 1 < ys.length; i++) {
    diffs.add(ys[i + 1] - ys[i]);
  }
  diffs.sort();
  final step = diffs[diffs.length ~/ 2];
  final holes = <List<double>>[];
  for (var i = 0; i + 1 < ys.length; i++) {
    if (ys[i + 1] - ys[i] > 1.7 * step) {
      holes.add([ys[i] + 2.5 * ref, ys[i + 1] - 2.5 * ref]);
    }
  }
  if (ys.first - 2.5 * ref > 0.9 * step) holes.add([0, ys.first - 2.5 * ref]);
  if (h - ys.last - 2.5 * ref > 0.9 * step) {
    holes.add([ys.last + 2.5 * ref, h.toDouble()]);
  }
  final out = List<SystemLine>.from(systems);
  for (final hole in holes) {
    final y0 = math.max(0, hole[0].toInt());
    final y1 = math.min(h, hole[1].toInt());
    if (y1 - y0 < 5 * ref) continue;
    final band = ink.crop(0, y0, ink.w, y1);
    for (final s in findSystems(band, tapFrac: 0.07, floorFrac: 0.10)) {
      if (!(0.72 * ref <= s.gap && s.gap <= 1.38 * ref)) continue;
      final ay = s.y + y0;
      if (out.every(
          (o) => (ay - o.y).abs() > 5.5 * math.max(s.gap, o.gap))) {
        out.add(SystemLine(ay, s.gap));
      }
    }
  }
  out.sort((a, b) => a.y.compareTo(b.y));
  return out;
}

List<SystemLine> slotFill(GrayF32 ink, List<SystemLine> systems) {
  if (systems.length < 4) return systems;
  final h = ink.h;
  final ref = _median(systems.map((s) => s.gap).toList());
  final ys = systems.map((s) => s.y).toList();
  final diffs = <double>[];
  for (var i = 0; i + 1 < ys.length; i++) {
    diffs.add(ys[i + 1] - ys[i]);
  }
  final dmin = diffs.reduce(math.min);
  final small = diffs.where((d) => d <= 1.45 * dmin).toList();
  final big = diffs.where((d) => d > 1.45 * dmin).toList();
  if (small.isEmpty || big.isEmpty) return systems;
  final s1 = _median(small), s2 = _median(big);
  double std(List<double> xs) {
    final m = xs.reduce((a, b) => a + b) / xs.length;
    return math.sqrt(
        xs.map((x) => (x - m) * (x - m)).reduce((a, b) => a + b) / xs.length);
  }

  if ((small.length >= 2 && std(small) > 0.15 * s1) ||
      (big.length >= 2 && std(big) > 0.15 * s2)) {
    return systems;
  }
  final base =
      _median(ys.map((y) => combResp(ink, y, ref)).toList());
  var k = -1;
  for (var i = 0; i < diffs.length; i++) {
    if (diffs[i] <= 1.45 * dmin) {
      k = i;
      break;
    }
  }
  if (k < 0) return systems;
  final slots = <double>[ys[k], ys[k + 1]];
  var yy = ys[k + 1];
  var stepNext = s2;
  while (true) {
    yy += stepNext;
    if (yy > h - 1.5 * ref) break;
    slots.add(yy);
    stepNext = stepNext == s2 ? s1 : s2;
  }
  yy = ys[k];
  var stepPrev = s2;
  while (true) {
    yy -= stepPrev;
    if (yy < 1.5 * ref) break;
    slots.insert(0, yy);
    stepPrev = stepPrev == s2 ? s1 : s2;
  }
  final out = List<SystemLine>.from(systems);
  for (final sl in slots) {
    if (out.any((o) => (sl - o.y).abs() <= 2.5 * ref)) continue;
    final lo = math.max(0, (sl - 2.0 * ref).toInt());
    final hi = math.min(h, (sl + 2.0 * ref).toInt() + 1);
    var cand = lo;
    var cr = -1.0;
    // combResp 를 행마다 재계산하면 프로파일이 매번 나온다 — 한 번만.
    final prof = conv3(_rowProf(ink));
    double resp(double y) {
      var a = 0.0;
      for (var m = -2; m <= 2; m++) {
        a += interpAt(prof, y + m * ref);
      }
      return a;
    }

    for (var y = lo; y < hi; y++) {
      final rr = resp(y.toDouble());
      if (rr > cr) {
        cr = rr;
        cand = y;
      }
    }
    if (cr >= 0.45 * base &&
        out.every((o) =>
            (cand - o.y).abs() > 5.5 * math.max(ref, o.gap))) {
      out.add(SystemLine(cand.toDouble(), ref));
    }
  }
  out.sort((a, b) => a.y.compareTo(b.y));
  return out;
}

// ───────────────────── 되펴기·전단 상쇄 ─────────────────────

GrayF32 dewarpLine(GrayF32 crop, double gap) {
  final g = crop;
  final h = g.h, w = g.w;
  final ink = prep.localBinarize(g);
  final strip = math.max(24, (gap * 2).toInt());
  final xs = <double>[], cs = <double>[], ws = <double>[];
  for (var x0 = 0; x0 < w - strip ~/ 2; x0 += strip) {
    final x1 = math.min(w, x0 + strip);
    final seg = ink.crop(x0, 0, x1, h);
    final prof = conv3(_rowProf(seg));
    var c = 0;
    var cv = -1.0;
    for (var y = 0; y < h; y++) {
      var a = 0.0;
      for (var m = -2; m <= 2; m++) {
        a += interpAt(prof, y + m * gap);
      }
      if (a > cv) {
        cv = a;
        c = y;
      }
    }
    if (cv < 5.0 * seg.w * 0.12) continue;
    xs.add(x0 + strip / 2.0);
    cs.add(c.toDouble());
    ws.add(cv);
  }
  if (xs.length < 3) return crop;
  final co = polyfit(xs, cs, 2, w: ws.map(math.sqrt).toList());
  final fit = Float64List(w);
  for (var x = 0; x < w; x++) {
    fit[x] = polyval(co, x.toDouble());
  }
  final med = _median(fit.toList());
  final shift = Float64List(w);
  var mx = 0.0;
  for (var x = 0; x < w; x++) {
    shift[x] = fit[x] - med;
    if (shift[x].abs() > mx) mx = shift[x].abs();
  }
  if (mx < 1.0) return crop;
  final out = GrayF32(w, h);
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      final src = y + shift[x];
      var r0 = src.floor();
      if (r0 < 0) r0 = 0;
      if (r0 > h - 1) r0 = h - 1;
      var r1 = r0 + 1;
      if (r1 > h - 1) r1 = h - 1;
      var t = src - r0;
      if (t < 0) t = 0;
      if (t > 1) t = 1;
      out.data[y * w + x] =
          g.data[r0 * w + x] * (1 - t) + g.data[r1 * w + x] * t;
    }
  }
  return _quantFloor(out);
}

GrayF32 rectifyByStaves(GrayF32 img, {int ww = workW}) {
  final isres = inkSmall(img, ww: ww);
  final ink = isres.ink;
  final h2 = ink.h, w2 = ink.w;
  final left = findSystems(_cols(ink, 0, w2 ~/ 2));
  final right = findSystems(_cols(ink, w2 ~/ 2, w2));
  final pys = <double>[], pdy = <double>[];
  for (final l in left) {
    SystemLine? best;
    for (final r in right) {
      if ((r.y - l.y).abs() < 4 * math.max(l.gap, r.gap)) {
        if (best == null || (r.y - l.y).abs() < (best.y - l.y).abs()) {
          best = r;
        }
      }
    }
    if (best != null) {
      pys.add(l.y);
      pdy.add(best.y - l.y);
    }
  }
  if (pys.length < 3) return img;
  double a, b;
  if (pys.length >= 5) {
    final co = polyfit(pys, pdy, 1); // [b, a]
    b = co[0];
    a = co[1];
    final resid = _median(
        List.generate(pys.length, (i) => (a + b * pys[i] - pdy[i]).abs()));
    if (resid > 1.5) return img;
  } else {
    a = _median(pdy);
    b = 0.0;
  }
  if (a.abs() < 0.8 && b.abs() * h2 < 0.8) return img;
  if (a.abs() + b.abs() * h2 > 12.0) return img;
  final gw = img.w, gh = img.h;
  final sf = gh / h2;
  final out = GrayF32(gw, gh);
  for (var y = 0; y < gh; y++) {
    final tilt = (a + b * (y / sf)) * sf;
    for (var x = 0; x < gw; x++) {
      final shift = ((x - gw / 2.0) / (gw / 2.0)) * (tilt / 2.0);
      final src = y + shift;
      var r0 = src.floor();
      if (r0 < 0) r0 = 0;
      if (r0 > gh - 1) r0 = gh - 1;
      var r1 = r0 + 1;
      if (r1 > gh - 1) r1 = gh - 1;
      var t = src - r0;
      if (t < 0) t = 0;
      if (t > 1) t = 1;
      out.data[y * gw + x] =
          img.data[r0 * gw + x] * (1 - t) + img.data[r1 * gw + x] * t;
    }
  }
  return _quantRound(out);
}

// ───────────────────── extract_lines ─────────────────────

class LineCrop {
  LineCrop(this.gray, this.cy, this.gap, this.box);
  final GrayF32 gray;
  final double cy; // 원본 좌표
  final double gap;
  final List<int> box; // [x0, top, x1, bot]
}

List<LineCrop> extractLines(GrayF32 photo,
    {double padRatio = 5.5, int ww = workW, bool correct = true}) {
  var img = photo;
  if (correct) {
    img = cropPaper(img);
    img = flattenIllum(img);
  }
  var isres = inkSmall(img, ww: ww);
  final ang = deskewAngle(isres.ink);
  if (ang.abs() > 0.05) {
    img = _quantRound(
        rotate(img, ang, fill: 1.0, expand: ang.abs() > 3.0));
  }
  if (correct) {
    img = rectifyByStaves(img, ww: ww);
  }
  isres = inkSmall(img, ww: ww);
  var ink = isres.ink;
  var f = isres.f;
  var systems = findSystemsMulti(ink);
  if (systems.isNotEmpty) {
    final med = _median(systems.map((s) => s.gap).toList());
    if (med < 12.0) {
      final ww2 = math.min(math.min((ww * 14.0 / med).toInt(), 3200), img.w);
      if (ww2 > ww * 1.15) {
        final is2 = inkSmall(img, ww: ww2);
        final sys2 = findSystemsMulti(is2.ink);
        if (sys2.length >= systems.length) {
          ink = is2.ink;
          f = is2.f;
          systems = sys2;
        }
      }
    }
  }
  systems = fillMissing(ink, systems);
  systems = slotFill(ink, systems);
  final out = <LineCrop>[];
  final bw = img.w, bh = img.h;
  for (final s in systems) {
    final cy0 = s.y * f, g0 = s.gap * f;
    final top = math.max(0, (cy0 - padRatio * g0).toInt());
    final bot = math.min(bh, (cy0 + padRatio * g0).toInt());
    final by0 = math.max(0, (s.y - padRatio * s.gap).toInt());
    final by1 = math.min(ink.h, (s.y + padRatio * s.gap).toInt());
    final band = ink.crop(0, by0, ink.w, by1);
    final colsOn = List<bool>.filled(band.w, false);
    for (var x = 0; x < band.w; x++) {
      var sSum = 0.0;
      for (var y = 0; y < band.h; y++) {
        sSum += band.data[y * band.w + x];
      }
      colsOn[x] = sSum > math.max(1.0, band.h * 0.02);
    }
    final runs = <List<int>>[];
    final gapTol = math.max(4, (3 * s.gap).toInt());
    int? i0;
    var lastOn = -1000000000;
    for (var x = 0; x < colsOn.length; x++) {
      if (colsOn[x]) {
        if (i0 == null || x - lastOn > gapTol) {
          if (i0 != null) runs.add([i0, lastOn]);
          i0 = x;
        }
        lastOn = x;
      }
    }
    if (i0 != null) runs.add([i0, lastOn]);
    int x0, x1;
    if (runs.isEmpty) {
      x0 = 0;
      x1 = bw;
    } else {
      var ri = 0;
      for (var i = 1; i < runs.length; i++) {
        if (runs[i][1] - runs[i][0] > runs[ri][1] - runs[ri][0]) ri = i;
      }
      var r0 = runs[ri][0], r1 = runs[ri][1];
      var k = ri;
      while (k - 1 >= 0 && runs[k][0] - runs[k - 1][1] <= 3 * gapTol) {
        k--;
        r0 = runs[k][0];
      }
      k = ri;
      while (k + 1 < runs.length && runs[k + 1][0] - runs[k][1] <= 3 * gapTol) {
        k++;
        r1 = runs[k][1];
      }
      x0 = math.max(0, (r0 * f - 2 * g0).toInt());
      x1 = math.min(bw, ((r1 + 1) * f + 2 * g0).toInt());
    }
    var c = img.crop(x0, top, x1, bot);
    if (correct) c = dewarpLine(c, g0);
    out.add(LineCrop(c, cy0, g0, [x0, top, x1, bot]));
  }
  return out;
}
