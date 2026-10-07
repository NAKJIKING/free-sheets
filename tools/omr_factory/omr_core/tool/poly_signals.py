# -*- coding: utf-8 -*-
"""단선율 아님 징후 신호 — 파이썬 기준 구현(다트 omr_core/lib/src/monophony.dart 와 같은 식).

① 쌓인 음표머리(head_mask → head_blobs → stacked_frac) ② 보표 쌍(paired).
입력 줄은 가짜 줄 제거(v5) 뒤의 것. 보정 경과·문턱 근거는 진행일지 S1 절 —
열 높이 방식(겹빔 오탐)·닫기 5(빈 머리+오선 융합)·큰 구멍 채우기(덜 지워진
오선 틈 메움) 를 차례로 버리고 이 판에 이르렀다.
"""
import numpy as np

STAFF_ROWS = (56, 68, 80, 92, 104)     # 정규화 텐서의 오선 행(간격 12, 중앙 80)
HEAD_SKIP, HEAD_MIN_W, HEAD_MAX_W, HEAD_MIN_H = 160, 12, 22, 8
HOLE_MAX_PX, HOLE_MAX_H = 60, 8
STACKED_PX, STACKED_FRAC_WARN = 24, 0.08
PAIR_ALT_MIN, PAIR_RATIO_MIN, PAIR_MIN_LINES = 0.8, 1.2, 4


def _minmax(m, k, op):
    """분리형 k×k 최소/최대 필터(가장자리 = 창을 안쪽으로 줄임)."""
    r = k // 2
    out = m
    for ax in (0, 1):
        n = out.shape[ax]
        acc = out.copy()
        for d in range(1, r + 1):
            fwd = np.take(out, np.r_[d:n, [n - 1] * d], axis=ax)
            bwd = np.take(out, np.r_[[0] * d, 0:n - d], axis=ax)
            acc = op(acc, op(fwd, bwd))
        out = acc
    return out


def _components(m, pixels=False):
    """4-연결 성분 → [(y0, x0, y1, x1, 화소수[, 화소목록])]."""
    H, W = m.shape
    seen = np.zeros(m.shape, dtype=bool)
    out = []
    ys, xs = np.nonzero(m)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        stack = [(y0, x0)]
        pts = []
        ylo = yhi = y0
        xlo = xhi = x0
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            ylo, yhi = min(ylo, y), max(yhi, y)
            xlo, xhi = min(xlo, x), max(xhi, x)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((ylo, xlo, yhi, xhi, len(pts)) + ((pts,) if pixels else ()))
    return out


def head_mask(a):
    """음표머리만 남긴 이진 마스크.

    ① 배경(중앙값) 대비 0.3 넘게 어두우면 잉크 ② 오선 다섯 행(±1)에서 바로
    위·아래가 비어 있는 화소 제거 ③ 테두리에 닿지 않는 작은 배경 성분
    (높이 ≤8px·60px 미만 = 빈 머리 속)만 채우기 ④ 열기 7 — 기둥·빔·덧줄·
    임시표 획 제거."""
    a = np.asarray(a, dtype=np.float32)
    m = (a - np.median(a) > 0.3).astype(np.uint8)
    H, W = m.shape
    for r in STAFF_ROWS:
        top, bot = r - 1, r + 1
        if top - 1 < 0 or bot + 1 >= H:
            continue
        clear = (m[top - 1] == 0) & (m[bot + 1] == 0)
        m[top:bot + 1, clear] = 0
    # 테두리와 이어진 배경을 벡터 연산으로 퍼뜨린다(4-연결) — 남은 배경이
    # 곧 테두리에 닿지 않는 성분들(배경 전체 BFS 와 결과 같음, 속도만 다름).
    bg = m == 0
    reach = np.zeros_like(bg)
    reach[0, :], reach[-1, :], reach[:, 0], reach[:, -1] = \
        bg[0, :], bg[-1, :], bg[:, 0], bg[:, -1]
    while True:
        nxt = reach.copy()
        nxt[1:, :] |= reach[:-1, :]
        nxt[:-1, :] |= reach[1:, :]
        nxt[:, 1:] |= reach[:, :-1]
        nxt[:, :-1] |= reach[:, 1:]
        nxt &= bg
        if (nxt == reach).all():
            break
        reach = nxt
    holes = (bg & ~reach).astype(np.uint8)
    for y0, _x0, y1, _x1, cnt, pts in _components(holes, pixels=True):
        if cnt < HOLE_MAX_PX and y1 - y0 + 1 <= HOLE_MAX_H:
            for y, x in pts:
                m[y, x] = 1
    return _minmax(_minmax(m, 7, np.minimum), 7, np.maximum)


def head_blobs(a):
    """음표머리 폭(12~22px)·높이 ≥8 덩어리의 (폭, 높이). 줄 앞 160px
    (음자리표·조표 7개·박자표·빠르기표)에 걸친 것은 뺀다."""
    out = []
    for y0, x0, y1, x1, _c in _components(head_mask(a)):
        h, w = y1 - y0 + 1, x1 - x0 + 1
        if x0 < HEAD_SKIP or h < HEAD_MIN_H or not HEAD_MIN_W <= w <= HEAD_MAX_W:
            continue
        out.append((w, h))
    return out


def head_stats(a):
    """(머리 수, 그중 높이 ≥ STACKED_PX) — 다트 headStats 와 같은 값."""
    hs = [h for _w, h in head_blobs(a)]
    return len(hs), sum(1 for h in hs if h >= STACKED_PX)


def kept_lines(lines):
    sqs = sorted(l['sq'] for l in lines)
    med = sqs[len(sqs) // 2] if sqs else 1.0
    return [l for l in lines
            if l['toks'] and not (l['notes'] <= 2 and l['sq'] < 0.3 * med)]


def _upper_median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def paired(k, min_lines=PAIR_MIN_LINES):
    """보표 쌍(피아노 큰보표·2중주): 줄 중심 간격이 작은·큰 두 값으로 교대.
    간격을 (최소+최대)/2 로 둘로 나눠 교대율·간격비(위 중앙값 기준)."""
    if len(k) < min_lines:
        return 0.0, 0.0
    g = _upper_median([l['gap'] for l in k])
    d = [(b['cy'] - a['cy']) / g for a, b in zip(k, k[1:])]
    mid = (min(d) + max(d)) / 2
    big = [x > mid for x in d]
    if not 0 < sum(big) < len(big):
        return 0.0, 0.0
    alt = sum(1 for a, b in zip(big, big[1:]) if a != b) / (len(big) - 1)
    ratio = _upper_median([x for x, b in zip(d, big) if b]) / \
        _upper_median([x for x, b in zip(d, big) if not b])
    return alt, ratio
