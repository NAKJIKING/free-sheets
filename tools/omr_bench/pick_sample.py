#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OMR 성능 측정용 표본 뽑기.

카탈로그에서 **악보 PDF 와 정답 MIDI 를 둘 다 가진 곡**을 골라,
출처·성부 두께·쪽수로 고르게 나눠 표본을 만든다.

왜 이렇게 뽑는가 — 카탈로그의 `instrument` 는 **주인공 악기일 뿐 짜임새가 아니다.**
'Cello' 로 적힌 곡이 실제로는 5성부인 경우가 있어, 악기 이름으로 뽑으면
단선율만 재려다 합주곡만 재게 된다(2026-09-09 에 실제로 겪음).
성부 두께는 **MIDI 에서 동시에 울리는 최대 음 수**로 직접 잰다.

    python3 tools/omr_bench/pick_sample.py --n 300 -o tools/omr_bench/sample.json
"""
import argparse
import collections
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG = os.path.join(ROOT, 'catalog.json')


def max_polyphony(path):
    """동시에 울리는 최대 음 수. 1 이면 완전한 단선율."""
    import mido
    try:
        mf = mido.MidiFile(path, clip=True)
    except Exception:
        return None
    ev = []
    for tr in mf.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == 'note_on' and m.velocity > 0:
                ev.append((t, 1))
            elif m.type == 'note_off' or (m.type == 'note_on' and m.velocity == 0):
                ev.append((t, -1))
    ev.sort()
    cur = mx = 0
    for _, d in ev:
        cur += d
        mx = max(mx, cur)
    return mx


def pdf_pages(path):
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError:
        return None
    if not data.startswith(b'%PDF-'):
        return None
    m = re.findall(rb'/Count\s+(\d+)', data)
    return max((int(x) for x in m), default=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=300, help='표본 크기')
    ap.add_argument('-o', '--out', default=os.path.join(ROOT, 'tools/omr_bench/sample.json'))
    ap.add_argument('--seed', type=int, default=20260909)
    args = ap.parse_args()
    random.seed(args.seed)

    with open(CATALOG, encoding='utf-8') as f:
        catalog = json.load(f)

    pool = []
    for e in catalog:
        if e.get('base'):                       # 외부 호스팅 — 로컬에서 못 잰다
            continue
        f_, m_ = e.get('file'), e.get('midi')
        if not (f_ and m_):
            continue
        fp, mp = os.path.join(ROOT, f_), os.path.join(ROOT, m_)
        if not (os.path.exists(fp) and os.path.exists(mp)):
            continue
        pg = pdf_pages(fp)
        poly = max_polyphony(mp)
        if not pg or not poly:
            continue
        pool.append({'source': e.get('source'), 'title': e.get('title'),
                     'file': f_, 'midi': m_, 'pages': pg, 'poly': poly,
                     'instrument': e.get('instrument'), 'level': e.get('level')})

    print(f'대조 가능한 곡 {len(pool)}개', file=sys.stderr)

    # 층: (출처, 성부 두께 구간) — 각 층에서 고르게 뽑는다
    def band(p):
        return '1(단선율)' if p == 1 else ('2-3' if p <= 3 else ('4-5' if p <= 5 else '6+'))

    strata = collections.defaultdict(list)
    for e in pool:
        strata[(e['source'], band(e['poly']))].append(e)

    # 단선율에 절반을 배정한다 — 1차 목표가 단선율 인식이기 때문
    mono = [k for k in strata if k[1].startswith('1')]
    rest = [k for k in strata if not k[1].startswith('1')]
    picked = []
    for group, quota in ((mono, args.n // 2), (rest, args.n - args.n // 2)):
        if not group:
            continue
        per = max(1, quota // len(group))
        for k in group:
            picked += random.sample(strata[k], min(per, len(strata[k])))
    # 모자라면 남은 것에서 채운다
    left = [e for e in pool if e not in picked]
    random.shuffle(left)
    picked += left[:max(0, args.n - len(picked))]
    picked = picked[:args.n]

    stat = collections.Counter((e['source'], band(e['poly'])) for e in picked)
    print(f'{"출처":<20}{"성부":<10}{"곡수":>5}', file=sys.stderr)
    for (s, b), n in sorted(stat.items()):
        print(f'{s:<20}{b:<10}{n:>5}', file=sys.stderr)
    print(f'합계 {len(picked)}곡', file=sys.stderr)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(picked, f, ensure_ascii=False, indent=1)
    print(f'→ {args.out}', file=sys.stderr)


if __name__ == '__main__':
    main()
