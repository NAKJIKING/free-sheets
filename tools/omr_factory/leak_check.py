#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시험셋 누수 검사 — 같은 가락이 학습셋에도 있는가.

    python tools/omr_factory/leak_check.py --data C:/Users/me/omr_lines

`split.py` 는 **곡 이름**으로 나눈다. 그런데 같은 곡이 출처가 달라 다른
이름으로 두 번 들어와 있으면(예: 엘리제가 `original:elise` 로도,
`pdmx2:...` 로도) 이름 분할은 그것을 못 막는다. 그러면 모델이 시험곡을
학습에서 이미 본 셈이 되어 **관문 1 점수가 통째로 무효**다.

방법: 가락을 **음정 열**(연속 음고 차)로 바꿔 n-gram 을 해시한다. 음정은
조옮김에 불변이므로 '같은 곡을 다른 조로 넣은 것'까지 잡힌다. 시험곡의
n-gram 중 학습곡에도 나오는 비율을 재고, 겹치는 학습곡을 지목한다.

리듬은 일부러 안 본다 — 같은 곡의 다른 편곡은 리듬이 조금씩 달라도
가락 윤곽은 같기 때문이다.
"""
import argparse
import collections
import json
import os
import sys

N = 12                                   # n-gram 길이(음정 12개 ≈ 음표 13개)


def ngrams(pitches):
    iv = [b - a for a, b in zip(pitches, pitches[1:])]
    return {tuple(iv[i:i + N]) for i in range(len(iv) - N + 1)}


def merged(tokens):
    out, carry = [], False
    for p, _d, tie in tokens:
        if p and not carry:
            out.append(p)
        carry = bool(p) and bool(tie)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--thresh', type=float, default=0.30,
                    help='이 비율 넘게 겹치면 보고한다')
    ap.add_argument('--fix-thresh', type=float, default=0.50,
                    help='이 비율 넘고 n-gram 도 충분하면 시험셋에서 뺀다')
    ap.add_argument('--min-ngrams', type=int, default=2,
                    help='n-gram 이 이보다 적은 곡은 판정하지 않는다')
    ap.add_argument('--fix', action='store_true',
                    help='누수 시험곡을 split.json 에서 train 으로 옮긴다')
    a = ap.parse_args()

    split = json.load(open(os.path.join(a.data, 'split.json'), encoding='utf-8'))
    # 곡 → n-gram 집합 (조옮김 판본은 음정이 같으므로 shift 0 만 봐도 되지만,
    # shift 0 이 없는 곡도 있으므로 전부 합친다 — 음정이라 어차피 같다)
    bag = collections.defaultdict(set)
    for ln in open(os.path.join(a.data, 'manifest.jsonl'), encoding='utf-8'):
        r = json.loads(ln)
        bag[r['song']] |= ngrams(merged(r['tokens']))

    # 학습 n-gram → 그것을 가진 학습곡들
    owner = collections.defaultdict(set)
    for s, g in bag.items():
        if split.get(s) == 'train':
            for k in g:
                owner[k].add(s)
    print(f'학습곡 n-gram {len(owner)}종 / 곡 {sum(1 for v in split.values() if v == "train")}')

    bad = []
    for s, g in sorted(bag.items()):
        if split.get(s) != 'test' or not g:
            continue
        hit = [k for k in g if k in owner]
        frac = len(hit) / len(g)
        if frac >= a.thresh:
            src = collections.Counter()
            for k in hit:
                for o in owner[k]:
                    src[o] += 1
            bad.append((frac, s, len(g), src.most_common(3)))

    bad.sort(reverse=True)
    print(f'\n■ 누수 의심 시험곡 {len(bad)}개 (문턱 {a.thresh:.0%})')
    for frac, s, n, src in bad[:25]:
        print(f'  {frac:6.1%}  {s}  (n-gram {n})')
        for o, c in src:
            print(f'            ← {o} ({c})')

    # ── 누수 시험곡을 시험셋에서 뺀다
    # 왜 'train' 으로 옮기나: 어차피 학습셋에 같은 가락이 이미 있으므로
    # 시험에 두면 '이미 본 곡'을 채점해 점수가 부풀려진다. 버리는 것보다
    # 학습에 넣는 편이 데이터를 안 버리고 정직하다.
    # n-gram 이 1개뿐인 곡은 판정하지 않는다 — 음계 한 토막이 우연히 겹친
    # 것을 같은 곡이라고 부르게 된다(실측: Cornelius/Arbeau 오탐).
    moved = [(f, s_, n) for f, s_, n, _src in bad
             if f >= a.fix_thresh and n >= a.min_ngrams]
    print()
    print(f'■ 시험셋에서 뺄 곡 {len(moved)}개 '
          f'(겹침 ≥{a.fix_thresh:.0%} 이고 n-gram ≥{a.min_ngrams})')
    for f, s_, n in moved:
        print(f'  {f:6.1%}  {s_}  (n-gram {n})')
    if a.fix and moved:
        for _f, s_, _n in moved:
            split[s_] = 'train'
        path = os.path.join(a.data, 'split.json')
        json.dump(split, open(path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=0)
        cnt = collections.Counter(split.values())
        print(f'  → {path} 갱신: {dict(cnt)}')

    gate = 'original:elise'
    if gate in bag:
        g = bag[gate]
        hit = [k for k in g if k in owner]
        print(f'\n■ 관문 시험곡 {gate}: 분할={split.get(gate)} / '
              f'n-gram {len(g)} / 학습과 겹침 {len(hit)} '
              f'({len(hit) / max(1, len(g)):.1%})')
        if hit:
            src = collections.Counter()
            for k in hit:
                for o in owner[k]:
                    src[o] += 1
            for o, c in src.most_common(5):
                print(f'    ← {o} ({c})')
        else:
            print('    [OK] 학습셋에 같은 가락 없음 — 관문 유효')
    else:
        print(f'\n[!] {gate} 가 데이터에 없다')
    return 0


if __name__ == '__main__':
    sys.exit(main())
