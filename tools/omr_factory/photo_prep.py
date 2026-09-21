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
from PIL import Image

import prep

WORK_W = 1400           # 각도·오선 탐색용 작업 폭(px)


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


def extract_lines(path_or_img, pad_ratio=5.5, work_w=WORK_W):
    """사진 → [회색 줄 크롭(PIL), ...] 위→아래. 크롭은 원해상도."""
    img = path_or_img if isinstance(path_or_img, Image.Image) \
        else Image.open(path_or_img)
    img = img.convert('L')
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
        crops.append(img.crop((x0, top, x1, bot)))
    return crops


def load_photo_lines(path, **kw):
    """사진 → 모델 입력 [(160, W) 잉크배열, ...] — normalize_photo 통과."""
    return [prep.normalize_photo(c, **kw) for c in extract_lines(path)]
