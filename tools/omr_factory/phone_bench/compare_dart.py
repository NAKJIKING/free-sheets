#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""포팅 3번 — 다트 파이프라인 출력을 파이썬 기준과 대조·채점.

    python compare_dart.py

비교: 줄 수 일치 / cy·gap·크롭 크기 오차 / 텐서 평균절대차 / 디코드 일치.
판정: 10장 전체 NER(자동선택 경로) — 다트 ≤ 파이썬 +1%p.
"""
import json
import os
import sys

sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
import numpy as np
import torch
from PIL import Image

import dataset as D
from evaluate_duet import build_line_truth
from evaluate_photo import align_lines
from model import greedy_decode
from ort_model import OrtCRNN
from train import edit

PIPE = r'C:\Users\user\omr_phone_bench_assets\pipe'
DART = r'C:\Users\user\omr_phone_bench_assets\dart_out'
EXP = 14

vocab = D.Vocab.load('C:/Users/user/omr_model_3c4/vocab.json')
ort = OrtCRNN('C:/Users/user/omr_export/omr_crnn_fp32.onnx')
truth = json.load(open('C:/Users/user/omr_dense/truth_canon.json',
                       encoding='utf-8'))
voices = [[(p, d) for p, d, _t in [tuple(t) for t in v] if p > 0]
          for v in truth['voices']]
line_truth = build_line_truth('C:/Users/user/omr_dense/캐논_플루트.png',
                              ort, vocab, 'cpu', voices)
refs = [seq for _vi, seq in line_truth]

pym = json.load(open(os.path.join(PIPE, 'pipe_manifest.json'),
                     encoding='utf-8'))
dam = json.load(open(os.path.join(DART, 'dart_manifest.json'),
                     encoding='utf-8'))
dmap = {p['stem']: p for p in dam['photos']}


def dec(a):
    x = torch.from_numpy(np.ascontiguousarray(a, np.float32))[None, None]
    return greedy_decode(ort(x), torch.tensor([a.shape[1] // 4]))[0]


def notes_of(ids):
    return [(p, d) for p, d, _t in (tuple(vocab.itos[k]) for k in ids)
            if p > 0]


def score(hyp_notes):
    pairs = align_lines(refs, hyp_notes)
    pe = pt = 0
    for ri, hj in pairs:
        if ri is None:
            pe += len(hyp_notes[hj])
        elif hj is None:
            pe += len(refs[ri])
            pt += len(refs[ri])
        else:
            pe += edit(refs[ri], hyp_notes[hj])
            pt += len(refs[ri])
    return pe, pt


tot = dict(py_pe=0, py_pt=0, da_pe=0, da_pt=0)
nmatch = 0
decmatch = decall = 0
tdiffs, cydiffs, gapdiffs = [], [], []
for ph in pym['photos']:
    stem = ph['stem']
    da = dmap[stem]
    row = [stem]
    da_side_data = {}
    for side in ('on', 'off'):
        pl = ph['sides'][side]
        dl = da['sides'][side]
        same_n = pl['n'] == dl['n']
        nmatch += same_n
        ids_list, confs, frames = [], [], []
        for li, dline in enumerate(dl['lines']):
            f = os.path.join(DART, stem,
                             f"{side}_l{li:02d}.bin")
            a = np.fromfile(f, dtype=np.float32).reshape(160, dline['w'])
            ids = dec(a)
            ids_list.append(ids)
            x = torch.from_numpy(a)[None, None]
            lg = ort(x)
            T = a.shape[1] // 4
            pr = torch.softmax(lg[0, :T], -1).max(-1).values
            confs.append(float(pr.mean()))
            frames.append(T)
            if li < pl['n']:
                pline = pl['lines'][li]
                cydiffs.append(abs(dline['cy'] - pline['cy']))
                gapdiffs.append(abs(dline['gap'] - pline['gap']))
                pa = np.asarray(Image.open(os.path.join(
                    PIPE, stem, pline['tensor'])), dtype=np.float32) / 255.0
                wmin = min(pa.shape[1], a.shape[1])
                tdiffs.append(float(np.abs(pa[:, :wmin] - a[:, :wmin]).mean()))
                decall += 1
                decmatch += (ids == pline['ids'])
        wc = (sum(c * f_ for c, f_ in zip(confs, frames))
              / max(1, sum(frames))) if frames else 0.0
        nonempty = sum(1 for i in ids_list if i)
        da_side_data[side] = dict(ids=ids_list, conf=wc, nonempty=nonempty)
        row.append(f'{side}:{pl["n"]}/{dl["n"]}{"=" if same_n else "!"}')
    # 자동선택 (다트 출력 기준)
    on, off = da_side_data['on'], da_side_data['off']
    if abs(on['conf'] - off['conf']) > 0.002:
        pick = 'on' if on['conf'] >= off['conf'] else 'off'
    else:
        do_, df_ = abs(on['nonempty'] - EXP), abs(off['nonempty'] - EXP)
        pick = 'on' if (do_, -on['conf']) <= (df_, -off['conf']) else 'off'
    da_notes = [notes_of(i) for i in da_side_data[pick]['ids'] if i]
    pe, pt = score(da_notes)
    tot['da_pe'] += pe
    tot['da_pt'] += pt
    py_pick = ph['pick']
    py_notes = [notes_of(l['ids']) for l in ph['sides'][py_pick]['lines']
                if l['ids']]
    pe2, pt2 = score(py_notes)
    tot['py_pe'] += pe2
    tot['py_pt'] += pt2
    row.append(f'pick {py_pick}/{pick}{"=" if pick == py_pick else "!"}')
    row.append('ner py %.3f da %.3f' % (pe2 / max(1, pt2), pe / max(1, pt)))
    print(' '.join(row), flush=True)

py_ner = tot['py_pe'] / max(1, tot['py_pt'])
da_ner = tot['da_pe'] / max(1, tot['da_pt'])
print()
print('줄 수 일치  %d/20 (사진×켬끔)' % nmatch)
print('cy 오차     평균 %.2f / 최대 %.2f px' % (np.mean(cydiffs), np.max(cydiffs)))
print('gap 오차    평균 %.3f / 최대 %.3f px' % (np.mean(gapdiffs), np.max(gapdiffs)))
print('텐서 |차|   평균 %.4f / 최대줄 %.4f' % (np.mean(tdiffs), np.max(tdiffs)))
print('디코드 일치 %d/%d' % (decmatch, decall))
print('NER 파이썬 %.4f%%  다트 %.4f%%  차 %+.3f%%p → %s' %
      (py_ner * 100, da_ner * 100, (da_ner - py_ner) * 100,
       '통과' if (da_ner - py_ner) <= 0.01 else '미달'))
