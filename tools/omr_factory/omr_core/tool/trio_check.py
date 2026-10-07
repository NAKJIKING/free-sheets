#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3중주·4중주 파트 나누기 — 렌더로만 확인(실물 사진 없음, 한계로 기록).

    python trio_check.py   # → C:/Users/user/omr_poly_calib/ens_*.png 조판 + 결과 표

파트마다 무작위 단선율(8분음표)을 만들어 StaffGroup 으로 조판 → 끔 경로 + ORT
(폰과 같은 줄당 B=1) → 가짜 줄 제거 → group_parts → 파트별 음표열을 원 선율과
편집거리 비교(음높이·길이).
"""
import glob
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
from poly_calib import OUT, LILY, lines_of  # noqa: E402
from poly_signals import kept_lines  # noqa: E402
from ref_parts import group_parts, part_tokens  # noqa: E402
from train import edit  # noqa: E402

NAMES = ['c', 'd', 'e', 'f', 'g', 'a', 'b']
STEPS = [0, 2, 4, 5, 7, 9, 11]


def melody(rng, n, lo):
    """lo = 시작 음계 위치(0 = c'). → (lilypond 문자열, [(midi, 6)])."""
    out, notes, i = [], [], lo + 3
    for _ in range(n):
        i = max(lo, min(lo + 9, i + rng.choice((-2, -1, 1, 2))))
        o, s = divmod(i, 7)
        name = NAMES[s] + ("'" * (o + 1) if o >= 0 else "," * (-o - 1))
        out.append(name + '8')
        notes.append((60 + 12 * o + STEPS[s], 6))
    return ' '.join(out), notes


def render(name, k, bars, seed):
    rng = random.Random(seed)
    los = [7, 3, 0, -3][:k]                    # 파트별 음역(위가 높게)
    staves, truth = [], []
    for j in range(k):
        ly, notes = melody(rng, bars * 8, los[j])
        staves.append(r'\new Staff { \time 4/4 %s }' % ly)
        truth.append(notes)
    src = (r'\version "2.24.4" #(set-global-staff-size 18) '
           r'\paper { #(set-paper-size "a4") indent = 0\mm print-page-number = ##f '
           r'ragged-last-bottom = ##t } \header { title = "%s" tagline = ##f } '
           r'\score { \new StaffGroup << %s >> \layout {} }' % (name, ' '.join(staves)))
    stem = os.path.join(OUT, name)
    open(stem + '.ly', 'w', encoding='utf-8').write(src)
    subprocess.run([LILY, '-dresolution=300', '--png', '-dno-point-and-click',
                    '-o', stem, stem + '.ly'], capture_output=True, timeout=300)
    for extra in glob.glob(stem + '-page*.png'):
        if extra.endswith('-page1.png'):
            os.replace(extra, stem + '.png')
        else:
            os.remove(extra)
    return stem + '.png', truth


def main():
    cases = [('ens_duo', 2, 16, 11), ('ens_trio0', 3, 12, 12),
             ('ens_trio1', 3, 12, 13), ('ens_quartet', 4, 8, 14)]
    print('이름  파트수(기대)  단 크기  파트별 NER(1페이지 분량만 비교)')
    for name, k, bars, seed in cases:
        png, truth = render(name, k, bars, seed)
        lines = kept_lines(lines_of(png))
        g = group_parts(lines)
        sizes = [len(s) for s in g['systems']]
        res = []
        if g['k'] == k:
            parts = part_tokens(lines, g)
            for j in range(k):
                hyp = [(p, d) for p, d, _t in parts[j] if p > 0]
                # 1페이지에 다 안 들어갔으면 앞부분만 비교
                ref = truth[j][:len(hyp)] if len(hyp) < len(truth[j]) else truth[j]
                res.append(f'{edit(ref, hyp) / max(1, len(ref)):.2%}({len(hyp)}음)')
        print(f'  {name:12s} {g["k"]}({k})  {sizes}  {" / ".join(res) or "나누기 실패"}')


if __name__ == '__main__':
    main()
