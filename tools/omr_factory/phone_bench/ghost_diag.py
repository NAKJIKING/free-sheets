#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5 가짜 줄(제목·여백 오검출) 진단 — 줄별 특징 수집 + 제거 규칙 평가.

    python ghost_diag.py collect   # 캐논 53 + 비캐논 43장 → ghost_diag.json
    python ghost_diag.py analyze   # 규칙 격자 평가(NER 악화 없음 조건)

collect: 사진마다 켬/끔 두 경로를 폰과 같은 방식(줄당 B=1 ORT FP32)으로
인식하고 v4 조기 결정·자동선택으로 고른 쪽의 줄별 특징을 남긴다 —
음표 수·토큰 수·줄 CTC 신뢰도·텐서 폭·오선 대비(staff_q, 아래 정의).
analyze: 줄 제거 규칙을 격자로 돌려 캐논·비캐논 NER(evaluate_duet 채점과
같은 줄 DP 정렬)을 v4(제거 없음)와 비교. 저장소 밖 출력(커밋 금지).
"""
import json
import os
import sys

# 저장소 밖 자료의 뿌리 — 사용자 폴더(식당 PC C:/Users/user, 집 PC C:/Users/cocok).
# 환경변수 OMR_ASSET_HOME 으로 덮어쓸 수 있다.
HOME = os.environ.get('OMR_ASSET_HOME') or os.path.expanduser('~')

sys.path.insert(0, os.path.join(HOME, 'free-sheets', 'tools', 'omr_factory'))
import numpy as np

OUT = os.path.join(HOME, 'omr_phone_bench_assets', 'ghost_diag.json')
ONNX = os.path.join(HOME, 'omr_export', 'omr_crnn_fp32.onnx')
MODEL = os.path.join(HOME, 'omr_model_3c4')
CANON = os.path.join(HOME, 'omr_photo_canon')
CANON_TRUTH = os.path.join(HOME, 'omr_dense', 'truth_canon.json')
CANON_RENDER = os.path.join(HOME, 'omr_dense', '캐논_플루트.png')
REAL = os.path.join(HOME, 'omr_real_shots')
REAL_REPORT = os.path.join(HOME, 'omr_real_lines', 'report.json')
PRINT = os.path.join(HOME, 'omr_print')
EARLY_CONF, EARLY_DIFF = 0.9975, 2          # v4 조기 결정(폰과 동일)


def staff_q(a):
    """정규화 텐서(160×w, 잉크 0~1, 오선 간격 12·중앙 80)의 오선 대비.

    다섯 오선 행(±1행 중 최대)의 평균 잉크 − 오선 사이 네 행 평균 잉크.
    진짜 보표는 오선이 폭 전체를 가로질러 크고, 제목·여백 오검출은 작다.
    다트(full_bench)에서 같은 식으로 계산한다."""
    rows = a.mean(axis=1)
    s = [max(rows[r - 1], rows[r], rows[r + 1]) for r in (56, 68, 80, 92, 104)]
    b = [rows[r] for r in (62, 74, 86, 98)]
    return float(np.mean(s) - np.mean(b)), float(min(s) - np.mean(b))


def collect():
    import torch
    import torch.nn.functional as F
    from PIL import Image, ImageOps

    import dataset as D
    import photo_prep
    import prep
    from evaluate_duet import build_line_truth
    from model import greedy_decode
    from ort_model import OrtCRNN
    from real_pack import line_truths

    vocab = D.Vocab.load(os.path.join(MODEL, 'vocab.json'))
    net = OrtCRNN(ONNX)
    dev = torch.device('cpu')

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
            sq, sqmin = staff_q(a)
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
        if abs(len(on['lines']) - len(off['lines'])) <= EARLY_DIFF \
                and on['conf'] >= EARLY_CONF:
            return 'on', True
        if abs(on['conf'] - off['conf']) > 0.002:
            return ('on' if on['conf'] >= off['conf'] else 'off'), False
        if on['nonempty'] != off['nonempty']:
            return ('on' if on['nonempty'] > off['nonempty'] else 'off'), False
        return ('on' if on['conf'] >= off['conf'] else 'off'), False

    # 사진마다 중간 저장 — 메모리 가드로 끊겨도 이어서 돈다
    out = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) \
        else dict(canon=[], real=[])
    save = lambda: json.dump(out, open(OUT, 'w', encoding='utf-8'))
    done = {e['photo'] for e in out['canon'] + out['real']}
    # ── 캐논 53장: 줄별 정답 = 렌더 역산(evaluate_duet 와 동일)
    if 'canon_refs' not in out:
        tr = json.load(open(CANON_TRUTH, encoding='utf-8'))
        voices = [[(p, d) for p, d, _t in v if p > 0] for v in tr['voices']]
        lt = build_line_truth(CANON_RENDER, net, vocab, dev, voices)
        out['canon_refs'] = [[list(n) for n in seq] for _vi, seq in lt]
    import glob
    photos = sorted(glob.glob(os.path.join(CANON, '*.jpg')))
    for i, ph in enumerate(photos):
        if os.path.basename(ph) in done:
            continue
        on, off = side(ph, True), side(ph, False)
        p, skip = pick(on, off)
        out['canon'].append(dict(photo=os.path.basename(ph), pick=p,
                                 skipped=skip, on=on, off=off))
        print(f'canon {i + 1}/{len(photos)} {os.path.basename(ph)} '
              f'{p} on{len(on["lines"])} off{len(off["lines"])}', flush=True)
        save()
    # ── 비캐논 43장: 시트 정답(인쇄 렌더 역산) + real_pack 매칭 결과(시트·회전)
    truth = json.load(open(os.path.join(PRINT, 'truth.json'), encoding='utf-8'))
    rep = json.load(open(REAL_REPORT, encoding='utf-8'))
    sheet_refs = out.setdefault('real_refs', {})
    for m in rep['matched']:
        sid = m['sheet']
        if sid not in sheet_refs:
            toks, _drift = line_truths(os.path.join(PRINT, sid + '.png'),
                                       truth[sid]['tokens'], net, vocab, dev)
            sheet_refs[sid] = [[[p, d] for p, d, _t in seq if p > 0]
                               for seq in toks]
    save()
    for i, m in enumerate(rep['matched']):
        if m['photo'] in done:
            continue
        with Image.open(os.path.join(REAL, m['photo'])) as im:
            img = ImageOps.exif_transpose(im).convert('L')
        if m['rot']:
            img = img.rotate(m['rot'], expand=True)
        on, off = side(img, True), side(img, False)
        p, skip = pick(on, off)
        out['real'].append(dict(photo=m['photo'], sheet=m['sheet'], pick=p,
                                skipped=skip, on=on, off=off))
        print(f'real {i + 1}/{len(rep["matched"])} {m["photo"]} {p}',
              flush=True)
        save()
    print('done →', OUT)


# ───────────────────────── 규칙 평가 ─────────────────────────
def score(refs, lines):
    """evaluate_duet 채점: 토큰 빈 줄 제외 → 줄 DP 정렬 → (오류, 정답음).
    반환에 줄별 판정(짝지은 정답 줄 또는 None=유령)도 함께."""
    from evaluate_photo import align_lines
    from train import edit
    keep = [l for l in lines if l['toks']]
    hyp = [[(p, d) for p, d, _t in l['toks'] if p > 0] for l in keep]
    rf = [[tuple(n) for n in r] for r in refs]
    pe = pt = 0
    lab = {}
    for ri, hj in align_lines(rf, hyp):
        if ri is None:
            pe += len(hyp[hj])
            lab[id(keep[hj])] = None
        elif hj is None:
            pe += len(rf[ri])
            pt += len(rf[ri])
        else:
            e = edit(rf[ri], hyp[hj])
            pe += e
            pt += len(rf[ri])
            lab[id(keep[hj])] = (ri, e)
    return pe, pt, lab


def is_ghost(l, page, rule):
    """제거 규칙. rule = (최대 음표 수, conf 상한, 오선대비 상한).
    음표가 적고(≤nmax) [줄 신뢰도 낮음 또는 오선 대비 약함]이면 가짜.
    음표 0개 줄은 조건 없이 가짜(재생할 것이 없다)."""
    nmax, cmax, qmax = rule
    if l['notes'] == 0:
        return True
    if l['notes'] > nmax:
        return False
    return l['conf'] < cmax or l['sq'] < qmax * page['sq_med']


def analyze():
    d = json.load(open(OUT, encoding='utf-8'))
    sets = [('canon', [(e, d['canon_refs']) for e in d['canon']]),
            ('real', [(e, d['real_refs'][e['sheet']]) for e in d['real']])]
    # 1) 가짜 줄 실태 — 선택된 쪽의 줄 중 정답 짝이 없는 줄(유령) 특징
    for name, items in sets:
        ghosts, reals = [], []
        for e, refs in items:
            lines = e[e['pick']]['lines']
            _pe, _pt, lab = score(refs, lines)
            sqs = sorted(l['sq'] for l in lines)
            med = sqs[len(sqs) // 2] if sqs else 1.0
            for k, l in enumerate(lines):
                row = (e['photo'], k + 1, len(lines), l['notes'],
                       round(l['conf'], 4), round(l['sq'] / max(1e-6, med), 2),
                       round(l['sqmin'], 3), l['w'])
                if not l['toks'] or lab.get(id(l)) is None:
                    ghosts.append(row)
                elif lab[id(l)][1] >= max(1, l['notes']):   # 짝은 있으나 전부 오답
                    ghosts.append(row + ('짝·전오답',))
                else:
                    reals.append(row)
        print(f'\n[{name}] 유령 후보 {len(ghosts)}줄 / 정상 {len(reals)}줄')
        print('  사진 줄/총 음표 conf sq비 sqmin 폭')
        for g in ghosts:
            print('  ', *g)
        rs = sorted(reals, key=lambda r: r[3])[:12]
        print('  정상 줄 중 음표 최소 12:')
        for r in rs:
            print('  ', *r)

    # 2) 규칙 격자 — 두 세트 모두 NER 악화 없음(≤ v4) 중 제거 줄 최대
    def run(rule):
        res = {}
        for name, items in sets:
            ne = nt = removed = 0
            for e, refs in items:
                lines = e[e['pick']]['lines']
                sqs = sorted(l['sq'] for l in lines)
                page = dict(sq_med=sqs[len(sqs) // 2] if sqs else 1.0)
                kept = lines if rule is None else \
                    [l for l in lines if not is_ghost(l, page, rule)]
                removed += len(lines) - len(kept)
                pe, pt, _ = score(refs, kept)
                ne += pe
                nt += pt
            res[name] = (ne / max(1, nt), removed, ne, nt)
        return res

    base = run(None)
    print('\nv4(제거 없음):', {k: f'{v[0]:.4%}' for k, v in base.items()})
    rows = []
    for nmax in (0, 1, 2, 3, 5, 8):
        for cmax in (0.0, 0.95, 0.97, 0.98, 0.99):
            for qmax in (0.0, 0.3, 0.4, 0.5, 0.6):
                r = run((nmax, cmax, qmax))
                ok = all(r[k][0] <= base[k][0] + 1e-12 for k in r)
                rows.append(((nmax, cmax, qmax), r, ok))
    print('규칙(nmax,cmax,qmax) | canon NER·제거 | real NER·제거 | 악화없음')
    for rule, r, ok in rows:
        print(f'  {rule} | {r["canon"][0]:.4%} {r["canon"][1]:3d} | '
              f'{r["real"][0]:.4%} {r["real"][1]:3d} | {"O" if ok else "x"}')


if __name__ == '__main__':
    {'collect': collect, 'analyze': analyze}[sys.argv[1]]()
