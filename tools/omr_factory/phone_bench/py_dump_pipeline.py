#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""포팅 2번 — 캐논 실물 10장의 파이썬 단계별 중간 결과 덤프 (다트 대조 기준).

    python py_dump_pipeline.py            # → C:/Users/user/omr_phone_bench_assets/pipe

사진마다 (보정 켬/끔 두 경로):
  - 검출 줄 수, 줄 박스 [x0, top, x1, bot] + (cy, gap) 원본 좌표
  - 줄별 최종 입력 텐서(normalize_photo 결과)를 PNG(uint8=round(a*255)) 로
  - 줄별 파이썬 ORT(FP32) 디코드 id 열
  - 켬/끔 자동선택 결과(신뢰도·비어있지 않은 보표 수·선택)
사진 원본(jpg)도 함께 복사한다. 모두 저장소 밖(커밋 금지).
"""
import json
import os
import shutil
import sys

sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
import numpy as np
import torch
from PIL import Image

import photo_prep
import prep
from model import greedy_decode
from ort_model import OrtCRNN

OUT = r'C:\Users\user\omr_phone_bench_assets\pipe'
EXP_STAVES = 14          # 캐논 렌더 기준 보표 수 (evaluate_duet line_truth)
# 품질 분포 고르게: 상(4)·중(3)·하(3) — 3c4 캐논 per_photo 기준 수동 선정
PHOTOS = ['20260921_190137.jpg', '20260921_190154.jpg', '20260921_190144.jpg',
          '20260921_190103.jpg', '20260921_190122.jpg', '20260921_190220.jpg',
          '20260921_190222.jpg', '20260921_190104.jpg', '20260921_190153(0).jpg',
          '20260921_190158.jpg']
SRC = 'C:/Users/user/omr_photo_canon/'

os.makedirs(OUT, exist_ok=True)
ort = OrtCRNN('C:/Users/user/omr_export/omr_crnn_fp32.onnx')

manifest = []
for ph in PHOTOS:
    stem = os.path.splitext(ph)[0].replace('(', '_').replace(')', '')
    d = os.path.join(OUT, stem)
    os.makedirs(d, exist_ok=True)
    shutil.copy(SRC + ph, os.path.join(d, 'photo.jpg'))
    entry = dict(photo=ph, stem=stem, sides={})
    for side in ('on', 'off'):
        res = photo_prep.extract_lines(SRC + ph, correct=(side == 'on'),
                                       with_pos=True)
        lines = []
        confs = []
        frames_n = []
        nonempty = 0
        for li, (crop, cy, gap) in enumerate(res):
            a = prep.normalize_photo(crop, gap_hint=gap)
            png = f'{side}_l{li:02d}.png'
            Image.fromarray(np.clip(np.round(a * 255), 0, 255)
                            .astype(np.uint8)).save(os.path.join(d, png))
            x = torch.from_numpy(np.ascontiguousarray(a, np.float32))[None, None]
            lg = ort(x)
            T = a.shape[1] // 4
            ids = greedy_decode(lg, torch.tensor([T]))[0]
            pr = torch.softmax(lg[0, :T], dim=-1).max(dim=-1).values
            confs.append(float(pr.mean()))
            frames_n.append(T)
            nonempty += bool(ids)
            # 박스: extract_lines 는 crop 만 주므로 좌표는 crop 크기+cy·gap 로
            # 기록(다트와 같은 정의: top/bot/x0/x1 은 다트가 자체 계산 후
            # cy·gap·크롭 크기와 대조).
            lines.append(dict(tensor=png, w=int(a.shape[1]),
                              crop_w=crop.size[0], crop_h=crop.size[1],
                              cy=round(float(cy), 2), gap=round(float(gap), 3),
                              ids=ids, conf=round(confs[-1], 5)))
        wc = (sum(c * f for c, f in zip(confs, frames_n))
              / max(1, sum(frames_n))) if frames_n else 0.0
        entry['sides'][side] = dict(n=len(res), nonempty=nonempty,
                                    conf=round(wc, 5), lines=lines)
    on, off = entry['sides']['on'], entry['sides']['off']
    if abs(on['conf'] - off['conf']) > 0.002:
        pick = 'on' if on['conf'] >= off['conf'] else 'off'
    else:
        do = abs(on['nonempty'] - EXP_STAVES)
        df = abs(off['nonempty'] - EXP_STAVES)
        pick = 'on' if (do, -on['conf']) <= (df, -off['conf']) else 'off'
    entry['pick'] = pick
    manifest.append(entry)
    print(ph, 'on', on['n'], 'off', off['n'], 'pick', pick, flush=True)

json.dump(dict(exp_staves=EXP_STAVES, photos=manifest),
          open(os.path.join(OUT, 'pipe_manifest.json'), 'w'),
          ensure_ascii=False, indent=1)
tot = sum(os.path.getsize(os.path.join(r, f))
          for r, _d, fs in os.walk(OUT) for f in fs)
print('완료 → %s (%.1fMB)' % (OUT, tot / 2**20))
