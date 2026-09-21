#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""모의 폰사진 생성 — 관문 2 자체 평가용.

시험 분할(test)의 300DPI 원본 줄들을 A4 페이지에 위→아래로 심고,
페이지 전체에 실사풍 열화(원근·회전·그늘·종이결·흐림·잡음·저해상도·JPEG)를
걸어 '사장님 폰사진'을 흉내낸다. 정답 토큰은 줄 순서대로 truth.json 에 남긴다.

    python tools/omr_factory/mock_photos.py --data C:/Users/me/omr_lines \
        --out C:/Users/me/omr_photo_mock --pages 60 --seed 77

출력: OUT/page_0000.jpg + OUT/page_0000.json (+ truth.jsonl 색인)
주의: 이미지 출력물은 커밋 금지(데이터 규칙). 수치만 진행일지에 기록.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import photo_prep
import prep

A4 = (2480, 3508)               # 300DPI A4
MARGIN_X, MARGIN_TOP = 90, 210
LINE_W = A4[0] - 2 * MARGIN_X   # 줄 최대 폭


def _curl(g, rng, s):
    """종이 휘어짐 — 열마다 세로로 미는 부드러운 굴곡(가운데 불룩/한쪽 들림)."""
    h, w = g.shape
    A = rng.uniform(8, 30) * s * rng.choice([-1, 1])
    phase = rng.uniform(0, np.pi)
    d = (A * np.sin(np.pi * np.arange(w, dtype=np.float32) / w + phase))
    rows = np.arange(h, dtype=np.float32)[:, None] - d[None, :]
    r0 = np.clip(np.floor(rows).astype(np.int64), 0, h - 1)
    r1 = np.clip(r0 + 1, 0, h - 1)
    t = np.clip(rows - r0, 0, 1).astype(np.float32)
    cols = np.arange(w)[None, :].repeat(h, axis=0)
    return g[r0, cols] * (1 - t) + g[r1, cols] * t


def degrade_page(g, rng, s=1.0):
    """(H, W) 회색 0~1 페이지 → 열화된 회색 폰사진 흉내.

    순서: 종이 성질(휘어짐→종이결) → 장면 배치(어두운 배경 위 원근·회전)
    → 촬영(조명·그늘→광학→센서→다운샘플/JPEG). 배경·원근·휘어짐은
    photo_prep 의 보정 ①②③이 되돌려야 할 대상이다.
    """
    h, w = g.shape
    # 종이: 휘어짐
    g = _curl(g, rng, s)
    # 종이: 종이결 + 톤
    small = rng.random((max(2, h // 16), max(2, w // 16))).astype(np.float32)
    tex = np.asarray(Image.fromarray((small * 255).astype(np.uint8))
                     .resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
    g = np.clip(g - (tex - 0.5) * 0.10 * s * g, 0, 1)
    g = g * rng.uniform(1.0 - 0.18 * s, 1.0)
    # 장면: 어두운 배경(책상) 위에 원근·회전으로 배치
    bw, bh = int(w * 1.12), int(h * 1.12)
    bg = np.full((bh, bw), rng.uniform(0.10, 0.42), dtype=np.float32)
    bn = rng.random((max(2, bh // 40), max(2, bw // 40))).astype(np.float32)
    bg += (np.asarray(Image.fromarray((bn * 255).astype(np.uint8))
                      .resize((bw, bh), Image.BICUBIC),
                      dtype=np.float32) / 255.0 - 0.5) * 0.12
    fit = rng.uniform(0.86, 0.97)
    pw, ph = int(w * fit * 1.12), int(h * fit * 1.12)
    ox, oy = (bw - pw) / 2, (bh - ph) / 2
    j = 0.022 * s * min(pw, ph)
    quad = [(ox + rng.uniform(-j, j), oy + rng.uniform(-j, j)),
            (ox + pw + rng.uniform(-j, j), oy + rng.uniform(-j, j)),
            (ox + pw + rng.uniform(-j, j), oy + ph + rng.uniform(-j, j)),
            (ox + rng.uniform(-j, j), oy + ph + rng.uniform(-j, j))]
    co = tuple(photo_prep._persp_coeffs(
        quad, [(0, 0), (w, 0), (w, h), (0, h)]))
    paper = Image.fromarray((g * 255).astype(np.uint8))
    warp = np.asarray(paper.transform((bw, bh), Image.PERSPECTIVE, co,
                                      resample=Image.BILINEAR, fillcolor=0),
                      dtype=np.float32) / 255.0
    mask = np.asarray(Image.new('L', (w, h), 255)
                      .transform((bw, bh), Image.PERSPECTIVE, co,
                                 resample=Image.BILINEAR, fillcolor=0),
                      dtype=np.float32) / 255.0
    g = bg * (1 - mask) + warp * mask
    ang = rng.normal(0, 1.2 * s)
    img = Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)) \
        .rotate(ang, resample=Image.BILINEAR, expand=False,
                fillcolor=int(bg.mean() * 255))
    g = np.asarray(img, dtype=np.float32) / 255.0
    bh, bw = g.shape
    # 촬영: 조명 그라데이션 + 그림자 덩어리
    gx = np.linspace(0, 1, bw, dtype=np.float32)[None, :]
    gy = np.linspace(0, 1, bh, dtype=np.float32)[:, None]
    g = g * (1.0 - 0.28 * s * np.clip(rng.uniform(-1, 1) * gx
                                      + rng.uniform(-1, 1) * gy, -1, 1))
    if rng.random() < 0.7:
        cx, cy = rng.uniform(0, 1), rng.uniform(0, 1)
        sx, sy = rng.uniform(0.2, 0.6), rng.uniform(0.2, 0.6)
        blob = np.exp(-(((gx - cx) / sx) ** 2 + ((gy - cy) / sy) ** 2))
        g = g * (1.0 - rng.uniform(0.08, 0.28) * s * blob.astype(np.float32))
    g = np.clip(g, 0, 1)
    # 광학 흐림
    img = Image.fromarray((g * 255).astype(np.uint8))
    r = abs(rng.normal(0, 0.9 * s))
    if r > 0.2:
        img = img.filter(ImageFilter.GaussianBlur(r))
    # 센서 잡음
    g = np.asarray(img, dtype=np.float32) / 255.0
    g = np.clip(g + rng.normal(0, 0.025 * s, g.shape).astype(np.float32), 0, 1)
    # 다운샘플(폰 해상도) — 마지막에 JPEG
    img = Image.fromarray((g * 255).astype(np.uint8))
    long_side = int(rng.uniform(2200, 3600))
    f = max(bw, bh) / long_side
    if f > 1.02:
        img = img.resize((int(bw / f), int(bh / f)), Image.BILINEAR)
    return img, int(rng.uniform(55, 90))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pages', type=int, default=60)
    ap.add_argument('--split', default='test')
    ap.add_argument('--seed', type=int, default=77)
    ap.add_argument('--strength', type=float, default=1.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)

    rows = []
    for ln in open(os.path.join(a.data, 'index.jsonl'), encoding='utf-8'):
        r = json.loads(ln)
        if r['split'] == a.split:
            rows.append(r)
    print(f'{a.split} 줄 {len(rows)}개에서 페이지 {a.pages}장 생성', flush=True)
    order = rng.permutation(len(rows))

    idx = open(os.path.join(a.out, 'truth.jsonl'), 'w', encoding='utf-8')
    used = 0
    for p in range(a.pages):
        canvas = np.ones((A4[1], A4[0]), dtype=np.float32)
        y = MARGIN_TOP + int(rng.uniform(0, 80))
        # 실제 A4 악보의 줄간격(~2mm=24px@300DPI) 근처로 페이지마다 고정 —
        # 줄 폭에 맞춰 늘리면 원본 폭 편차 때문에 줄간격이 4~30px 로 널뛴다.
        target_gap = rng.uniform(17.0, 24.0)
        lines = []
        while used < len(order):
            r = rows[order[used]]
            orig = os.path.join(a.data, r['cache'][6:])
            try:
                with Image.open(orig) as im:
                    g = np.asarray(im.convert('L'), dtype=np.float32) / 255.0
            except Exception:
                used += 1
                continue
            h0, w0 = g.shape
            st = prep.find_staff(1.0 - g)
            if st is None:
                used += 1
                continue
            f = min(target_gap / st[1], LINE_W / w0)
            nh, nw = max(1, int(h0 * f)), max(1, int(w0 * f))
            gs = np.asarray(Image.fromarray((g * 255).astype(np.uint8))
                            .resize((nw, nh), Image.BILINEAR),
                            dtype=np.float32) / 255.0
            if y + nh > A4[1] - 140:
                break
            x0 = MARGIN_X + int(rng.uniform(-25, 25))
            x0 = max(0, min(A4[0] - nw, x0))
            canvas[y:y + nh, x0:x0 + nw] = np.minimum(
                canvas[y:y + nh, x0:x0 + nw], gs)
            lines.append(dict(song=r['song'], chunk=r['chunk'],
                              shift=r['shift'], tokens=r['tokens']))
            used += 1
            y += nh + int(rng.uniform(70, 150))
        if not lines:
            break
        img, q = degrade_page(canvas, rng, a.strength)
        name = f'page_{p:04d}'
        img.save(os.path.join(a.out, name + '.jpg'), quality=q)
        meta = dict(page=name + '.jpg', jpeg_q=q, lines=lines)
        json.dump(meta, open(os.path.join(a.out, name + '.json'), 'w',
                             encoding='utf-8'), ensure_ascii=False)
        idx.write(json.dumps(dict(page=name, n=len(lines)),
                             ensure_ascii=False) + '\n')
        if (p + 1) % 10 == 0:
            print(f'  {p + 1}/{a.pages} (줄 {used})', flush=True)
    idx.close()
    print(f'끝: 페이지 {p + 1}장 / 줄 {used}개 → {a.out}', flush=True)


if __name__ == '__main__':
    main()
