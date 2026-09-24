#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관문 3b 판정 — 구조 토큰(도돌이·볼타) 정확도 + 전개 미디 일치.

시험 분할에서 구조 토큰이 든 줄을 깨끗한 렌더로 디코드해:
  ① 구조 토큰 정확도 — 줄의 구조열(마커 순서열)이 정답과 정확히 일치하는
     줄 비율 + 토큰 정밀도/재현율. 기준 ≥95%.
  ② 전개 미디 일치 — unfold_tokens 로 정답·인식 둘 다 전개해 (음고,길이)
     열이 일치하면 그 줄의 '연주'가 맞다. 곡 단위로 묶어(구조 줄 전부 일치)
     일치 곡 비율. 기준 ≥90%. (반복을 잘못 읽으면 연주 길이가 통째로 틀린다)

    python tools/omr_factory/eval_structure.py --data C:/Users/me/omr_lines3b \
        --model C:/Users/me/omr_model_3b2 --out C:/Users/me/omr_gate3b_struct
"""
import argparse
import collections
import json
import os
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as D
from evaluate_photo import decode_crops
from lib_lines import unfold_tokens
from model import CRNN
from train import edit

STRUCT = {-1, -2, -3, -4}


def struct_seq(toks):
    return [p for p, _d, _t in toks if p in STRUCT]


def perf_seq(toks):
    """전개 후 (음고,길이) 연주열 — 붙임줄 병합."""
    out = []
    carry = False
    for p, d, tie in unfold_tokens([list(t) for t in toks]):
        if p in STRUCT:
            continue
        if carry and out and out[-1][0] == p:
            out[-1] = (p, out[-1][1] + d)
        elif p >= 0:
            out.append((p, d))
        carry = p > 0 and bool(tie)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--ckpt', default='best.pt')
    ap.add_argument('--out', required=True)
    ap.add_argument('--batch', type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    vocab = D.Vocab.load(os.path.join(a.model, 'vocab.json'))
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    st = torch.load(os.path.join(a.model, a.ckpt), map_location=dev)
    net = CRNN(len(vocab)).to(dev)
    net.load_state_dict(st['net'])
    net.eval()

    rows = []
    for ln in open(os.path.join(a.data, 'index.jsonl'), encoding='utf-8'):
        r = json.loads(ln)
        if r['split'] == 'test' and any(t[0] < 0 for t in r['tokens']):
            rows.append(r)
    print(f'구조 토큰 포함 시험 줄 {len(rows)}개', flush=True)

    line_ok = 0
    tp = fp = fn = 0
    perf_ok_lines = 0
    song_lines = collections.defaultdict(list)
    for k in range(0, len(rows), a.batch):
        chunk = rows[k:k + a.batch]
        crops = []
        for r in chunk:
            with Image.open(os.path.join(a.data, r['cache'])) as im:
                crops.append(np.asarray(im.convert('L'),
                                        dtype=np.float32) / 255.0)
        hyps = decode_crops(net, crops, dev)
        for r, h in zip(chunk, hyps):
            ht = [list(vocab.itos[i]) for i in h if i > 0]
            rt = [list(t) for t in r['tokens']]
            ss_r, ss_h = struct_seq(rt), struct_seq(ht)
            line_ok += (ss_r == ss_h)
            # 토큰 P/R — 순서 정렬 없이 다중집합 교집합(구조 토큰은 희소)
            cr, ch = collections.Counter(ss_r), collections.Counter(ss_h)
            inter = sum((cr & ch).values())
            tp += inter
            fp += sum(ch.values()) - inter
            fn += sum(cr.values()) - inter
            pok = perf_seq(rt) == perf_seq(ht)
            perf_ok_lines += pok
            song_lines[r['song']].append(pok)
        if (k // a.batch) % 40 == 0:
            print(f'  {k + len(chunk)}/{len(rows)}', flush=True)

    songs = len(song_lines)
    song_ok = sum(1 for v in song_lines.values() if all(v))
    res = dict(
        lines=len(rows),
        struct_line_acc=round(line_ok / max(1, len(rows)), 4),
        struct_precision=round(tp / max(1, tp + fp), 4),
        struct_recall=round(tp / max(1, tp + fn), 4),
        perf_line_acc=round(perf_ok_lines / max(1, len(rows)), 4),
        songs=songs, songs_ok=song_ok,
        perf_song_acc=round(song_ok / max(1, songs), 4),
        pass_struct=line_ok / max(1, len(rows)) >= 0.95,
        pass_perf=song_ok / max(1, songs) >= 0.90,
        ckpt_epoch=st.get('epoch'))
    json.dump(res, open(os.path.join(a.out, 'gate3b.json'), 'w',
                        encoding='utf-8'), indent=1)
    print(json.dumps(res, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
