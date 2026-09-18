#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전처리 캐시 — 300DPI 렌더를 오선 정규화해 학습용 작은 회색 PNG 로 굽는다.

`prep.normalize` 의 오선 찾기는 줄마다 ~25ms 다. 에폭마다 다시 하면
GPU 가 놀기 때문에 한 번 구워 둔다. 동시에 **오선을 못 찾은 줄을 여기서
걸러낸다**(그런 줄은 배율이 틀려 학습을 망친다).

    python tools/omr_factory/cache.py --data C:/Users/me/omr_lines
    → DIR/cache/<var>/<stem>.png  +  DIR/index.jsonl

index.jsonl 한 줄 = {song, var, chunk, shift, split, cache, w, tokens}
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep


def bake(a):
    data, row = a
    src = os.path.join(data, row['png'])
    dst = os.path.join(data, 'cache', row['png'])
    if os.path.exists(dst):
        with Image.open(dst) as im:
            return dict(row, w=im.size[0], ok=True)
    try:
        with Image.open(src) as im:
            g = 1.0 - np.asarray(im.convert('L'), dtype=np.float32) / 255.0
            st = prep.find_staff(g)
            if st is None:
                return dict(row, ok=False, why='오선못찾음')
            x = prep.normalize(im)
    except Exception as e:
        return dict(row, ok=False, why=repr(e)[:80])
    if x.shape[1] < 64:
        return dict(row, ok=False, why='너무좁음')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray((x * 255).astype(np.uint8)).save(dst, optimize=True)
    return dict(row, w=x.shape[1], ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    a = ap.parse_args()

    split = json.load(open(os.path.join(a.data, 'split.json'), encoding='utf-8'))
    rows = [json.loads(l) for l in
            open(os.path.join(a.data, 'manifest.jsonl'), encoding='utf-8')]
    print(f'줄 {len(rows)}개 굽는다 (병렬 {a.jobs})', flush=True)

    n, bad, why = 0, 0, {}
    out = open(os.path.join(a.data, 'index.jsonl'), 'w', encoding='utf-8')
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for r in ex.map(bake, ((a.data, x) for x in rows), chunksize=32):
            n += 1
            if not r.get('ok'):
                bad += 1
                why[r.get('why', '?')] = why.get(r.get('why', '?'), 0) + 1
            else:
                out.write(json.dumps(dict(song=r['song'], var=r.get('var', ''),
                                          chunk=r['chunk'], shift=r['shift'],
                                          split=split.get(r['song'], 'train'),
                                          cache='cache/' + r['png'], w=r['w'],
                                          tokens=r['tokens']),
                                     ensure_ascii=False) + '\n')
            if n % 5000 == 0:
                print(f'  {n}/{len(rows)} 탈락 {bad}', flush=True)
    out.close()
    print(f'끝: 성공 {n - bad} / 탈락 {bad} {why}', flush=True)


if __name__ == '__main__':
    main()
