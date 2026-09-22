# -*- coding: utf-8 -*-
"""줄 이미지 전처리 — **학습과 추론이 반드시 같은 함수를 쓴다.**

왜 오선 간격으로 정규화하나
  공장은 보표 크기를 18~26 로 흔들고(조판 다양성), LilyPond 의
  one-line-auto-height-breaking 은 내용에 맞춰 높이를 잘라낸다. 그래서
  **이미지 높이로 정규화하면 같은 악보가 덧줄 유무에 따라 다른 배율로
  들어간다.** 오선 다섯 줄을 찾아 줄 간격(interline)을 고정 배율로 맞추고
  오선을 세로 중앙에 두면 배율·위치가 항상 같아진다. 실제 사진에도 같은
  전처리를 적용하면 조판 배율·촬영 거리 차이가 흡수된다.

    from prep import load_line
    x = load_line('a.png')        # (1, H, W) float32, 0=흰 1=검
"""
import numpy as np
from PIL import Image, ImageFilter

INTERLINE = 12          # 오선 줄 간격을 이 픽셀로 맞춘다
HEIGHT = 160            # 최종 높이(오선 중앙 정렬, 위아래로 덧줄 여유 ~4.5칸)
MIN_W, MAX_W = 32, 4096


def _gray(img):
    if img.mode != 'L':
        img = img.convert('L')
    return img


def find_staff(a, soft=False):
    """세로 방향 잉크 분포에서 오선 다섯 줄을 찾아 (중심y, 줄간격) 반환.

    못 찾으면 None. a 는 잉크=1 로 정규화된 (H, W) 배열.
    soft=True: 실사 사진용 — 오선이 노이즈·원근으로 끊겨 행 합이 낮아지므로
    문턱과 간격 균일성 조건을 완화한다. 깨끗한 렌더(관문 1) 경로는 기본값 그대로.
    """
    prof = a.sum(axis=1)
    if prof.max() <= 0:
        return None
    # 오선은 가로로 거의 끝까지 이어지므로 폭의 절반 이상 찍힌 행만 후보
    if soft:
        thr = max(prof.max() * 0.35, a.shape[1] * 0.22)
    else:
        thr = max(prof.max() * 0.45, a.shape[1] * 0.5)
    rows = prof >= thr
    bands, i = [], 0
    while i < len(rows):
        if rows[i]:
            j = i
            while j + 1 < len(rows) and rows[j + 1]:
                j += 1
            bands.append((i + j) / 2.0)
            i = j + 1
        else:
            i += 1
    if len(bands) < 5:
        return None
    # 간격이 가장 고른 연속 5줄
    best, score = None, None
    for k in range(len(bands) - 4):
        g = [bands[k + m + 1] - bands[k + m] for m in range(4)]
        mean = sum(g) / 4
        if mean <= 1.0:
            continue
        var = sum((x - mean) ** 2 for x in g) / 4
        s = var / (mean ** 2)
        if score is None or s < score:
            score, best = s, (bands[k + 2], mean)
    if best is None or score > (0.12 if soft else 0.05):
        return None
    return best


def normalize(img, interline=INTERLINE, height=HEIGHT):
    """오선 간격을 맞추고 오선을 세로 중앙에 둔 (H, W) 잉크배열(0~1)."""
    a = 1.0 - np.asarray(_gray(img), dtype=np.float32) / 255.0
    st = find_staff(a)
    if st is None:
        # 오선을 못 찾으면 높이 기준으로 넘어간다(그런 줄은 학습에서 걸러진다)
        scale = height / max(1, a.shape[0])
        cy = a.shape[0] / 2.0
    else:
        cy, gap = st
        scale = interline / gap
    w = max(MIN_W, min(MAX_W, int(round(a.shape[1] * scale))))
    h = max(1, int(round(a.shape[0] * scale)))
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    b = np.asarray(im, dtype=np.float32) / 255.0
    out = np.zeros((height, w), dtype=np.float32)
    top = int(round(cy * scale - height / 2.0))
    src0, dst0 = max(0, top), max(0, -top)
    n = min(h - src0, height - dst0)
    if n > 0:
        out[dst0:dst0 + n] = b[src0:src0 + n]
    return out


def load_line(path, **kw):
    with Image.open(path) as im:
        return normalize(im, **kw)[None, :, :]


# ───────────────────── 실사 사진 경로 (관문 2) ─────────────────────
# 깨끗한 렌더는 배경이 완전한 흰색이라 `1 − gray` 가 곧 잉크지만, 사진은
# 조명·종이색 때문에 배경이 0.1~0.4 로 떠 있다. 그래서 **오선 찾기만
# 국소 이진화로 하고, 모델 입력 픽셀은 회색 원본을 그대로 쓴다** —
# 배경 얼룩을 다루는 법은 증강 미세조정으로 모델이 배운다.

def local_binarize(gray, win=31, k=0.12):
    """(H, W) 회색 0~1(1=밝음) → 잉크=1 이진배열. 국소 평균보다 k 만큼
    어두우면 잉크로 본다(창 크기는 줄간격 몇 배면 충분)."""
    img = Image.fromarray((gray * 255).astype(np.uint8))
    mean = np.asarray(img.filter(ImageFilter.BoxBlur(max(3, win // 2))),
                      dtype=np.float32) / 255.0
    return (gray < mean - k).astype(np.float32)


def _comb_center(ink, gap):
    """간격을 알 때 오선 중심만 찾는다 — 다섯 빗살 응답 최대 행.

    탐색을 **크롭 중앙 ±2.5칸**으로 제한한다: 크롭 밴드(±5.5칸)에 이웃
    보표 일부가 걸리면 전역 최대가 이웃을 잡아 오선을 화면 밖으로 미는
    사고가 났다(실측 190139(0): 17→85% 역행)."""
    prof = ink.sum(axis=1).astype(np.float32)
    prof = np.convolve(prof, np.ones(3, np.float32) / 3, mode='same')
    ys = np.arange(len(prof), dtype=np.float32)
    acc = np.zeros(len(prof), dtype=np.float32)
    for m in (-2, -1, 0, 1, 2):
        acc += np.interp(ys + m * gap, ys, prof, left=0, right=0)
    mid = len(prof) / 2.0
    lo = max(0, int(mid - 2.5 * gap))
    hi = min(len(prof), int(mid + 2.5 * gap) + 1)
    if hi <= lo:
        return float(np.argmax(acc))
    return float(lo + np.argmax(acc[lo:hi]))


def normalize_photo(img, interline=INTERLINE, height=HEIGHT, gap_hint=None):
    """사진 줄 한 장 → 학습과 같은 (H, W) 잉크배열.

    학습(augment_photo 뒤)과 추론(photo_prep 크롭 뒤)이 **반드시 이 함수를
    같이 쓴다** — 관문 1 의 '같은 전처리' 원칙 그대로.
    gap_hint: 페이지 오선계 검출이 잰 줄간격(신뢰도 높음). 크롭 내 재측정이
    이것과 25% 이상 어긋나면 힌트를 쓴다 — 흐릿한 원거리 크롭에서 soft
    재측정이 배율을 무너뜨리는 사고를 실측(190158 줄13)으로 확인.
    """
    g = np.asarray(_gray(img), dtype=np.float32) / 255.0
    ink = local_binarize(g)
    st = find_staff(ink, soft=True)
    a = np.clip(1.0 - g, 0.0, 1.0)
    if gap_hint and (st is None or not (0.75 * gap_hint <= st[1] <= 1.33 * gap_hint)):
        st = (_comb_center(ink, gap_hint), float(gap_hint))
    if st is None:
        scale = height / max(1, a.shape[0])
        cy = a.shape[0] / 2.0
    else:
        cy, gap = st
        scale = interline / gap
    w = max(MIN_W, min(MAX_W, int(round(a.shape[1] * scale))))
    h = max(1, int(round(a.shape[0] * scale)))
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    b = np.asarray(im, dtype=np.float32) / 255.0
    out = np.zeros((height, w), dtype=np.float32)
    top = int(round(cy * scale - height / 2.0))
    src0, dst0 = max(0, top), max(0, -top)
    n = min(h - src0, height - dst0)
    if n > 0:
        out[dst0:dst0 + n] = b[src0:src0 + n]
    return out
