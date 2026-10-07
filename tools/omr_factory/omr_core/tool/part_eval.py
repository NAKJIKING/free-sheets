#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""파트 나누기 검증 — 캐논 2중주 53장 파트별 NER + 단선율 43장 1파트 회귀.

    python part_eval.py            # ghost_diag.json(폰 방식 인식 결과) 재사용

캐논: 파트 j 의 음표열(전개 전, 쉼표·기호 제외)을 정답 voices[j] 음표열과
편집거리로 비교 — 파트별 NER = 오류/정답 음 수. 참고로 같은 줄들을 정답 줄에
DP 로 짝지은 '오라클 배정' NER(evaluate_duet 채점, ghost_diag.score)도 함께 낸다
— 파트 나누기가 잃는 몫 = 둘의 차.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory\phone_bench')
from ghost_diag import OUT as GD, score  # noqa: E402
from poly_signals import kept_lines  # noqa: E402
from ref_parts import group_parts, part_tokens  # noqa: E402
from train import edit  # noqa: E402


def notes(toks):
    return [(p, d) for p, d, _t in toks if p > 0]


def main():
    d = json.load(open(GD, encoding='utf-8'))
    tr = json.load(open('C:/Users/user/omr_dense/truth_canon.json', encoding='utf-8'))
    voices = [notes([tuple(t) for t in v]) for v in tr['voices']]
    ks = collections.Counter()
    pe, pt = [0, 0], [0, 0]
    oe = ot = 0
    bad = []
    for e in d['canon']:
        lines = kept_lines(e[e['pick']]['lines'])
        g = group_parts(lines)
        ks[g['k']] += 1
        e_, t_, _ = score(d['canon_refs'], lines)
        oe += e_
        ot += t_
        if g['k'] != 2:
            bad.append((e['photo'], g['k'], round(g['ratio'], 2), len(lines)))
            # 나누지 못한 사진: 두 파트 모두 '전부 누락'으로 센다(정직한 채점)
            for j in (0, 1):
                pe[j] += len(voices[j])
                pt[j] += len(voices[j])
            continue
        parts = part_tokens(lines, g)
        for j in (0, 1):
            pe[j] += edit(voices[j], notes(parts[j]))
            pt[j] += len(voices[j])
    print(f'[캐논 53장] 파트 수 분포 {dict(ks)}')
    print(f'  파트별 NER  1파트 {pe[0] / pt[0]:.4%}  2파트 {pe[1] / pt[1]:.4%}  '
          f'합 {(pe[0] + pe[1]) / (pt[0] + pt[1]):.4%}')
    print(f'  (참고) 정답 줄 오라클 배정 NER {oe / ot:.4%}')
    print(f'  2파트로 못 나눈 사진: {bad}')
    kr = collections.Counter()
    for e in d['real']:
        g = group_parts(kept_lines(e[e['pick']]['lines']))
        kr[g['k']] += 1
        if g['k'] != 1:
            print('  ! 단선율인데 다파트:', e['photo'], g['k'], round(g['ratio'], 2))
    print(f'[단선율 43장] 파트 수 분포 {dict(kr)}')


if __name__ == '__main__':
    main()
