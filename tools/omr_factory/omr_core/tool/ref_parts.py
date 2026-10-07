# -*- coding: utf-8 -*-
"""다성부(2중주·3중주) 파트 나누기 — 파이썬 기준(다트 omr_core/lib/src/parts.dart 와 같은 식).

입력: 가짜 줄을 뺀 줄(위→아래, dict: cy·gap·toks). 곡별 상수 없이 **보표 간격**만
쓴다: 같은 단(시스템) 안 보표 간격은 작고, 단과 단 사이는 크다.
  1) 이웃 줄 간격(오선 간격 단위)을 정렬해 비가 가장 크게 뛰는 곳에서 작은·큰
     둘로 나눈다. 큰/작은 중앙값 비 < 1.2 이거나 분리도(최소 큰 간격/최대 작은
     간격) < 1.3 이면 한 파트(단선율).
  2) 큰 간격에서 끊어 단을 만들고, 2보표 이상 단 중 가장 흔한 크기 k 가 2번
     이상 나오면 k 파트. 아니면 한 파트.
  3) 크기 k 인 단은 위에서부터 파트 0..k−1. 모자란 단(검출 누락)은 가까운 온전한
     단의 배치(단 첫 보표 기준 오프셋)로 각 보표의 파트를 추정한다. 넘치는 단은
     위에서부터 순서대로(초과분은 마지막 파트에 붙지 않고 버림 표시).
  4) 단에서 빠진 파트 자리는 그 단의 길이(있는 보표들의 최대 길이)만큼 쉼표로
     채워 파트 간 박자가 어긋나지 않게 한다.
"""

MIN_RATIO = 1.2
MIN_SEP = 1.3


def _um(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def staff_ticks(toks):
    return sum(t[1] for t in toks if t[0] >= 0)


def group_parts(lines):
    """→ dict(k=파트 수, systems=[[(파트, 줄번호), ...], ...], ratio=간격비)."""
    n = len(lines)
    one = dict(k=1, systems=[[(0, i)] for i in range(n)], ratio=0.0)
    if n < 4:
        return one
    # 간격은 '그 자리 오선 간격' 단위로 — 원근이 센 사진은 위·아래 오선 간격이
    # 1.5배까지 달라(190113 실측: 9→14.5px) 한 값으로 나누면 단 구분이 무너진다.
    # 줄마다 이웃 3줄 오선 간격의 중앙값을 쓰고(튀는 값 완화), 두 줄 평균으로 나눈다.
    lg = [_um([l['gap'] for l in lines[max(0, i - 1):i + 2]]) for i in range(n)]
    d = [(lines[i + 1]['cy'] - lines[i]['cy']) / ((lg[i] + lg[i + 1]) / 2)
         for i in range(n - 1)]
    u = [0.0]                                  # 누적 위치(오선 간격 단위)
    for x in d:
        u.append(u[-1] + x)
    # 작은·큰 경계 = 정렬한 간격에서 비(뒤/앞)가 가장 크게 뛰는 곳 — 보표
    # 누락으로 생긴 아주 큰 간격 하나가 경계를 끌어올리지 않게(중간값 방식 실패:
    # 190127 실측). 비가 같으면 앞쪽.
    s = sorted(d)
    cut = max(range(len(s) - 1), key=lambda i: (s[i + 1] / s[i], -i))
    thr = s[cut]
    big = [x > thr for x in d]
    if not 0 < sum(big) < len(big):
        return one
    small_med = _um([x for x, b in zip(d, big) if not b])
    ratio = _um([x for x, b in zip(d, big) if b]) / small_med
    # 분리도: 가장 작은 '큰 간격'이 가장 큰 '작은 간격'보다 1.3배 이상 — 원근으로
    # 간격이 서서히 커지는 단선율 사진(비 최대 1.4, 실측)은 두 무리가 붙어 있어 탈락.
    sep = min(x for x, b in zip(d, big) if b) / max(x for x, b in zip(d, big) if not b)
    if ratio < MIN_RATIO or sep < MIN_SEP:
        return dict(one, ratio=ratio)
    systems, cur = [], [0]
    for i, b in enumerate(big):
        if b:
            systems.append(cur)
            cur = [i + 1]
        else:
            cur.append(i + 1)
    systems.append(cur)
    counts = {}
    for sy in systems:
        counts[len(sy)] = counts.get(len(sy), 0) + 1
    multi = {sz: c for sz, c in counts.items() if sz >= 2}
    if not multi:
        return dict(one, ratio=ratio)
    # 2보표 이상 단 중 가장 흔한 크기(동률이면 큰 쪽), 2번 이상. 외톨이 보표
    # (크기 1 — 대개 짝 보표 검출 누락)는 아래에서 자리를 추정해 넣는다.
    k = max(multi, key=lambda sz: (multi[sz], sz))
    if multi[k] < 2:
        return dict(one, ratio=ratio)
    full = [si for si, s in enumerate(systems) if len(s) == k]
    step = small_med                           # 단 안 보표 간격(오선 간격 단위)
    out = []
    for si, s in enumerate(systems):
        if len(s) == k:
            out.append([(j, i) for j, i in enumerate(s)])
            continue
        if len(s) > k:                         # 넘침 — 위에서부터 k 개만
            out.append([(j, i) for j, i in enumerate(s[:k])])
            continue
        # 모자람 — 가장 가까운 온전한 단(앞쪽 우선)의 첫 보표에서 '단 간격'
        # (이웃한 온전한 단 첫 보표끼리 거리의 중앙값) 만큼 옮겨 이 단 첫 파트
        # 자리를 예측하고, 각 보표를 가까운 파트 자리에 둔다.
        ref = min(full, key=lambda f: (abs(f - si), f > si))
        pitches = [u[systems[b][0]] - u[systems[a][0]]
                   for a, b in zip(full, full[1:]) if b == a + 1]
        # 이웃한 온전한 단이 없으면 단 안 간격×(k−1) + 가장 작은 큰 간격(누락은
        # 간격을 키우기만 하므로 최소가 순수한 단 사이 간격)
        pitch = _um(pitches) if pitches else \
            (k - 1) * step + min(x for x, b in zip(d, big) if b)
        top = u[systems[ref][0]] + (si - ref) * pitch
        used, slot = set(), []
        for i in s:
            j = int(round((u[i] - top) / step))
            j = max(0, min(k - 1, j))
            while j in used and j < k - 1:
                j += 1
            used.add(j)
            slot.append((j, i))
        out.append(slot)
    return dict(k=k, systems=out, ratio=ratio)


def part_tokens(lines, grouping):
    """파트별 토큰열(단마다 빠진 파트는 그 단 길이만큼 쉼표)."""
    k = grouping['k']
    parts = [[] for _ in range(k)]
    for sysl in grouping['systems']:
        have = {j: lines[i]['toks'] for j, i in sysl}
        length = max((staff_ticks(t) for t in have.values()), default=0)
        for j in range(k):
            if j in have:
                parts[j] += [tuple(t) for t in have[j]]
            elif length:
                parts[j].append((0, length, 0))
    return parts
