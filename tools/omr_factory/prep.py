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
from PIL import Image

INTERLINE = 12          # 오선 줄 간격을 이 픽셀로 맞춘다
HEIGHT = 160            # 최종 높이(오선 중앙 정렬, 위아래로 덧줄 여유 ~4.5칸)
MIN_W, MAX_W = 32, 4096


def _gray(img):
    if img.mode != 'L':
        img = img.convert('L')
    return img


def find_staff(a):
    """세로 방향 잉크 분포에서 오선 다섯 줄을 찾아 (중심y, 줄간격) 반환.

    못 찾으면 None. a 는 잉크=1 로 정규화된 (H, W) 배열.
    """
    prof = a.sum(axis=1)
    if prof.max() <= 0:
        return None
    # 오선은 가로로 거의 끝까지 이어지므로 폭의 절반 이상 찍힌 행만 후보
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
    if best is None or score > 0.05:
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
