# -*- coding: utf-8 -*-
"""실사 폰사진 → 줄(오선계) 크롭 — 관문 2 전처리.

    from photo_prep import extract_lines
    crops = extract_lines('photo.jpg')   # [회색 PIL 이미지, ...] 위→아래 순서

단계
  ① 회색화 + 작업 해상도로 축소(속도)
  ② 기울기 보정 — 국소 이진화한 잉크의 행 프로파일이 가장 '날카로워지는'
     각도를 찾는다(오선이 수평일 때 행 합의 분산이 최대).
  ③ 오선계 검출 — 행 프로파일에서 오선 후보 행을 뽑아 간격이 고른 연속
     5줄 묶음을 찾는다(prep.find_staff 와 같은 원리를 페이지 전체로 확장).
  ④ 각 오선계를 중심 ±5.5칸(덧줄 여유)으로 잘라 원해상도에서 크롭.

한계(기록): 원근이 심해 페이지 안에서 기울기가 줄마다 다르면 ②의 전역
보정으로 부족하다 — 줄 크롭 뒤 prep.normalize_photo 의 soft 오선 찾기가
남은 오차를 흡수한다. 실물 50장에서 미달하면 줄별 재보정을 추가할 것.
"""
import numpy as np
from PIL import Image, ImageFilter

import prep

WORK_W = 1400           # 각도·오선 탐색용 작업 폭(px)


# ───────────────────── 보정 ① 종이 검출·원근 보정 ─────────────────────

def _persp_coeffs(dst, src):
    """출력 사각형 dst(4점) → 입력 사각형 src(4점) 원근 계수 8개 (PIL 규약)."""
    A, b = [], []
    for (X, Y), (x, y) in zip(dst, src):
        A.append([X, Y, 1, 0, 0, 0, -x * X, -x * Y])
        A.append([0, 0, 0, X, Y, 1, -y * X, -y * Y])
        b += [x, y]
    return np.linalg.solve(np.asarray(A, dtype=np.float64),
                           np.asarray(b, dtype=np.float64))


def find_paper(img, work_w=800):
    """사진에서 종이 사각형 4귀퉁이 (nw, ne, se, sw) — 원본 좌표.

    밝은 화소 마스크의 대각 방향 극점 4개를 귀퉁이로 삼는다(45° 미만
    회전에서 유효). 종이가 화면 대부분이거나 못 찾으면 None(보정 생략).
    """
    w, h = img.size
    f = max(1.0, w / work_w)
    g = np.asarray(img.resize((int(w / f), int(h / f)), Image.BILINEAR),
                   dtype=np.float32) / 255.0
    lo, hi = np.percentile(g, (8, 92))
    if hi - lo < 0.25:                      # 배경·종이 명암차 없음 → 전체가 종이
        return None
    mask = g >= (lo + hi) / 2.0
    # 자잘한 밝은 점 제거(닫힘 연산 흉내)
    m = Image.fromarray((mask * 255).astype(np.uint8)) \
        .filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    mask = np.asarray(m) > 127
    # 종이 밖의 밝은 물체(스티커·라벨·옆 종이)가 극점 귀퉁이를 가로채는
    # 사고 방지: 마스크 무게중심이 속한 **연결 성분만** 남긴다(저해상도
    # 플러드필 — scipy 없이 MaxFilter 반복).
    if mask.any():
        gh0, gw0 = mask.shape
        # 해상도를 너무 낮추면 종이와 옆 물체 사이 가는 틈이 뭉개져 성분이
        # 합쳐진다(실측) — 400px 폭 기준으로 유지.
        f2 = max(1, gw0 // 400)
        small = np.asarray(Image.fromarray((mask * 255).astype(np.uint8))
                           .resize((gw0 // f2, gh0 // f2), Image.NEAREST)) > 127
        yy0, xx0 = np.nonzero(mask)
        cy, cx = int(yy0.mean()) // f2, int(xx0.mean()) // f2
        cy = min(max(cy, 0), small.shape[0] - 1)
        cx = min(max(cx, 0), small.shape[1] - 1)
        if not small[cy, cx]:               # 무게중심이 구멍이면 근처 참점
            ys2, xs2 = np.nonzero(small)
            if len(ys2) == 0:
                return None
            k = np.argmin((ys2 - cy) ** 2 + (xs2 - cx) ** 2)
            cy, cx = int(ys2[k]), int(xs2[k])
        comp = np.zeros_like(small)
        comp[cy, cx] = True
        for _ in range(400):
            grown = np.asarray(
                Image.fromarray((comp * 255).astype(np.uint8))
                .filter(ImageFilter.MaxFilter(5))) > 127
            grown &= small
            if grown.sum() == comp.sum():
                break
            comp = grown
        comp_big = np.asarray(Image.fromarray((comp * 255).astype(np.uint8))
                              .resize((gw0, gh0), Image.NEAREST)) > 127
        mask = mask & comp_big
    frac = mask.mean()
    if frac < 0.18:                         # 종이가 너무 작다 — 오검 위험
        return None
    if frac > 0.93:                         # 종이가 프레임을 채움 — 자를 것 없음
        return None
    yy, xx = np.nonzero(mask)
    s, d = xx + yy, xx - yy
    corners = [(xx[np.argmin(s)], yy[np.argmin(s)]),     # nw
               (xx[np.argmax(d)], yy[np.argmax(d)]),     # ne
               (xx[np.argmax(s)], yy[np.argmax(s)]),     # se
               (xx[np.argmin(d)], yy[np.argmin(d)])]     # sw
    # 검증 — 그늘진 종이를 배경으로 오인해 엉뚱한 사각형을 자르는 사고 방지:
    # ① 사각형 넓이가 화면의 20~95%, 마스크 넓이와도 비슷해야 하고(볼록 종이),
    # ② 사각형 안은 마스크가 짙고 밖은 옅어야 한다(진짜 종이/배경 경계).
    q = np.asarray(corners, dtype=np.float32)
    # 마주보는 변 길이가 크게 다르면(전단된 마름모) 종이가 아니다 —
    # 잘못 자르면 배율이 틀어져 뒤 전체가 망가지므로 안 자르는 쪽이 낫다.
    el = [float(np.hypot(*(q[(i + 1) % 4] - q[i]))) for i in range(4)]
    if max(el[0], el[2]) > 1.5 * min(el[0], el[2]) \
            or max(el[1], el[3]) > 1.5 * min(el[1], el[3]):
        return None
    area = 0.5 * abs(sum(q[i, 0] * q[(i + 1) % 4, 1]
                         - q[(i + 1) % 4, 0] * q[i, 1] for i in range(4)))
    gh, gw = mask.shape
    if not (0.18 * gh * gw <= area <= 0.97 * gh * gw):
        return None
    if not (0.75 <= mask.sum() / max(1.0, area) <= 1.25):
        return None
    ys, xs = np.mgrid[0:gh, 0:gw]
    inside = np.ones((gh, gw), dtype=bool)
    for i in range(4):
        ax, ay = q[i]
        bx, by = q[(i + 1) % 4]
        inside &= ((bx - ax) * (ys - ay) - (by - ay) * (xs - ax)) >= -2 * (gw + gh)
    if inside.mean() < 0.999 and mask[~inside].mean() > 0.35:
        return None
    if mask[inside].mean() < 0.80:
        return None
    return [(float(x * f), float(y * f)) for x, y in corners]


def crop_paper(img):
    """종이 사각형을 찾아 반듯한 직사각형으로 원근 보정. 못 찾으면 원본."""
    q = find_paper(img)
    if q is None:
        return img
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
    tw = int(round((np.hypot(x1 - x0, y1 - y0)
                    + np.hypot(x2 - x3, y2 - y3)) / 2))
    th = int(round((np.hypot(x3 - x0, y3 - y0)
                    + np.hypot(x2 - x1, y2 - y1)) / 2))
    if tw < 200 or th < 200:
        return img
    co = _persp_coeffs([(0, 0), (tw, 0), (tw, th), (0, th)], q)
    return img.transform((tw, th), Image.PERSPECTIVE, tuple(co),
                         resample=Image.BILINEAR, fillcolor=255)


# ───────────────────── 보정 ② 조명 평탄화 ─────────────────────

def flatten_illum(img, cell=24):
    """배경(종이) 밝기를 추정해 나눗셈으로 그림자·조명 기울기를 지운다.

    배경 = 축소본의 국소 최댓값(잉크는 어두워 걸러짐)을 부드럽게 편 것.
    종이 잘라내기 **뒤에** 쓸 것 — 어두운 책상 배경이 남아 있으면 그
    영역의 이득이 폭주한다(이득 상한으로 2차 방어).
    """
    g = np.asarray(img.convert('L'), dtype=np.float32) / 255.0
    h, w = g.shape
    sw, sh = max(2, w // cell), max(2, h // cell)
    small = Image.fromarray((g * 255).astype(np.uint8)) \
        .resize((sw, sh), Image.BILINEAR) \
        .filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.BoxBlur(2))
    bg = np.asarray(small.resize((w, h), Image.BICUBIC),
                    dtype=np.float32) / 255.0
    out = np.clip(g / np.maximum(bg, 0.18), 0, 1)
    return Image.fromarray((out * 255).astype(np.uint8))


# ───────────────────── 보정 ③ 줄 단위 되펴기(디워핑) ─────────────────────

def dewarp_line(crop, gap, strip=None):
    """줄 크롭의 휘어짐 보정 — 오선은 원래 직선이라는 성질을 쓴다.

    세로 조각(strip)마다 다섯 빗살 상관으로 오선 중심을 찾고, 2차 다항식으로
    부드럽게 이어 그 굴곡만큼 열마다 세로로 되민다. 신뢰도 낮은 조각
    (응답 약함)은 이웃 보간에 맡긴다.
    """
    g = np.asarray(crop.convert('L'), dtype=np.float32) / 255.0
    h, w = g.shape
    ink = prep.local_binarize(g)
    if strip is None:
        strip = max(24, int(gap * 2))
    xs, cs, ws = [], [], []
    ys = np.arange(h, dtype=np.float32)
    for x0 in range(0, w - strip // 2, strip):
        seg = ink[:, x0:x0 + strip]
        prof = seg.sum(axis=1).astype(np.float32)
        prof = np.convolve(prof, np.ones(3, np.float32) / 3, mode='same')
        acc = np.zeros(h, dtype=np.float32)
        for m in (-2, -1, 0, 1, 2):
            acc += np.interp(ys + m * gap, ys, prof, left=0, right=0)
        c = int(np.argmax(acc))
        if acc[c] < 5.0 * seg.shape[1] * 0.12:
            continue
        xs.append(x0 + strip / 2.0)
        cs.append(float(c))
        ws.append(float(acc[c]))
    if len(xs) < 3:
        return crop
    co = np.polyfit(np.asarray(xs), np.asarray(cs), 2, w=np.sqrt(ws))
    fit = np.polyval(co, np.arange(w, dtype=np.float32))
    shift = fit - float(np.median(fit))
    if np.abs(shift).max() < 1.0:
        return crop
    rows = np.arange(h, dtype=np.float32)[:, None] + shift[None, :]
    r0 = np.clip(np.floor(rows).astype(np.int64), 0, h - 1)
    r1 = np.clip(r0 + 1, 0, h - 1)
    t = np.clip(rows - r0, 0, 1).astype(np.float32)
    cols = np.arange(w)[None, :].repeat(h, axis=0)
    out = g[r0, cols] * (1 - t) + g[r1, cols] * t
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def _ink_small(img, work_w=WORK_W):
    """회색 PIL → (작업 해상도 잉크배열, 축소 배율)."""
    w, h = img.size
    f = max(1.0, w / work_w)
    small = img.resize((int(w / f), int(h / f)), Image.BILINEAR)
    g = np.asarray(small, dtype=np.float32) / 255.0
    return prep.local_binarize(g, win=25, k=0.10), f


def deskew_angle(ink, lo=-20.0, hi=20.0):
    """행 프로파일 분산을 최대화하는 회전각(도). 굵게 1.5° → 가늘게 0.25°.

    범위를 ±6°로 캡했더니 ~20° 돌아간 실물 사진(190127)이 통째로
    무너졌다(실측) — 폰사진은 크게 돌아갈 수 있다."""
    im = Image.fromarray((ink * 255).astype(np.uint8))

    def sharp(deg):
        r = im.rotate(deg, resample=Image.BILINEAR, fillcolor=0, expand=False)
        p = np.asarray(r, dtype=np.float32).sum(axis=1)
        return float(((p - p.mean()) ** 2).mean())

    best = max(np.arange(lo, hi + 0.5, 1.5), key=sharp)
    mid = max(np.arange(best - 1.5, best + 1.6, 0.5), key=sharp)
    fine = np.arange(mid - 0.5, mid + 0.55, 0.1)
    return float(max(fine, key=sharp))


def find_systems(ink, min_gap=6.0, max_gap=40.0, max_systems=16,
                 tap_frac=0.12, floor_frac=0.16):
    """작업 해상도 잉크배열 → [(중심행, 줄간격), ...] 위→아래.

    빗살(comb) 상관: 중심행 y·간격 g 마다 다섯 오선 위치의 행 잉크량을
    합산해 응답을 만들고, 응답이 큰 (y, g) 를 탐욕적으로 채택한 뒤 그
    구역을 지운다. 오선이 끊기거나(합산이라 상관없음) 잔여 기울기로
    행이 몇 px 번져도(이웃 행 완충) 견딘다 — 밴드 나열 방식의 약점 보완.
    """
    h, w = ink.shape
    prof = ink.sum(axis=1).astype(np.float32)
    if prof.max() <= 0:
        return []
    # 잔여 기울기 완충: 이웃 3행 이동평균
    k = np.array([1, 1, 1], dtype=np.float32) / 3.0
    prof = np.convolve(prof, k, mode='same')

    gaps = np.arange(min_gap, max_gap + 0.25, 0.5, dtype=np.float32)
    ys = np.arange(h, dtype=np.float32)
    resp = np.zeros((len(gaps), h), dtype=np.float32)
    for gi, g in enumerate(gaps):
        taps = np.stack([np.interp(ys + m * g, ys, prof, left=0, right=0)
                         for m in (-2, -1, 0, 1, 2)])
        # 하모닉 차단: 반간격 빗살은 줄 사이 빈 행을, 배간격 빗살은 오선
        # 밖 빈 행을 찍는다 → 다섯 빗살의 최솟값이 작으면 오선계가 아니다.
        # 문턱을 낮추면 16분음표 빔 무리가 가짜 오선계로 무더기 검출된다
        # (실측) — 원거리 사진의 스케일 문제는 종이 잘라내기가 해결한다.
        resp[gi] = np.where(taps.min(axis=0) >= w * tap_frac,
                            taps.sum(axis=0), 0.0)
    floor = 5.0 * w * floor_frac
    out = []
    r = resp.copy()
    while len(out) < max_systems:
        gi, y = np.unravel_index(np.argmax(r), r.shape)
        if r[gi, y] < floor:
            break
        g = float(gaps[gi])
        out.append((float(y), g, float(r[gi, y])))
        y0 = max(0, int(y - 3.5 * g))
        y1 = min(h, int(y + 3.5 * g) + 1)
        r[:, y0:y1] = 0.0
    # 한 페이지의 오선계는 줄간격이 같다 — **응답이 가장 큰 검출**(폭
    # 전체를 가로지르는 진짜 오선)의 간격을 기준으로 벗어난 것(제목 텍스트,
    # 빔 무리)을 버린다. 개수 중앙값 기준은 빔 오검이 다수가 되는 순간
    # 진짜 오선을 거꾸로 죽였다(실측).
    if len(out) >= 2:
        ref = max(out, key=lambda t: t[2])[1]
        out = [(y, g, s) for y, g, s in out if 0.72 * ref <= g <= 1.38 * ref]
    out.sort()
    return [(y, g) for y, g, _s in out]


def rectify_by_staves(img, work_w=WORK_W):
    """오선으로 원근 잔재를 편다 — 종이 테두리보다 튼튼한 신호.

    좌/우 반쪽에서 따로 찾은 오선계의 y 차이(dy)는 그 높이의 기울기다.
    dy(y) 를 1차로 피팅해(원근이면 y 에 따라 변한다) 열·행별 세로
    재매핑으로 상쇄한다. 짝이 3개 미만이면 그대로 둔다.
    """
    ink, f = _ink_small(img, work_w)
    h2, w2 = ink.shape
    L = find_systems(ink[:, :w2 // 2])
    R = find_systems(ink[:, w2 // 2:])
    pairs = []
    for yl, gl in L:
        best = None
        for yr, gr in R:
            if abs(yr - yl) < 4 * max(gl, gr):
                if best is None or abs(yr - yl) < abs(best[0] - yl):
                    best = (yr, gr)
        if best is not None:
            pairs.append((yl, best[0] - yl))
    if len(pairs) < 3:
        return img
    ys = np.asarray([p[0] for p in pairs], dtype=np.float64)
    dy = np.asarray([p[1] for p in pairs], dtype=np.float64)
    if len(pairs) >= 5:
        b, a = np.polyfit(ys, dy, 1)          # dy(y) ≈ a + b·y
        # 피팅이 관측을 못 설명하면(좌/우 짝 어긋남) 워프 금지 — 어긋난
        # 전단은 이미지를 통째로 망가뜨린다(실측 190127: 12→3보표).
        resid = float(np.median(np.abs(a + b * ys - dy)))
        if resid > 1.5:
            return img
    else:
        a, b = float(np.median(dy)), 0.0      # 짝이 적으면 상수 전단만
    if abs(a) < 0.8 and abs(b) * h2 < 0.8:    # 이미 수평 — 건드리지 않는다
        return img
    if abs(a) + abs(b) * h2 > 12.0:           # 비정상적으로 큰 보정 — 불신
        return img
    g = np.asarray(img, dtype=np.float32)
    H, W = g.shape
    sf = H / float(h2)
    cols = np.arange(W, dtype=np.float32)
    rows = np.arange(H, dtype=np.float32)
    # 작업 좌표의 dy 를 원본 배율로: 중심 대비 열 위치 비율 × 그 행의 기울기
    tilt = (a + b * (rows / sf)) * sf         # 행별 좌→우 전체 낙차(px, 원본)
    shift = ((cols - W / 2.0) / (W / 2.0))[None, :] * (tilt / 2.0)[:, None]
    src = rows[:, None] + shift
    r0 = np.clip(np.floor(src).astype(np.int64), 0, H - 1)
    r1 = np.clip(r0 + 1, 0, H - 1)
    t = np.clip(src - r0, 0, 1).astype(np.float32)
    cc = np.arange(W)[None, :].repeat(H, axis=0)
    out = g[r0, cc] * (1 - t) + g[r1, cc] * t
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def _find_systems_multi(ink):
    """전체 폭 + 좌/우 반쪽에서 각각 오선계를 찾아 병합.

    원근이 남은 사진은 오선 행이 폭 전체에선 수 픽셀 번져 빗살 응답이
    죽지만, 반쪽에서는 절반만 번져 살아난다(실측). 반쪽 검출은 전체
    검출에 없는 y 만 보탠다."""
    w = ink.shape[1]
    out = list(find_systems(ink))
    for half in (ink[:, :w // 2], ink[:, w // 2:]):
        for y, g in find_systems(half):
            if all(abs(y - y0) > 2.5 * max(g, g0) for y0, g0 in out):
                out.append((y, g))
    out.sort()
    return out


def fill_missing(ink, systems):
    """검출 보표 사이 '구멍'(이웃 간격의 1.7배 초과 벌어짐)과 페이지
    위·아래 여백을 문턱을 낮춰 국소 재탐색해 누락 보표를 채운다.

    낮춘 문턱은 구멍 안에서만 쓰므로 전역 오검(빔 무리)이 되살아나지
    않고, 찾은 것도 기준 간격(±38%) 검사를 통과해야 채택된다."""
    if len(systems) < 2:
        return systems
    h = ink.shape[0]
    ref = sorted(g for _y, g in systems)[len(systems) // 2]
    ys = [y for y, _g in systems]
    diffs = sorted(b - a for a, b in zip(ys, ys[1:]))
    step = diffs[len(diffs) // 2]           # 이웃 보표 중심 간격의 중앙값
    holes = []
    for a, b in zip(ys, ys[1:]):
        if b - a > 1.7 * step:
            holes.append((a + 2.5 * ref, b - 2.5 * ref))
    if ys[0] - 2.5 * ref > 0.9 * step:      # 첫 보표 위 여백
        holes.append((0, ys[0] - 2.5 * ref))
    if h - ys[-1] - 2.5 * ref > 0.9 * step:  # 마지막 보표 아래 여백
        holes.append((ys[-1] + 2.5 * ref, h))
    out = list(systems)
    for y0, y1 in holes:
        y0, y1 = max(0, int(y0)), min(h, int(y1))
        if y1 - y0 < 5 * ref:
            continue
        band = ink[y0:y1]
        found = find_systems(band, tap_frac=0.07, floor_frac=0.10)
        for by, bg in found:
            if not (0.72 * ref <= bg <= 1.38 * ref):
                continue
            ay = by + y0
            if all(abs(ay - y) > 2.5 * max(bg, g) for y, g in out):
                out.append((ay, bg))
    out.sort()
    return out


def extract_lines(path_or_img, pad_ratio=5.5, work_w=WORK_W, correct=True,
                  with_pos=False):
    """사진 → [회색 줄 크롭(PIL), ...] 위→아래. 크롭은 원해상도.

    correct=True: 종이 원근 보정 → 조명 평탄화 → 기울기 보정 →
    오선계 검출 → 줄 크롭 → 줄 단위 되펴기. False 는 기울기 보정과
    검출만 하는 구버전 경로(전/후 비교용).
    """
    img = path_or_img if isinstance(path_or_img, Image.Image) \
        else Image.open(path_or_img)
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img)      # 폰사진은 EXIF 회전 필수
    img = img.convert('L')
    if correct:
        img = crop_paper(img)                        # ① 종이·원근
        img = flatten_illum(img)                     # ② 조명
    ink, f = _ink_small(img, work_w)
    ang = deskew_angle(ink)
    if abs(ang) > 0.05:
        # 큰 각에서 expand=False 는 모서리 보표를 잘라먹는다(실측 190127)
        img = img.rotate(ang, resample=Image.BILINEAR, fillcolor=255,
                         expand=abs(ang) > 3.0)
    if correct:
        img = rectify_by_staves(img)                 # ①′ 오선 기반 원근 상쇄
    ink, f = _ink_small(img, work_w)
    systems = _find_systems_multi(ink)
    # 멀리 찍어 줄간격이 작업 해상도에서 너무 작으면(선이 1px 로 뭉개짐)
    # 해상도를 키워 다시 찾는다 — 원거리 사진 대응 2패스.
    if systems:
        med = sorted(g for _y, g in systems)[len(systems) // 2]
        if med < 12.0:
            work_w2 = min(int(work_w * 14.0 / med), 3200, img.size[0])
            if work_w2 > work_w * 1.15:
                ink2, f2 = _ink_small(img, work_w2)
                systems2 = _find_systems_multi(ink2)
                # 고해상도 재검출이 더 적게 찾으면(그림자·빔 잡음) 원래 것 유지
                if len(systems2) >= len(systems):
                    ink, f, systems = ink2, f2, systems2
    systems = fill_missing(ink, systems)
    crops = []
    W, H = img.size
    for cy, gap in systems:
        cy0, g0 = cy * f, gap * f                    # 원해상도 좌표
        top = max(0, int(cy0 - pad_ratio * g0))
        bot = min(H, int(cy0 + pad_ratio * g0))
        band = ink[max(0, int(cy - pad_ratio * gap)):
                   min(ink.shape[0], int(cy + pad_ratio * gap))]
        cols = band.sum(axis=0)
        on = cols > max(1.0, band.shape[0] * 0.02)
        # 펼친 책 사진은 옆 페이지 조각·책 모서리가 같은 높이에 걸린다 —
        # 잉크 열이 이어지는 **가장 긴 구간** 하나만 줄로 삼는다
        # (작은 끊김 ≤ 3칸은 마디 사이 여백으로 보고 잇는다).
        runs, i0 = [], None
        gap_tol = max(4, int(3 * gap))
        last_on = -10 ** 9
        for x in range(len(on)):
            if on[x]:
                if i0 is None or x - last_on > gap_tol:
                    if i0 is not None:
                        runs.append((i0, last_on))
                    i0 = x
                last_on = x
        if i0 is not None:
            runs.append((i0, last_on))
        if not runs:
            x0, x1 = 0, W
        else:
            r0, r1 = max(runs, key=lambda r: r[1] - r[0])
            x0 = max(0, int(r0 * f - 2 * g0))
            x1 = min(W, int((r1 + 1) * f + 2 * g0))
        c = img.crop((x0, top, x1, bot))
        if correct:
            c = dewarp_line(c, g0)                   # ③ 되펴기
        crops.append((c, cy0, g0) if with_pos else c)
    return crops


def load_photo_lines(path, correct=True, **kw):
    """사진 → 모델 입력 [(160, W) 잉크배열, ...] — normalize_photo 통과."""
    return [prep.normalize_photo(c, **kw)
            for c in extract_lines(path, correct=correct)]
