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
    # 그늘진 종이를 배경으로 오인하는 사고 방지: 진짜 배경(책상)이 있으면
    # **테두리**가 중앙보다 뚜렷이 어둡다. 아니면 종이가 프레임을 채운 것
    # 이므로 자르지 않는다(조명 얼룩은 ② 평탄화가 처리).
    gh, gw = g.shape
    b = max(2, int(min(gh, gw) * 0.04))
    border = np.concatenate([g[:b].ravel(), g[-b:].ravel(),
                             g[:, :b].ravel(), g[:, -b:].ravel()])
    inner = g[int(gh * 0.25):int(gh * 0.75), int(gw * 0.25):int(gw * 0.75)]
    if np.median(border) > np.median(inner) - 0.20:
        return None
    mask = g >= (lo + hi) / 2.0
    # 자잘한 밝은 점 제거(닫힘 연산 흉내)
    m = Image.fromarray((mask * 255).astype(np.uint8)) \
        .filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    mask = np.asarray(m) > 127
    if mask.mean() < 0.25:                  # 종이가 너무 작다 — 오검 위험
        return None
    yy, xx = np.nonzero(mask)
    s, d = xx + yy, xx - yy
    corners = [(xx[np.argmin(s)], yy[np.argmin(s)]),     # nw
               (xx[np.argmax(d)], yy[np.argmax(d)]),     # ne
               (xx[np.argmax(s)], yy[np.argmax(s)]),     # se
               (xx[np.argmin(d)], yy[np.argmin(d)])]     # sw
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


def deskew_angle(ink, lo=-6.0, hi=6.0):
    """행 프로파일 분산을 최대화하는 회전각(도). 굵게 0.5° → 가늘게 0.1°."""
    im = Image.fromarray((ink * 255).astype(np.uint8))

    def sharp(deg):
        r = im.rotate(deg, resample=Image.BILINEAR, fillcolor=0, expand=False)
        p = np.asarray(r, dtype=np.float32).sum(axis=1)
        return float(((p - p.mean()) ** 2).mean())

    best = max(np.arange(lo, hi + 0.25, 0.5), key=sharp)
    fine = np.arange(best - 0.5, best + 0.55, 0.1)
    return float(max(fine, key=sharp))


def find_systems(ink, min_gap=6.0, max_gap=40.0, max_systems=16):
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
        resp[gi] = np.where(taps.min(axis=0) >= w * 0.12,
                            taps.sum(axis=0), 0.0)
    floor = 5.0 * w * 0.16          # 오선 한 줄이 폭의 16% 이상은 찍힌다고 본다
    out = []
    r = resp.copy()
    while len(out) < max_systems:
        gi, y = np.unravel_index(np.argmax(r), r.shape)
        if r[gi, y] < floor:
            break
        g = float(gaps[gi])
        out.append((float(y), g))
        y0 = max(0, int(y - 3.5 * g))
        y1 = min(h, int(y + 3.5 * g) + 1)
        r[:, y0:y1] = 0.0
    out.sort()
    return out


def extract_lines(path_or_img, pad_ratio=5.5, work_w=WORK_W, correct=True):
    """사진 → [회색 줄 크롭(PIL), ...] 위→아래. 크롭은 원해상도.

    correct=True: 종이 원근 보정 → 조명 평탄화 → 기울기 보정 →
    오선계 검출 → 줄 크롭 → 줄 단위 되펴기. False 는 기울기 보정과
    검출만 하는 구버전 경로(전/후 비교용).
    """
    img = path_or_img if isinstance(path_or_img, Image.Image) \
        else Image.open(path_or_img)
    img = img.convert('L')
    if correct:
        img = crop_paper(img)                        # ① 종이·원근
        img = flatten_illum(img)                     # ② 조명
    ink, f = _ink_small(img, work_w)
    ang = deskew_angle(ink)
    if abs(ang) > 0.05:
        img = img.rotate(ang, resample=Image.BILINEAR, fillcolor=255,
                         expand=False)
        ink, f = _ink_small(img, work_w)
    systems = find_systems(ink)
    crops = []
    W, H = img.size
    for cy, gap in systems:
        cy0, g0 = cy * f, gap * f                    # 원해상도 좌표
        top = max(0, int(cy0 - pad_ratio * g0))
        bot = min(H, int(cy0 + pad_ratio * g0))
        band = ink[max(0, int(cy - pad_ratio * gap)):
                   min(ink.shape[0], int(cy + pad_ratio * gap))]
        cols = band.sum(axis=0)
        on = np.where(cols > max(1.0, band.shape[0] * 0.02))[0]
        if len(on) == 0:
            x0, x1 = 0, W
        else:
            x0 = max(0, int(on[0] * f - 2 * g0))
            x1 = min(W, int((on[-1] + 1) * f + 2 * g0))
        c = img.crop((x0, top, x1, bot))
        if correct:
            c = dewarp_line(c, g0)                   # ③ 되펴기
        crops.append(c)
    return crops


def load_photo_lines(path, correct=True, **kw):
    """사진 → 모델 입력 [(160, W) 잉크배열, ...] — normalize_photo 통과."""
    return [prep.normalize_photo(c, **kw)
            for c in extract_lines(path, correct=correct)]
