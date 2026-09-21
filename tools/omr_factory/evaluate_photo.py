#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관문 2 자체 평가 — 사진(모의/실물) 끝단 파이프라인 NER.

    python tools/omr_factory/evaluate_photo.py \
        --photos C:/Users/me/omr_photo_mock --model C:/Users/me/omr_model_g2 \
        --out C:/Users/me/omr_gate2_mock

각 페이지: photo_prep.extract_lines → prep.normalize_photo → 모델 → 토큰열.
검출 줄과 정답 줄 수가 다를 수 있으므로 **줄 정렬을 DP(니들만-분치)로**
맞춘다 — 놓친 정답 줄의 음표는 전부 오류로, 유령 검출 줄의 음표는 전부
삽입 오류로 센다. 검출 실패를 숨기지 않는 정직한 채점.

판정(관문 2, 모의): 음표 NER ≤ 10%.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as D
import photo_prep
import prep
from model import CRNN, greedy_decode
from train import edit


def align_lines(refs, hyps):
    """줄 단위 DP 정렬 — [(ref_i|None, hyp_j|None)] 반환.
    비용: 짝 = 음표 편집거리, 정답 줄 누락 = |ref|, 유령 줄 = |hyp|."""
    n, m = len(refs), len(hyps)
    INF = 10 ** 9
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            c = dp[i][j]
            if c >= INF:
                continue
            if i < n and j < m:
                d = c + edit(refs[i], hyps[j])
                if d < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = d
            if i < n:
                d = c + max(1, len(refs[i]))
                if d < dp[i + 1][j]:
                    dp[i + 1][j] = d
            if j < m:
                d = c + max(1, len(hyps[j]))
                if d < dp[i][j + 1]:
                    dp[i][j + 1] = d
    # 역추적
    out, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and \
                dp[i][j] == dp[i - 1][j - 1] + edit(refs[i - 1], hyps[j - 1]):
            out.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + max(1, len(refs[i - 1])):
            out.append((i - 1, None))
            i -= 1
        else:
            out.append((None, j - 1))
            j -= 1
    return list(reversed(out))


@torch.no_grad()
def decode_crops(net, crops, dev, max_w=2600, batch=8):
    """정규화된 (160, W) 배열들 → 토큰 인덱스열 목록."""
    out = []
    for k in range(0, len(crops), batch):
        chunk = [c[:, :max_w] for c in crops[k:k + batch]]
        W = max(c.shape[1] for c in chunk)
        x = torch.zeros(len(chunk), 1, prep.HEIGHT, W)
        for i, c in enumerate(chunk):
            x[i, 0, :, :c.shape[1]] = torch.from_numpy(c)
        xl = torch.tensor([c.shape[1] for c in chunk])
        x = x.to(dev)
        with torch.autocast('cuda', dtype=torch.bfloat16,
                            enabled=dev.type == 'cuda'):
            lg = net(x).float()
        out += greedy_decode(lg, net.out_len(xl))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--photos', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--ckpt', default='best.pt')
    ap.add_argument('--gate', type=float, default=0.10)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    vocab = D.Vocab.load(os.path.join(a.model, 'vocab.json'))
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    st = torch.load(os.path.join(a.model, a.ckpt), map_location=dev)
    net = CRNN(len(vocab)).to(dev)
    net.load_state_dict(st['net'])
    net.eval()
    print(f"체크포인트 에폭 {st.get('epoch')} (렌더 검증NER {st.get('ner')})")

    pages = sorted(glob.glob(os.path.join(a.photos, 'page_*.json')))
    print(f'페이지 {len(pages)}장 평가', flush=True)
    ne = nt = 0
    miss = ghost = lines_tot = det_tot = 0
    per_page = []
    for pj in pages:
        meta = json.load(open(pj, encoding='utf-8'))
        # 정답: 음표 인덱스열(쉼표 제외) — 어휘 밖은 −1(항상 오류)
        refs = []
        for ln in meta['lines']:
            y = vocab.encode([tuple(t) for t in ln['tokens']], unk=-1)
            refs.append([k for k in y if not vocab.is_rest(k)])
        crops = photo_prep.load_photo_lines(
            os.path.join(a.photos, meta['page']))
        hyps_all = decode_crops(net, crops, dev) if crops else []
        hyps = [[k for k in h if not vocab.is_rest(k)] for h in hyps_all]
        pe = pt = 0
        pairs = align_lines(refs, hyps)
        for ri, hj in pairs:
            if ri is None:
                ghost += 1
                pe += len(hyps[hj])
            elif hj is None:
                miss += 1
                pe += len(refs[ri])
                pt += len(refs[ri])
            else:
                pe += edit(refs[ri], hyps[hj])
                pt += len(refs[ri])
        ne += pe
        nt += pt
        lines_tot += len(refs)
        det_tot += len(hyps)
        per_page.append(dict(page=meta['page'], lines=len(refs),
                             detected=len(hyps), err=pe, notes=pt,
                             ner=pe / max(1, pt)))
    ner = ne / max(1, nt)
    print()
    print(f'■ 사진 음표 NER     {ner:.4%}   ({ne} / {nt}음)')
    print(f'■ 줄 검출          정답 {lines_tot} / 검출 {det_tot} '
          f'(누락 {miss}, 유령 {ghost})')
    print(f'■ 관문 2 모의 (NER ≤ {a.gate:.0%}) '
          f'{"통과" if ner <= a.gate else "미달"}')
    worst = sorted(per_page, key=lambda p: -p['ner'])[:10]
    print('\n오류율 높은 페이지 10:')
    for p in worst:
        print(f"  {p['ner']:7.2%}  {p['page']} (검출 {p['detected']}/{p['lines']})")
    rep = dict(photos=a.photos, pages=len(pages), ner_notes=ner,
               err=ne, notes=nt, lines=lines_tot, detected=det_tot,
               missed_lines=miss, ghost_lines=ghost,
               gate2_mock_pass=bool(ner <= a.gate),
               ckpt_epoch=st.get('epoch'), per_page=per_page)
    json.dump(rep, open(os.path.join(a.out, 'gate2_mock.json'), 'w',
                        encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n보고서 → {os.path.join(a.out, 'gate2_mock.json')}")


if __name__ == '__main__':
    main()
