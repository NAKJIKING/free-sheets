#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습/검증/시험 분할 — **곡 단위**로만 나눈다.

같은 곡이 학습과 시험 양쪽에 있으면 시험은 무효다. 청크 단위로 섞으면
같은 곡의 1번째 줄로 배우고 2번째 줄로 시험을 보는 셈이 된다. 그래서
manifest 의 `song`(악기·설정 판본을 묶은 곡 식별자) 으로 나눈다.

  - **시험(test)**: 엘리제(`original:elise`) 전 청크·전 조 무조건 + 곡의 8%
  - **검증(val)**: 곡의 10%
  - 나머지 학습

    python tools/omr_factory/split.py --data C:/Users/me/omr_lines
    → data/split.json  {song: 'train'|'val'|'test'}
"""
import argparse
import collections
import hashlib
import json
import os

GATE_SONGS = ('original:elise',)          # 관문 1 시험곡 — 절대 학습 금지


def bucket(song, val_pct, test_pct):
    if song in GATE_SONGS:
        return 'test'
    h = int(hashlib.sha1(song.encode('utf-8')).hexdigest(), 16) % 1000
    if h < test_pct * 10:
        return 'test'
    if h < (test_pct + val_pct) * 10:
        return 'val'
    return 'train'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--val', type=float, default=10.0, help='검증용 곡 비율 %%')
    ap.add_argument('--test', type=float, default=8.0, help='시험용 곡 비율 %%')
    a = ap.parse_args()

    songs, lines = set(), collections.Counter()
    with open(os.path.join(a.data, 'manifest.jsonl'), encoding='utf-8') as f:
        for ln in f:
            r = json.loads(ln)
            songs.add(r['song'])
            lines[r['song']] += 1
    split = {s: bucket(s, a.val, a.test) for s in sorted(songs)}
    for g in GATE_SONGS:
        if g not in split:
            print(f'⚠ 관문 시험곡 {g} 가 데이터에 없다', flush=True)

    cnt = collections.Counter(split.values())
    ln = collections.Counter()
    for s, b in split.items():
        ln[b] += lines[s]
    print('곡 수  ', dict(cnt))
    print('줄 수  ', dict(ln))
    for g in GATE_SONGS:
        print(f'  {g}: {split.get(g)} / 줄 {lines.get(g, 0)}')
    out = os.path.join(a.data, 'split.json')
    json.dump(split, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('→', out)


if __name__ == '__main__':
    main()
