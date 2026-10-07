#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""단선율 아님 경고 신호 보정용 — 화음·피아노·2중음 악보를 LilyPond 로 조판해
우리 파이프라인(끔 경로 + ORT FP32, 줄당 B=1)에 넣고 신호를 잰다.

    python poly_calib.py render   # → C:/Users/user/omr_poly_calib/*.png
    python poly_calib.py dump      # 실물 96장 선택 경로 줄 텐서 캐시(uint8 npz)
    python poly_calib.py evaluate  # 최종 신호 표 (렌더 + 실물 96장)

양성(경고 떠야 함): chord(한 박마다 3화음), dyad(4음 중 1음 겹3·6도),
piano(피아노 큰보표: 오른손 선율 + 왼손 화음). 음성: mel(단선율 대조).
출력 PNG 는 저장소 밖(커밋 금지).
"""
import glob
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
OUT = 'C:/Users/user/omr_poly_calib'
LILY = os.environ.get('LILYPOND', 'lilypond')
HEAD = r'''\version "2.24.4"
#(set-global-staff-size 20)
\paper { #(set-paper-size "a4") indent = 0\mm print-page-number = ##f
  ragged-last-bottom = ##t }
\header { title = "%s" tagline = ##f }
'''
SCALE = ["c'", "d'", "e'", "f'", "g'", "a'", "b'", "c''", "d''", "e''", "f''", "g''"]


def mel(rng, bars, dur='8'):
    out = []
    i = 5
    for _ in range(bars * (8 if dur == '8' else 4)):
        i = max(0, min(len(SCALE) - 1, i + rng.choice((-2, -1, -1, 1, 1, 2))))
        out.append(SCALE[i] + dur)
    return ' '.join(out)


def chords(rng, bars, dur='4'):
    out = []
    for _ in range(bars * 4):
        i = rng.randrange(0, len(SCALE) - 4)
        out.append(f'<{SCALE[i]} {SCALE[i + 2]} {SCALE[i + 4]}>{dur}')
    return ' '.join(out)


def dyads(rng, bars):
    out = []
    i = 5
    for k in range(bars * 4):
        i = max(0, min(len(SCALE) - 3, i + rng.choice((-2, -1, 1, 2))))
        out.append(f'<{SCALE[i]} {SCALE[i + 2]}>4' if k % 4 == 0 else SCALE[i] + '4')
    return ' '.join(out)


def render():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(7)
    pages = {}
    for s in range(2):
        pages[f'mel{s}'] = r'\score { { \time 4/4 %s } \layout {} }' % mel(rng, 40)
        pages[f'chord{s}'] = r'\score { { \time 4/4 %s } \layout {} }' % chords(rng, 36)
        pages[f'dyad{s}'] = r'\score { { \time 4/4 %s } \layout {} }' % dyads(rng, 40)
        lh = ' '.join(f'<{a} {b} {c}>2' for a, b, c in
                      [rng.choice((("c", "e", "g"), ("f,", "a,", "c"),
                                   ("g,", "b,", "d"))) for _ in range(48)])
        pages[f'piano{s}'] = (r'\score { \new PianoStaff << \new Staff { \time 4/4 %s }'
                              r' \new Staff { \clef bass %s } >> \layout {} }'
                              % (mel(rng, 24), lh))
    # 음성(단선율) 함정 페이지: 임시표 많은 선율·조표 6개·빠르기표·16분 겹빔
    def acc_mel(bars):
        out = []
        i = 5
        for _ in range(bars * 8):
            i = max(0, min(len(SCALE) - 1, i + rng.choice((-2, -1, 1, 2))))
            p = SCALE[i]
            p = p[0] + rng.choice(('', 'is', 'es', '')) + p[1:]
            out.append(p + '8')
        return ' '.join(out)
    pages['acc0'] = (r'\score { { \key fis \major \time 4/4 \tempo 4 = 96 %s } '
                     r'\layout {} }' % acc_mel(36))
    pages['acc1'] = (r'\score { { \key ges \major \time 3/4 \tempo "Allegro" 4 = 132 %s } '
                     r'\layout {} }' % acc_mel(36))
    pages['fast0'] = (r'\score { { \key d \major \time 2/4 %s } \layout {} }'
                      % mel(rng, 30, '16'))
    for name, body in pages.items():
        stem = os.path.join(OUT, name)
        open(stem + '.ly', 'w', encoding='utf-8').write(HEAD % name + body)
        subprocess.run([LILY, '-dresolution=300', '--png', '-dno-point-and-click',
                        '-o', stem, stem + '.ly'], capture_output=True, timeout=300)
        for extra in glob.glob(stem + '-page*.png'):
            if not extra.endswith('-page1.png'):
                os.remove(extra)
            else:
                os.replace(extra, stem + '.png')
        print(name, os.path.exists(stem + '.png'), flush=True)


def lines_of(img):
    """폰과 같은 처리: 끔 경로(깨끗한 렌더라 보정 불필요) + 줄당 B=1 디코드."""
    import torch
    import torch.nn.functional as F
    import dataset as D
    import photo_prep
    import prep
    from model import greedy_decode
    from ort_model import OrtCRNN
    sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory\phone_bench')
    from ghost_diag import ONNX, MODEL, staff_q
    global _net, _vocab
    if '_net' not in globals():
        _net = OrtCRNN(ONNX)
        _vocab = D.Vocab.load(os.path.join(MODEL, 'vocab.json'))
    out = []
    for c, cy, g in photo_prep.extract_lines(img, correct=False, with_pos=True):
        a = prep.normalize_photo(c, gap_hint=g)
        lg = _net(torch.from_numpy(a)[None, None]).float()
        n = max(1, a.shape[1] // 4)
        ids = greedy_decode(lg, torch.tensor([n]))[0]
        toks = [list(_vocab.itos[k]) for k in ids if k > 0]
        out.append(dict(toks=toks, notes=sum(1 for t in toks if t[0] > 0),
                        sq=staff_q(a)[0], w=int(a.shape[1]), cy=float(cy),
                        gap=float(g),
                        conf=float(F.softmax(lg, -1).max(-1).values[0, :n].mean())))
    return out


def dump():
    """96장 선택 경로의 가짜 제외 줄 텐서를 uint8 npz 로 캐시(실험 반복용)."""
    import numpy as np
    from PIL import Image, ImageOps
    import photo_prep
    import prep
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from poly_signals import kept_lines
    sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory\phone_bench')
    from ghost_diag import OUT as GD, CANON, REAL
    d = json.load(open(GD, encoding='utf-8'))
    rep = {m['photo']: m for m in json.load(open(
        'C:/Users/user/omr_real_lines/report.json', encoding='utf-8'))['matched']}
    out_dir = os.path.join(OUT, 'tensors')
    os.makedirs(out_dir, exist_ok=True)
    for set_name in ('canon', 'real'):
        for e in d[set_name]:
            key = f'{set_name}_{e["photo"][:-4]}'
            path = os.path.join(out_dir, key + '.npz')
            if os.path.exists(path):
                continue
            if set_name == 'canon':
                img = os.path.join(CANON, e['photo'])
            else:
                with Image.open(os.path.join(REAL, e['photo'])) as im:
                    img = ImageOps.exif_transpose(im).convert('L')
                if rep[e['photo']]['rot']:
                    img = img.rotate(rep[e['photo']]['rot'], expand=True)
            res_l = photo_prep.extract_lines(img, correct=e['pick'] == 'on',
                                             with_pos=True)
            lines = e[e['pick']]['lines']
            keep = {id(l) for l in kept_lines(lines)}
            arrs = {}
            for i, ((c, _cy, g), l) in enumerate(zip(res_l, lines)):
                if id(l) in keep:
                    a = prep.normalize_photo(c, gap_hint=g)
                    arrs[f'l{i:02d}'] = np.round(np.clip(a, 0, 1) * 255).astype(np.uint8)
            np.savez_compressed(path, **arrs)
            print(key, len(arrs), flush=True)
    print('done')


def evaluate():
    """최종 신호 표 — 렌더(양성·함정) + 실물 96장 캐시 텐서(dump).
    렌더는 끔 경로 정규화 텐서로 머리 비율과 보표 쌍(검출 cy·gap)을 잰다."""
    import numpy as np
    import photo_prep
    import prep
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import poly_signals as S
    from ref_parts import group_parts

    def frac(stats):
        n = sum(a for a, _ in stats)
        return sum(b for _, b in stats) / n if n else 0.0

    print('[렌더]  이름  쌓인머리비율  파트수  화음경고')
    pages = [p for p in sorted(glob.glob(os.path.join(OUT, '*.png')))
             if 'dbg' not in p] + ['C:/Users/user/omr_dense/캐논_플루트.png']
    for p in pages:
        res = photo_prep.extract_lines(p, correct=False, with_pos=True)
        st = [S.head_stats(prep.normalize_photo(c, gap_hint=g)) for c, _y, g in res]
        k = group_parts([dict(cy=y, gap=g) for _c, y, g in res])['k']
        f = frac(st)
        print(f'  {os.path.basename(p)[:-4]:12s} {f:.3f}  {k}  '
              f'{"경고" if f >= S.STACKED_FRAC_WARN else "-"}')
    for set_name in ('canon', 'real'):
        fr = []
        for f in sorted(glob.glob(os.path.join(OUT, 'tensors', set_name + '_*.npz'))):
            z = np.load(f)
            fr.append((frac([S.head_stats(z[k].astype(np.float32) / 255.0)
                             for k in z.files]), os.path.basename(f)[:-4]))
        fr.sort()
        over = [n for v, n in fr if v >= S.STACKED_FRAC_WARN]
        print(f'[실물 {set_name} {len(fr)}장] 쌓인머리 최대 {fr[-1][0]:.3f}, '
              f'문턱({S.STACKED_FRAC_WARN}) 이상 {len(over)}장 {over}')

if __name__ == '__main__':
    {'render': render, 'dump': dump, 'evaluate': evaluate}[sys.argv[1]]()
