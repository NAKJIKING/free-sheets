#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""다트 정합 시험용 기준값 — 캐논 53 + 비캐논 43장 (ghost_diag.json 재사용).

    python make_fixture.py   # → C:/Users/user/omr_core_fixture/fixture.json

사진마다 켬/끔 줄(id·신뢰도·프레임·폭·sq·cy·gap)과 파이썬 기대값:
조기 결정·선택(v4), 가짜 줄(v5), 보표 쌍 신호, 연주 음표·SMF(bpm 90, base64).
또 dart_out_v5 텐서(10장×켬끔)의 staffQ·음표머리 통계 기대값.
SMF 는 셈여림이 없을 때 evaluate.write_midi(unfold(...)) 와 바이트 일치를
여기서 전수 검사한다(기준 구현 자체의 정합). 출력은 저장소 밖.
"""
import base64
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory\phone_bench')
import ref_score as R  # noqa: E402
from ghost_diag import OUT as GD, MODEL, staff_q  # noqa: E402
from poly_signals import head_stats, paired  # noqa: E402

OUT = 'C:/Users/user/omr_core_fixture'
DART_OUT = 'C:/Users/user/omr_phone_bench_assets/dart_out_v5'
EARLY_CONF, EARLY_DIFF, TIE = 0.9975, 2, 0.002


def side_conf(lines):
    fr = sum(l['frames'] for l in lines)
    return sum(l['conf'] * l['frames'] for l in lines) / max(1, fr)


def pick(on, off):
    if abs(len(on['lines']) - len(off['lines'])) <= EARLY_DIFF \
            and side_conf(on['lines']) >= EARLY_CONF:
        return 'on', True
    co, cf = side_conf(on['lines']), side_conf(off['lines'])
    ne = lambda s: sum(1 for l in s['lines'] if l['toks'])  # noqa: E731
    if abs(co - cf) > TIE:
        return ('on' if co >= cf else 'off'), False
    if ne(on) != ne(off):
        return ('on' if ne(on) > ne(off) else 'off'), False
    return ('on' if co >= cf else 'off'), False


def ghost_mask(lines):
    sqs = sorted(l['sq'] for l in lines)
    med = sqs[len(sqs) // 2] if sqs else 1.0
    return [(not l['toks']) or (l['notes'] <= 2 and l['sq'] < 0.3 * med)
            for l in lines]


def main():
    import evaluate
    os.makedirs(OUT, exist_ok=True)
    vocab = json.load(open(os.path.join(MODEL, 'vocab.json'), encoding='utf-8'))
    stoi = {tuple(t): i + 1 for i, t in enumerate(vocab)}
    d = json.load(open(GD, encoding='utf-8'))
    photos, same_bytes = [], 0
    for set_name in ('canon', 'real'):
        for e in d[set_name]:
            p, skip = pick(e['on'], e['off'])
            assert (p, skip) == (e['pick'], e['skipped']), e['photo']
            lines = e[p]['lines']
            gm = ghost_mask(lines)
            kept = [l for l, g in zip(lines, gm) if not g]
            alt, ratio = paired(kept)
            toks = [l['toks'] for l in kept]
            notes, total = R.build_score(toks)
            midi = R.write_midi_bytes(notes, total, bpm=90)
            # 기준 구현 정합: 셈여림 없으면 write_midi(unfold) 와 같은 바이트
            if not any(t[0] in R.DYN_VEL for l in toks for t in l):
                tmp = os.path.join(OUT, '_tmp.mid')
                evaluate.write_midi(tmp, R.unfold_tokens(
                    [tuple(t) for l in toks for t in l]), bpm=90)
                assert open(tmp, 'rb').read() == midi, e['photo']
                same_bytes += 1

            def pack(s):
                return dict(n=len(s['lines']), lines=[dict(
                    ids=[stoi[tuple(t)] for t in l['toks']], conf=l['conf'],
                    frames=l['frames'], w=l['w'], sq=l['sq'], cy=l['cy'],
                    gap=l['gap']) for l in s['lines']])
            photos.append(dict(
                photo=f'{set_name}:{e["photo"]}', on=pack(e['on']),
                off=pack(e['off']), pick=p, skipped=skip, ghost=gm,
                pair_alt=alt, pair_ratio=ratio,
                notes=[list(n) for n in notes], total=total,
                midi=base64.b64encode(midi).decode()))
    # 텐서 단위: staffQ·음표머리 (다트 파이프라인 출력 텐서 그대로)
    man = json.load(open(os.path.join(DART_OUT, 'dart_manifest.json')))
    tensors = []
    for ph in man['photos']:
        for side, s in ph['sides'].items():
            for i, l in enumerate(s['lines']):
                f = f"{ph['stem']}/{side}_l{i:02d}.bin"
                a = np.fromfile(os.path.join(DART_OUT, f), dtype='<f4')
                a = a.reshape(160, l['w'])
                heads, tall = head_stats(a)
                tensors.append(dict(file=f, w=l['w'],
                                    sq=staff_q(a.astype(np.float64))[0],
                                    heads=heads, tall=tall))
    json.dump(dict(photos=photos, tensors=tensors, tensor_dir=DART_OUT),
              open(os.path.join(OUT, 'fixture.json'), 'w'))
    print(f'사진 {len(photos)}장(SMF 기준 바이트 일치 {same_bytes}장), '
          f'텐서 {len(tensors)}줄 → {OUT}/fixture.json')


if __name__ == '__main__':
    main()
