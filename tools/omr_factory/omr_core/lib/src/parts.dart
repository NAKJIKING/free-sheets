// 다성부(2중주·3중주…) 파트 나누기 — 파이썬 기준: omr_core/tool/ref_parts.py.
//
// 곡별 상수 없이 **보표 간격**만 쓴다: 같은 단(시스템) 안 보표 간격은 작고
// 단 사이는 크다.
//  1) 이웃 줄 간격을 '그 자리 오선 간격' 단위로 잰다(원근 대응: 줄마다 이웃 3줄
//     오선 간격의 중앙값, 두 줄 평균으로 나눔).
//  2) 정렬한 간격에서 비가 가장 크게 뛰는 곳으로 작은·큰을 나눈다. 큰/작은 중앙값
//     비 < 1.2 이거나 분리도(최소 큰/최대 작은) < 1.3 이면 한 파트.
//  3) 큰 간격에서 끊어 단을 만들고, 2보표 이상 단 중 가장 흔한 크기 k 가 2번
//     이상이면 k 파트. 크기 k 인 단은 위에서부터 파트 0..k−1.
//  4) 모자란 단(보표 검출 누락)은 가장 가까운 온전한 단(앞쪽 우선)에서 단 간격
//     만큼 옮긴 자리로 파트를 추정. 넘치는 단은 위에서 k 개만.
//  5) 단에서 빠진 파트 자리는 그 단 길이만큼 쉼표 — 파트 간 박자 정렬 유지.
// 검증(진행일지 2026-10-07): 캐논 2중주 53장 전부 2파트, 파트별 NER 합 8.447%
// (정답 줄 오라클 배정 8.439%), 단선율 43장 전부 1파트, 3·4중주 렌더 정답 일치.
import 'select.dart';
import 'vocab.dart';

const partMinRatio = 1.2;
const partMinSep = 1.3;

class PartGrouping {
  PartGrouping(this.k, this.systems, this.ratio);

  /// 파트 수(1 = 단선율).
  final int k;

  /// 단마다 (파트, 줄 번호) 목록(줄 번호는 입력 줄 목록 기준).
  final List<List<(int, int)>> systems;

  /// 큰/작은 간격 중앙값 비(진단용).
  final double ratio;
}

double _um(List<double> xs) {
  final s = [...xs]..sort();
  return s[s.length ~/ 2];
}

/// 파이썬 round(): 반올림 시 정확히 .5 면 짝수 쪽.
int _pyRound(double x) {
  final f = x.floorToDouble();
  final diff = x - f;
  if (diff > 0.5) return f.toInt() + 1;
  if (diff < 0.5) return f.toInt();
  return f.toInt().isEven ? f.toInt() : f.toInt() + 1;
}

PartGrouping groupParts(List<ScanLine> lines) {
  final n = lines.length;
  PartGrouping one([double ratio = 0.0]) => PartGrouping(
      1,
      [
        for (var i = 0; i < n; i++) [(0, i)],
      ],
      ratio);
  if (n < 4) return one();
  final lg = [
    for (var i = 0; i < n; i++)
      _um([
        for (var j = (i - 1 < 0 ? 0 : i - 1); j < (i + 2 > n ? n : i + 2); j++)
          lines[j].gap,
      ]),
  ];
  final d = [
    for (var i = 0; i < n - 1; i++)
      (lines[i + 1].cy - lines[i].cy) / ((lg[i] + lg[i + 1]) / 2),
  ];
  final u = <double>[0.0];
  for (final x in d) {
    u.add(u.last + x);
  }
  final s = [...d]..sort();
  var cut = 0;
  var best = s[1] / s[0];
  for (var i = 1; i < s.length - 1; i++) {
    final r = s[i + 1] / s[i];
    if (r > best) {
      best = r;
      cut = i;
    }
  }
  final thr = s[cut];
  final big = [for (final x in d) x > thr];
  final nb = big.where((b) => b).length;
  if (nb == 0 || nb == big.length) return one();
  final bigs = [
    for (var i = 0; i < d.length; i++)
      if (big[i]) d[i],
  ];
  final smalls = [
    for (var i = 0; i < d.length; i++)
      if (!big[i]) d[i],
  ];
  final smallMed = _um(smalls);
  final ratio = _um(bigs) / smallMed;
  final sep = bigs.reduce((a, b) => a < b ? a : b) /
      smalls.reduce((a, b) => a > b ? a : b);
  if (ratio < partMinRatio || sep < partMinSep) return one(ratio);

  final systems = <List<int>>[];
  var cur = <int>[0];
  for (var i = 0; i < big.length; i++) {
    if (big[i]) {
      systems.add(cur);
      cur = [i + 1];
    } else {
      cur.add(i + 1);
    }
  }
  systems.add(cur);
  final multi = <int, int>{};
  for (final sy in systems) {
    if (sy.length >= 2) multi[sy.length] = (multi[sy.length] ?? 0) + 1;
  }
  if (multi.isEmpty) return one(ratio);
  var k = -1;
  for (final e in multi.entries) {
    if (k < 0 ||
        e.value > multi[k]! ||
        (e.value == multi[k]! && e.key > k)) {
      k = e.key;
    }
  }
  if (multi[k]! < 2) return one(ratio);

  final full = [
    for (var si = 0; si < systems.length; si++)
      if (systems[si].length == k) si,
  ];
  final step = smallMed;
  final pitches = <double>[
    for (var a = 0; a + 1 < full.length; a++)
      if (full[a + 1] == full[a] + 1)
        u[systems[full[a + 1]][0]] - u[systems[full[a]][0]],
  ];
  // 이웃한 온전한 단이 없으면 단 안 간격×(k−1) + 가장 작은 큰 간격(누락은 간격을
  // 키우기만 하므로 최소가 순수한 단 사이 간격).
  final pitch = pitches.isNotEmpty
      ? _um(pitches)
      : (k - 1) * step + bigs.reduce((a, b) => a < b ? a : b);
  final out = <List<(int, int)>>[];
  for (var si = 0; si < systems.length; si++) {
    final sy = systems[si];
    if (sy.length >= k) {
      out.add([for (var j = 0; j < k; j++) (j, sy[j])]);
      continue;
    }
    // 가장 가까운 온전한 단(같은 거리면 앞쪽)
    var ref = full.first;
    for (final f in full) {
      final df = (f - si).abs(), dr = (ref - si).abs();
      if (df < dr || (df == dr && f < si && ref > si)) ref = f;
    }
    final top = u[systems[ref][0]] + (si - ref) * pitch;
    final used = <int>{};
    final slot = <(int, int)>[];
    for (final i in sy) {
      var j = _pyRound((u[i] - top) / step);
      j = j < 0 ? 0 : (j > k - 1 ? k - 1 : j);
      while (used.contains(j) && j < k - 1) {
        j++;
      }
      used.add(j);
      slot.add((j, i));
    }
    out.add(slot);
  }
  return PartGrouping(k, out, ratio);
}

int staffTicks(List<Tok> toks) =>
    toks.fold(0, (s, t) => t.pitch >= 0 ? s + t.dur : s);

/// 파트별 토큰열 — 단에서 빠진 파트는 그 단 길이만큼 쉼표.
List<List<Tok>> partTokens(List<ScanLine> lines, PartGrouping g) {
  final parts = [for (var j = 0; j < g.k; j++) <Tok>[]];
  for (final sy in g.systems) {
    final have = <int, List<Tok>>{for (final (j, i) in sy) j: lines[i].toks};
    var len = 0;
    for (final t in have.values) {
      final v = staffTicks(t);
      if (v > len) len = v;
    }
    for (var j = 0; j < g.k; j++) {
      final t = have[j];
      if (t != null) {
        parts[j].addAll(t);
      } else if (len > 0) {
        parts[j].add(Tok(0, len, false));
      }
    }
  }
  return parts;
}
