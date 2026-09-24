#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실물 촬영본 → 실물 학습쌍 코퍼스 (관문 2 실물 간극 해소, 2026-09-24).

인쇄 팩(gen_print_sheets)의 촬영 사진을 라벨 있는 학습 데이터로 바꾼다:
  1) 깨끗한 렌더(01..15.png)를 모델로 읽어 **줄별 정답** 역산
     (evaluate_duet.build_line_truth 방식, 단선율이라 성부 없음)
  2) 사진마다 보정 켬/끔 둘 다 추출·디코드 → 15곡 전역 편집거리로 자동 매칭
     (정답이 있으므로 켬/끔도 실제 NER 로 고른다 — 학습 데이터 선별은 정당)
  3) 크롭 수 == 줄 수면 순서 1:1, 아니면 줄 단위 DP(align_lines)로 짝짓기
  4) 정규화 크롭 PNG + index.jsonl 저장 — 코퍼스 형식(real:true 표시,
     곡 단위 train/val 분할: 검증 시트는 통째로 val)

    python tools/omr_factory/real_pack.py --photos C:/Users/me/omr_real_shots \
        --print-dir C:/Users/me/omr_print --model C:/Users/me/omr_model_ch2 \
        --out C:/Users/me/omr_real_lines --val-sheets 04,07,14

출력: OUT/cache/<사진>/l##.png + index.jsonl + report.json
주의: 이미지 출력물 커밋 금지. 매칭 실패 사진은 report 와 stdout 에 남긴다.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as D
import photo_prep
import prep
from evaluate_duet import decode_conf, infix_edit_span
from evaluate_photo import align_lines, decode_crops
from model import CRNN
from train import edit


def full_toks(vocab, hyp):
    """디코드 인덱스열 → (p,d,tie) 튜플열 — 쉼표 포함(라벨용)."""
    return [tuple(vocab.itos[k]) for k in hyp if k > 0]


def line_truths(png, tokens, net, vocab, dev):
    """깨끗한 렌더 → 줄별 정답 구간(전체 토큰, 쉼표·붙임줄 포함)."""
    crops = photo_prep.extract_lines(png, correct=False)
    norm = [prep.normalize_photo(c) for c in crops]
    decs = [full_toks(vocab, h) for h in decode_crops(net, norm, dev)]
    T = [tuple(t) for t in tokens]
    out, pos = [], 0
    for i, dec in enumerate(decs):
        if i + 1 == len(decs):
            end = len(T)
        else:
            _e, _s, t = infix_edit_span(dec, T[pos:])
            end = pos + t
        end = max(end, pos)
        out.append(T[pos:end])
        pos = end
    assert pos == len(T), f'분할 불일치 {pos}/{len(T)}'
    drift = sum(edit(d, list(t)) for d, t in zip(decs, out))
    return out, drift / max(1, len(T))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--photos', required=True)
    ap.add_argument('--print-dir', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--ckpt', default='best.pt')
    ap.add_argument('--out', required=True)
    ap.add_argument('--val-sheets', default='04,07,14')
    ap.add_argument('--match-max', type=float, default=0.75,
                    help='이보다 NER 나쁘면 매칭 실패로 보고')
    a = ap.parse_args()
    val_sheets = set(a.val_sheets.split(','))
    os.makedirs(os.path.join(a.out, 'cache'), exist_ok=True)

    truth = json.load(open(os.path.join(a.print_dir, 'truth.json'),
                           encoding='utf-8'))
    vocab = D.Vocab.load(os.path.join(a.model, 'vocab.json'))
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    st = torch.load(os.path.join(a.model, a.ckpt), map_location=dev)
    net = CRNN(len(vocab)).to(dev)
    net.load_state_dict(st['net'])
    net.eval()

    lt, flat = {}, {}
    for sid, tr in sorted(truth.items()):
        png = os.path.join(a.print_dir, sid + '.png')
        lt[sid], drift = line_truths(png, tr['tokens'], net, vocab, dev)
        flat[sid] = [tuple(t) for t in tr['tokens']]
        mark = ' ⚠드리프트' if drift > 0.03 else ''
        print(f'  {sid}: 줄 {len(lt[sid])} 정답 역산 (렌더 오차 {drift:.1%}{mark})',
              flush=True)

    photos = sorted(glob.glob(os.path.join(a.photos, '*.jpg')))
    print(f'사진 {len(photos)}장 매칭·추출', flush=True)
    idx = open(os.path.join(a.out, 'index.jsonl'), 'w', encoding='utf-8')
    report = dict(matched=[], unmatched=[], sheets={})
    n_train = n_val = 0
    from PIL import ImageOps
    for ph in photos:
        stem = os.path.splitext(os.path.basename(ph))[0]
        with Image.open(ph) as im:
            base = ImageOps.exif_transpose(im).convert('L')
        # 방향 후보 4종 — 수직 하향 촬영은 자이로가 방향을 못 잡아 EXIF 가
        # 제멋대로다(실측: ori=1/3 배치 29장 전멸). 보표가 잡히는 방향만
        # 남기고(0°/180° 모호성은 매칭 NER 가 가른다) 디코드한다.
        cands = []
        for rot in (0, 90, 180, 270):
            img = base if rot == 0 else base.rotate(rot, expand=True)
            res = photo_prep.extract_lines(img, correct=False, with_pos=True)
            if len(res) >= 3:
                cands.append((rot, img, res))
        best = None                     # (ner, sid, cor, rot, norm, decs)
        for rot, img, res_off in cands:
            for cor in (False, True):
                res = res_off if not cor else \
                    photo_prep.extract_lines(img, correct=True, with_pos=True)
                norm = [prep.normalize_photo(c, gap_hint=g)
                        for c, _y, g in res]
                if not norm:
                    continue
                hyps, _c, _f = decode_conf(net, norm, dev)
                decs = [full_toks(vocab, h) for h in hyps]
                cat = [t for d in decs for t in d]
                if not cat:
                    continue
                for sid, T in flat.items():
                    ner = edit(cat, T) / max(1, len(T))
                    if best is None or ner < best[0]:
                        best = (ner, sid, cor, rot, norm, decs)
        if best is None or best[0] > a.match_max:
            why = '추출 실패(전 방향 줄 0개)' if best is None \
                else f'최적 NER {best[0]:.0%}'
            report['unmatched'].append(dict(photo=stem + '.jpg', why=why))
            print(f'  ✗ {stem}: 매칭 실패 — {why}', flush=True)
            continue
        ner, sid, cor, rot, norm, decs = best
        refs = [list(t) for t in lt[sid]]
        if len(norm) == len(refs):
            pairs = [(i, i) for i in range(len(refs))]
        else:
            pairs = [(i, j) for i, j in align_lines(refs, decs)
                     if i is not None and j is not None]
        d = os.path.join(a.out, 'cache', stem)
        os.makedirs(d, exist_ok=True)
        split = 'val' if sid in val_sheets else 'train'
        kept = 0
        for i, j in pairs:
            if not refs[i]:
                continue
            g = np.clip(norm[j] * 255, 0, 255).astype(np.uint8)
            name = f'l{i:02d}.png'
            Image.fromarray(g).save(os.path.join(d, name))
            row = dict(song=f'real:{sid}', var=stem, chunk=i, shift=0,
                       split=split, cache=f'cache/{stem}/{name}',
                       w=int(g.shape[1]),
                       tokens=[list(t) for t in lt[sid][i]], real=True)
            idx.write(json.dumps(row, ensure_ascii=False) + '\n')
            kept += 1
        if split == 'val':
            n_val += kept
        else:
            n_train += kept
        report['matched'].append(dict(
            photo=stem + '.jpg', sheet=sid, correct=cor, rot=rot,
            ner=round(ner, 3), crops=len(norm), truth_lines=len(refs),
            kept=kept))
        report['sheets'].setdefault(sid, 0)
        report['sheets'][sid] += 1
        print(f'  ✓ {stem} → {sid} ({"켬" if cor else "끔"}, rot {rot}°, '
              f'NER {ner:.1%}, 크롭 {len(norm)}/{len(refs)}줄, 채택 {kept}) '
              f'[{split}]', flush=True)
    idx.close()
    json.dump(report, open(os.path.join(a.out, 'report.json'), 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"끝: 매칭 {len(report['matched'])}/{len(photos)}장, "
          f'학습 {n_train}줄 / 검증 {n_val}줄 → {a.out}', flush=True)
    if report['unmatched']:
        print('매칭 실패:', ', '.join(u['photo'] for u in report['unmatched']),
              flush=True)


if __name__ == '__main__':
    main()
