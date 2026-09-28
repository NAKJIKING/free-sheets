# -*- coding: utf-8 -*-
"""폰 벤치용 30줄 세트 — 전처리 완료 텐서(.bin float32 LE) + 정답 디코드 + PC 기준."""
import json
import os
import sys
import time

sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
import numpy as np
import torch
from PIL import Image

import photo_prep
import prep
from model import greedy_decode
from ort_model import OrtCRNN

OUT = r'C:\Users\user\omr_phone_bench_assets'
os.makedirs(OUT + r'\lines', exist_ok=True)
ort = OrtCRNN('C:/Users/user/omr_export/omr_crnn_fp32.onnx')

items = []

# ① 엘리제 20줄 (관문1 코퍼스 시험 분할, 폭 고르게)
rows = []
for ln in open('C:/Users/user/omr_lines/index.jsonl', encoding='utf-8'):
    r = json.loads(ln)
    if r['song'] == 'original:elise' and r['split'] == 'test':
        rows.append(r)
rows.sort(key=lambda r: r['w'])
step = max(1, len(rows) // 20)
for r in rows[::step][:20]:
    with Image.open('C:/Users/user/omr_lines/' + r['cache']) as im:
        a = np.asarray(im.convert('L'), dtype=np.float32) / 255.0
    items.append(('elise', a))

# ② 캐논 실물 10줄 (성적 좋은 사진 2장, 보정 켬)
for ph in ('20260921_190137.jpg', '20260921_190154.jpg'):
    res = photo_prep.extract_lines('C:/Users/user/omr_photo_canon/' + ph,
                                   correct=True, with_pos=True)
    for c, _y, g in res[:5]:
        items.append(('canon', prep.normalize_photo(c, gap_hint=g)))
items = items[:30]

meta = []
lat = []
for i, (src, a) in enumerate(items):
    a = np.ascontiguousarray(a, dtype=np.float32)
    h, w = a.shape
    fn = f'line_{i:02d}.bin'
    a.tofile(os.path.join(OUT, 'lines', fn))
    x = torch.from_numpy(a)[None, None]
    t0 = time.perf_counter()
    lg = ort(x)
    dt = (time.perf_counter() - t0) * 1000
    lat.append(dt)
    ref = greedy_decode(lg, torch.tensor([w // 4]))[0]
    meta.append(dict(file=fn, src=src, h=h, w=w, ref=ref))
    print(i, src, h, w, len(ref), f'{dt:.0f}ms')

# PC 기준(준비운전 3회 제외, 2회전 평균)
lat2 = []
for _ in range(2):
    for i, (src, a) in enumerate(items):
        x = torch.from_numpy(np.ascontiguousarray(a, np.float32))[None, None]
        t0 = time.perf_counter()
        ort(x)
        lat2.append((time.perf_counter() - t0) * 1000)
lat2 = sorted(lat2[3:])
pc = dict(mean_ms=round(sum(lat2) / len(lat2), 1),
          p50_ms=round(lat2[len(lat2) // 2], 1), max_ms=round(lat2[-1], 1))
json.dump(dict(lines=meta, pc_ort_fp32=pc),
          open(os.path.join(OUT, 'meta.json'), 'w'), ensure_ascii=False)
tot = sum(os.path.getsize(os.path.join(OUT, 'lines', m['file'])) for m in meta)
print('lines', len(meta), 'bin 합계 %.1fMB' % (tot / 2**20), 'PC 기준', pc)
