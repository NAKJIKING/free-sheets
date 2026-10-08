#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S5 사진 크기 실험 — 긴 변 축소(2000/2500/3000px)별 NER 을 원본과 비교.

    python size_study.py collect 2000   # 한 크기씩(메모리 가드, 이어 돌기)
    python size_study.py analyze        # 원본(ghost_diag.json) 대비 표

collect 는 ghost_diag.collect 와 같은 처리(켬/끔 두 경로, 줄당 B=1 ORT FP32,
v4 조기 결정·자동선택)를 하되 회색 변환 직후 긴 변을 [크기]로 줄인다 —
PIL BILINEAR('L' 8비트) = omr_core capLongSide(삼각 필터 + 8비트 재양자화).
analyze 는 v5 가짜 줄 규칙(음표 0, 또는 음표≤2·오선대비<중앙값×0.3)을 적용한
캐논 53·비캐논 43장 NER 을 ghost_diag.score 로 채점한다. 저장소 밖 출력.
"""
import ctypes
import json
import os
import sys

sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghost_diag as G

OUT_DIR = r'C:\Users\user\omr_phone_bench_assets'
SIZES = (2000, 2500, 3000)
GUARD_MB = 1200                 # 여유 램이 이보다 적으면 스스로 멈춘다
GHOST_RULE = (2, 0.0, 0.3)      # v5 = omr_core select.ghostMask


def out_path(size):
    return os.path.join(OUT_DIR, f'size_study_{size}.json')


def free_mb():
    class MS(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2 ** 20


def cap(img, size):
    """긴 변 > size 면 축소(omr_core capLongSide 와 같은 반올림)."""
    from PIL import Image
    w, h = img.size
    if max(w, h) <= size:
        return img
    s = size / max(w, h)
    return img.resize((int(w * s + 0.5), int(h * s + 0.5)), Image.BILINEAR)


def collect(size):
    import glob

    import torch
    import torch.nn.functional as F
    from PIL import Image, ImageOps

    import dataset as D
    import photo_prep
    import prep
    from model import greedy_decode
    from ort_model import OrtCRNN

    vocab = D.Vocab.load(os.path.join(G.MODEL, 'vocab.json'))
    net = OrtCRNN(G.ONNX)

    def side(img, correct):
        res = photo_prep.extract_lines(img, correct=correct, with_pos=True)
        lines = []
        for c, cy, g in res:
            a = prep.normalize_photo(c, gap_hint=g)
            x = torch.from_numpy(a)[None, None]
            lg = net(x).float()
            n = max(1, a.shape[1] // 4)
            ids = greedy_decode(lg, torch.tensor([n]))[0]
            pr = F.softmax(lg, dim=-1).max(dim=-1).values[0, :n]
            toks = [tuple(vocab.itos[k]) for k in ids if k > 0]
            sq, sqmin = G.staff_q(a)
            lines.append(dict(
                toks=[list(t) for t in toks],
                notes=sum(1 for t in toks if t[0] > 0),
                conf=float(pr.mean()), frames=n, w=int(a.shape[1]),
                sq=sq, sqmin=sqmin, cy=float(cy), gap=float(g)))
        fr = sum(l['frames'] for l in lines)
        conf = sum(l['conf'] * l['frames'] for l in lines) / max(1, fr)
        nonempty = sum(1 for l in lines if l['toks'])
        return dict(lines=lines, conf=conf, nonempty=nonempty)

    def pick(on, off):
        if abs(len(on['lines']) - len(off['lines'])) <= G.EARLY_DIFF \
                and on['conf'] >= G.EARLY_CONF:
            return 'on', True
        if abs(on['conf'] - off['conf']) > 0.002:
            return ('on' if on['conf'] >= off['conf'] else 'off'), False
        if on['nonempty'] != off['nonempty']:
            return ('on' if on['nonempty'] > off['nonempty'] else 'off'), False
        return ('on' if on['conf'] >= off['conf'] else 'off'), False

    def load(path, rot=0):
        with Image.open(path) as im:
            img = ImageOps.exif_transpose(im).convert('L')
        if rot:
            img = img.rotate(rot, expand=True)
        return cap(img, size)

    def guard():
        f = free_mb()
        if f < GUARD_MB:
            print(f'메모리 가드: 여유 {f:.0f}MB < {GUARD_MB}MB — 멈춤(이어 돌기 가능)',
                  flush=True)
            sys.exit(3)

    path = out_path(size)
    out = json.load(open(path, encoding='utf-8')) if os.path.exists(path) \
        else dict(size=size, canon=[], real=[])
    save = lambda: json.dump(out, open(path, 'w', encoding='utf-8'))
    done = {e['photo'] for e in out['canon'] + out['real']}
    photos = sorted(glob.glob(os.path.join(G.CANON, '*.jpg')))
    for i, ph in enumerate(photos):
        if os.path.basename(ph) in done:
            continue
        guard()
        img = load(ph)
        on, off = side(img, True), side(img, False)
        p, skip = pick(on, off)
        out['canon'].append(dict(photo=os.path.basename(ph), wh=list(img.size),
                                 pick=p, skipped=skip, on=on, off=off))
        print(f'[{size}] canon {i + 1}/{len(photos)} {os.path.basename(ph)} '
              f'{img.size} {p}', flush=True)
        save()
    rep = json.load(open(G.REAL_REPORT, encoding='utf-8'))
    for i, m in enumerate(rep['matched']):
        if m['photo'] in done:
            continue
        guard()
        img = load(os.path.join(G.REAL, m['photo']), m['rot'])
        on, off = side(img, True), side(img, False)
        p, skip = pick(on, off)
        out['real'].append(dict(photo=m['photo'], sheet=m['sheet'],
                                wh=list(img.size), pick=p, skipped=skip,
                                on=on, off=off))
        print(f'[{size}] real {i + 1}/{len(rep["matched"])} {m["photo"]} '
              f'{img.size} {p}', flush=True)
        save()
    print('done →', path)


def ner(d, refs_of, rule=GHOST_RULE):
    ne = nt = 0
    for e in d:
        lines = e[e['pick']]['lines']
        sqs = sorted(l['sq'] for l in lines)
        page = dict(sq_med=sqs[len(sqs) // 2] if sqs else 1.0)
        kept = [l for l in lines if not G.is_ghost(l, page, rule)]
        pe, pt, _ = G.score(refs_of(e), kept)
        ne += pe
        nt += pt
    return ne / max(1, nt), ne, nt


def analyze():
    base = json.load(open(G.OUT, encoding='utf-8'))
    canon_refs, real_refs = base['canon_refs'], base['real_refs']
    rows = [('원본', base)]
    for s in SIZES:
        if os.path.exists(out_path(s)):
            rows.append((str(s), json.load(open(out_path(s), encoding='utf-8'))))
    b = None
    print('크기 | 캐논 NER (n) | 비캐논 NER (n) | 악화(캐논, 비캐논) %p')
    for name, d in rows:
        nc, nr = len(d['canon']), len(d['real'])
        c = ner(d['canon'], lambda e: canon_refs)
        r = ner(d['real'], lambda e: real_refs[e['sheet']])
        if b is None:
            b = (c[0], r[0])
        dc, dr = (c[0] - b[0]) * 100, (r[0] - b[1]) * 100
        ok = 'O' if dc <= 0.3 + 1e-9 and dr <= 0.3 + 1e-9 else 'x'
        print(f'{name:>4} | {c[0]:.4%} ({nc}) | {r[0]:.4%} ({nr}) | '
              f'{dc:+.3f}, {dr:+.3f} {ok}')


if __name__ == '__main__':
    if sys.argv[1] == 'collect':
        collect(int(sys.argv[2]))
    else:
        analyze()
