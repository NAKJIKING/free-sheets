#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관문 3c 판정 — 빠르기표(♩=숫자)·셈여림(f/p/mf/cresc) 인식.

시험 분할에서 3c 토큰(빠르기 −5, 셈여림 −6..−10)이 든 줄을 깨끗한 렌더로
디코드해:
  ① 빠르기 숫자 정확도 — 정답에 빠르기 토큰이 있는 줄에서, 예측의 빠르기
     토큰열(값 포함)이 정답과 정확히 일치하는 줄 비율. 기준 ≥95%.
     (숫자가 하나라도 다르면, 안 읽거나 헛읽어도 그 줄은 오답)
  ② 셈여림 유무 정확도 — 정답에 셈여림이 있는 줄에서, 예측의 셈여림
     **종류 집합**(f/p/mf/cresc)이 정답과 일치하는 줄 비율. 기준 ≥90%.
     (로드맵의 '유무'보다 엄격한 종류 일치로 잰다 — 이게 통과하면 유무는
     자동으로 통과. 참고로 둘 다 보고한다.)
  참고 지표: 셈여림 없는 줄에서의 오검출(유령) 비율, 종류별 정밀/재현.

    python tools/omr_factory/eval_3c.py --data C:/Users/me/omr_lines3c \
        --model C:/Users/me/omr_model_3c --out C:/Users/me/omr_gate3c
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
from model import CRNN

TEMPO = -5
DYN_NAME = {-6: 'f', -7: 'p', -8: 'mf', -9: 'cresc'}   # −10(끝)은 −9 에 붙는 짝


def tempo_seq(toks):
    return [d for p, d, _t in toks if p == TEMPO]


def dyn_kinds(toks):
    """줄에 나타난 셈여림 종류 집합 — cresc 는 시작(−9) 기준."""
    return {DYN_NAME[p] for p, _d, _t in toks if p in DYN_NAME}


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
        if r['split'] == 'test' and any(t[0] <= -5 for t in r['tokens']):
            rows.append(r)
    print(f'3c 토큰 포함 시험 줄 {len(rows)}개', flush=True)

    tempo_lines = tempo_ok = 0
    dyn_lines = dyn_kind_ok = dyn_presence_ok = 0
    clean_dyn_lines = dyn_ghost_lines = 0          # 셈여림 없는 줄의 오검출
    clean_tempo_lines = tempo_ghost_lines = 0      # 빠르기 없는 줄의 오검출
    kind_tp = collections.Counter()
    kind_fp = collections.Counter()
    kind_fn = collections.Counter()
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
            # ① 빠르기
            tr_, th_ = tempo_seq(rt), tempo_seq(ht)
            if tr_:
                tempo_lines += 1
                tempo_ok += (tr_ == th_)
            else:
                clean_tempo_lines += 1
                tempo_ghost_lines += bool(th_)
            # ② 셈여림
            kr, kh = dyn_kinds(rt), dyn_kinds(ht)
            if kr:
                dyn_lines += 1
                dyn_kind_ok += (kr == kh)
                dyn_presence_ok += bool(kh)
            else:
                clean_dyn_lines += 1
                dyn_ghost_lines += bool(kh)
            for kind in kr | kh:
                if kind in kr and kind in kh:
                    kind_tp[kind] += 1
                elif kind in kh:
                    kind_fp[kind] += 1
                else:
                    kind_fn[kind] += 1
        if (k // a.batch) % 40 == 0:
            print(f'  {k + len(chunk)}/{len(rows)}', flush=True)

    tempo_acc = tempo_ok / max(1, tempo_lines)
    dyn_kind_acc = dyn_kind_ok / max(1, dyn_lines)
    dyn_presence_acc = dyn_presence_ok / max(1, dyn_lines)
    per_kind = {kind: dict(
        precision=round(kind_tp[kind] / max(1, kind_tp[kind] + kind_fp[kind]), 4),
        recall=round(kind_tp[kind] / max(1, kind_tp[kind] + kind_fn[kind]), 4))
        for kind in sorted(set(kind_tp) | set(kind_fp) | set(kind_fn))}
    res = dict(
        lines=len(rows),
        tempo_lines=tempo_lines,
        tempo_num_acc=round(tempo_acc, 4),
        tempo_ghost=round(tempo_ghost_lines / max(1, clean_tempo_lines), 4),
        dyn_lines=dyn_lines,
        dyn_kind_acc=round(dyn_kind_acc, 4),
        dyn_presence_acc=round(dyn_presence_acc, 4),
        dyn_ghost=round(dyn_ghost_lines / max(1, clean_dyn_lines), 4),
        per_kind=per_kind,
        pass_tempo=tempo_acc >= 0.95,
        pass_dyn=dyn_kind_acc >= 0.90,
        ckpt_epoch=st.get('epoch'))
    json.dump(res, open(os.path.join(a.out, 'gate3c.json'), 'w',
                        encoding='utf-8'), indent=1)
    print(json.dumps(res, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
