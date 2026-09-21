#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관문 2 실물 평가 — 자가 조판 2중주(정답 보유) 폰사진 채점.

    python tools/omr_factory/evaluate_duet.py \
        --photos C:/Users/me/omr_photo_canon \
        --truth C:/Users/me/omr_dense/truth_canon.json \
        --model C:/Users/me/omr_model_g2 --out C:/Users/me/omr_gate2_canon \
        [--no-correct]

정답: truth JSON 의 voices=[1성부 토큰열, 2성부 토큰열] (조판과 원천 동일).
채점: 검출 보표를 세로 간격으로 (위·아래) 짝지어 위=1성부·아래=2성부로
배정하고, 성부별로 위→아래 이어붙인 인식 열을 정답 전체와 편집거리 비교.
누락 보표는 그대로 삭제 오류로 남는다 — 검출 실패를 숨기지 않는 채점.
낙오 보표(짝 없음)는 두 성부 중 잘 맞는 쪽에 넣는다.

증명물: 대표 사진(최고·중앙·최악)의 성부별 정답/모델 미디.
"""
import argparse
import collections
import glob
import json
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as D
import photo_prep
import prep
from evaluate import write_midi
from evaluate_photo import align_lines, decode_crops
from model import CRNN
from train import edit


def infix_edit_win(q, r):
    """q 를 r 안 어디든 끼워 맞추는 최소 편집거리와 소비한 창 길이.

    반환 (오류수, 창길이). q 의 모든 음이 정렬 대상(삽입도 오류로 셈),
    r 은 양끝이 자유 — 보표 하나가 정답 전체의 어느 구간이든 될 수 있다."""
    if not q:
        return 0, 0
    m = len(r)
    prev = [0] * (m + 1)
    start = list(range(m + 1))
    for x in q:
        cur = [prev[0] + 1]
        cst = [start[0]]
        for j in range(1, m + 1):
            sub = prev[j - 1] + (x != r[j - 1])
            dele = prev[j] + 1
            ins = cur[j - 1] + 1
            best = min(sub, dele, ins)
            cur.append(best)
            cst.append(start[j - 1] if best == sub
                       else (start[j] if best == dele else cst[j - 1]))
        prev, start = cur, cst
    j = min(range(m + 1), key=lambda k: prev[k])
    return prev[j], j - start[j]


def infix_edit_span(q, r):
    """infix_edit_win 과 같되 (오류수, 시작, 끝) — 창 위치까지 돌려준다."""
    if not q:
        return 0, 0, 0
    m = len(r)
    prev = [0] * (m + 1)
    start = list(range(m + 1))
    for x in q:
        cur = [prev[0] + 1]
        cst = [start[0]]
        for j in range(1, m + 1):
            sub = prev[j - 1] + (x != r[j - 1])
            dele = prev[j] + 1
            ins = cur[j - 1] + 1
            best = min(sub, dele, ins)
            cur.append(best)
            cst.append(start[j - 1] if best == sub
                       else (start[j] if best == dele else cst[j - 1]))
        prev, start = cur, cst
    j = min(range(m + 1), key=lambda k: prev[k])
    return prev[j], start[j], j


@torch.no_grad()
def decode_conf(net, crops, dev, max_w=2600, batch=8):
    """decode_crops + 신뢰도 — 프레임별 최대 소프트맥스 확률의 평균.

    정답 없이 켬/끔 파이프라인 중 나은 쪽을 고르는 근거로 쓴다: 크롭이
    엉키면(배율·워프 실패) 모델 출력 분포가 뭉개져 신뢰도가 떨어진다."""
    import torch.nn.functional as F
    import prep as _prep
    hyps, confs, frames = [], [], []
    for k in range(0, len(crops), batch):
        chunk = [c[:, :max_w] for c in crops[k:k + batch]]
        W = max(c.shape[1] for c in chunk)
        x = torch.zeros(len(chunk), 1, _prep.HEIGHT, W)
        for i, c in enumerate(chunk):
            x[i, 0, :, :c.shape[1]] = torch.from_numpy(c)
        xl = torch.tensor([c.shape[1] for c in chunk])
        x = x.to(dev)
        with torch.autocast('cuda', dtype=torch.bfloat16,
                            enabled=dev.type == 'cuda'):
            lg = net(x).float()
        ol = net.out_len(xl)
        from model import greedy_decode
        hyps += greedy_decode(lg, ol)
        pr = F.softmax(lg, dim=-1).max(dim=-1).values.cpu()
        for i in range(len(chunk)):
            n = int(ol[i])
            confs.append(float(pr[i, :n].mean()))
            frames.append(n)
    return hyps, confs, frames


def build_line_truth(render, net, vocab, dev, voices):
    """깨끗한 원본 렌더(우리 조판 PNG)를 모델로 읽어(오류 ~0.3%) 각 보표
    줄이 정답의 어느 구간인지 역산 → 줄별 정답 목록(위→아래)과 성부 번호.

    창 경계는 성부별로 이어붙여 빈틈·겹침 없이 스냅한다 — 합이 정답
    전체와 일치하는지 검사해 어긋나면 바로 죽는다(조용한 오답 방지)."""
    crops = photo_prep.extract_lines(render, correct=False)
    assert len(crops) % 2 == 0, f'렌더 보표 수 {len(crops)} — 짝수가 아니다'
    norm = [prep.normalize_photo(c) for c in crops]
    hyps = decode_crops(net, norm, dev)
    decs = [[(p, d) for p, d, _t in
             [tuple(vocab.itos[k]) for k in h if k > 0] if p > 0]
            for h in hyps]
    # 성부는 내용이 아니라 **조판 구조**로 정한다 — 돌림곡은 두 성부 선율이
    # 같아 내용 판별이 반드시 헷갈린다(실측: 성부 배정 붕괴). 위=1성부.
    lines = [None] * len(decs)
    for vi in (0, 1):
        idxs = [i for i in range(len(decs)) if i % 2 == vi]
        pos = 0
        for k, i in enumerate(idxs):
            if k + 1 == len(idxs):
                end = len(voices[vi])
            else:
                _e, _s, t = infix_edit_span(decs[i], voices[vi][pos:])
                end = pos + t
            end = max(end, pos)
            lines[i] = (vi, voices[vi][pos:end])
            pos = end
        assert pos == len(voices[vi]), f'{vi + 1}성부 분할 불일치 {pos}'
    total = sum(len(seq) for _v, seq in lines)
    assert total == len(voices[0]) + len(voices[1])
    return lines                              # [(성부, [(p,d),...]), ...] 위→아래


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--photos', required=True)
    ap.add_argument('--truth', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--ckpt', default='best.pt')
    ap.add_argument('--gate', type=float, default=0.10)
    ap.add_argument('--no-correct', action='store_true')
    ap.add_argument('--auto', action='store_true',
                    help='사진마다 보정 켬/끔을 둘 다 돌려 CTC 신뢰도 높은 쪽 채택')
    ap.add_argument('--proof', type=int, default=3, help='증명물 사진 수')
    ap.add_argument('--render', default='C:/Users/user/omr_dense/캐논_플루트.png',
                    help='깨끗한 원본 렌더 — 줄별 정답 역산용')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    tr = json.load(open(a.truth, encoding='utf-8'))
    voices_tok = [[tuple(t) for t in v] for v in tr['voices']]
    voices = [[(p, d) for p, d, _t in v if p > 0] for v in voices_tok]
    print(f"정답: {tr['song']} — " +
          ' / '.join(f'{i + 1}성부 {len(v)}음' for i, v in enumerate(voices)))

    vocab = D.Vocab.load(os.path.join(a.model, 'vocab.json'))
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    st = torch.load(os.path.join(a.model, a.ckpt), map_location=dev)
    net = CRNN(len(vocab)).to(dev)
    net.load_state_dict(st['net'])
    net.eval()
    line_truth = build_line_truth(a.render, net, vocab, dev, voices)
    print(f'줄별 정답 {len(line_truth)}줄 역산 완료: ' +
          ' '.join(f'{vi + 1}성부{len(seq)}음' for vi, seq in line_truth))

    photos = sorted(glob.glob(os.path.join(a.photos, '*.jpg')))
    print(f"사진 {len(photos)}장 / 보정 {'끔' if a.no_correct else '켬'}",
          flush=True)
    ne = nt = 0
    det_hist = collections.Counter()
    v_ok = [0, 0]
    per_photo = []
    proofs = {}
    chose_on = 0
    for pi, ph in enumerate(photos):
        # extract_lines 는 위→아래 정렬된 (크롭, 중심y, 줄간격)을 준다
        def run(correct):
            res = photo_prep.extract_lines(ph, correct=correct, with_pos=True)
            crops = [c for c, _y, _g in res]
            centers = [y for _c, y, _g in res]
            norm = [prep.normalize_photo(c) for c in crops]
            if not norm:
                return crops, centers, [], 0.0
            hyps, confs, frames = decode_conf(net, norm, dev)
            conf = sum(c * f for c, f in zip(confs, frames)) \
                / max(1, sum(frames))
            return crops, centers, hyps, conf
        if a.auto:
            r_on = run(True)
            r_off = run(False)
            crops, centers, hyps, _c = r_on if r_on[3] >= r_off[3] else r_off
            chose_on += (r_on[3] >= r_off[3])
        else:
            crops, centers, hyps, _c = run(not a.no_correct)
        toks = [[tuple(vocab.itos[k]) for k in h if k > 0] for h in hyps]
        # 인식이 빈 보표(오검·잘린 조각)는 짝짓기 전에 뺀다 — 진짜 보표를
        # 놓친 경우라도 성부 편집거리에서 삭제 오류로 정직하게 남는다.
        keep = [i for i in range(len(crops)) if toks[i]]
        crops = [crops[i] for i in keep]
        centers = [centers[i] for i in keep]
        toks = [toks[i] for i in keep]
        det_hist[len(crops)] += 1
        # 줄 순서 보존 DP 정렬(evaluate_photo.align_lines 재사용) — 위→아래
        # 순서라는 확실한 구조를 쓰므로 보표 누락·유령이 그 줄 몫의
        # 오류로만 남고 사진 전체를 무너뜨리지 않는다.
        hyp_notes = [[(p, d) for p, d, _t in tk if p > 0] for tk in toks]
        refs = [seq for _vi, seq in line_truth]
        pairs = align_lines(refs, hyp_notes)
        pe = pt = 0
        assign = [[], []]
        for ri, hj in pairs:
            if ri is None:                       # 유령 보표 — 삽입 오류
                pe += len(hyp_notes[hj])
            elif hj is None:                     # 누락 보표 — 삭제 오류
                pe += len(refs[ri])
                pt += len(refs[ri])
            else:
                pe += edit(refs[ri], hyp_notes[hj])
                pt += len(refs[ri])
                vi = line_truth[ri][0]
                assign[vi].append(hj)
                v_ok[vi] += 1
        ne += pe
        nt += pt
        name = os.path.basename(ph)
        per_photo.append(dict(photo=name, staves=len(crops),
                              v1=len(assign[0]), v2=len(assign[1]),
                              err=pe, notes=pt, ner=pe / max(1, pt)))
        proofs[name] = ([[t for t in toks[i]] for i in assign[0]],
                        [[t for t in toks[i]] for i in assign[1]])
        if (pi + 1) % 10 == 0:
            print(f'  {pi + 1}/{len(photos)}', flush=True)

    ner = ne / max(1, nt)
    exp_staves = 7 * len(photos)
    print()
    print(f'■ 실물 음표 NER      {ner:.4%}   ({ne} / {nt}음)')
    print(f'■ 보표 검출 분포     {dict(sorted(det_hist.items()))} (기대 14)')
    print(f'■ 성부별 보표 추출   1성부 {v_ok[0]}/{exp_staves} '
          f'({v_ok[0] / exp_staves:.1%}) / 2성부 {v_ok[1]}/{exp_staves} '
          f'({v_ok[1] / exp_staves:.1%})')
    print(f'■ 관문 2 실물 (NER ≤ {a.gate:.0%}) '
          f'{"통과" if ner <= a.gate else "미달"}')
    srt = sorted(per_photo, key=lambda p: p['ner'])
    print('\n최고 3 / 최악 3:')
    for p in srt[:3] + srt[-3:]:
        print(f"  {p['ner']:7.2%}  {p['photo']} (보표 {p['staves']})")

    # 증명물 미디 — 최고·중앙·최악
    pick = [srt[0], srt[len(srt) // 2], srt[-1]][:a.proof]
    for p in pick:
        tag = p['photo'].replace('.jpg', '')
        pv = proofs[p['photo']]
        for vi in (0, 1):
            gt = voices_tok[vi]
            pred = [t for line in pv[vi] for t in line]
            write_midi(os.path.join(a.out, f'{tag}_v{vi + 1}__정답.mid'), gt)
            write_midi(os.path.join(a.out, f'{tag}_v{vi + 1}__모델.mid'), pred)
    print(f'\n■ 증명물 미디 {len(pick)}장×2성부×2 → {a.out}')

    if a.auto:
        print(f'■ 자동 선택          켬 {chose_on} / 끔 {len(photos) - chose_on}')
    tag = 'auto' if a.auto else ('off' if a.no_correct else 'on')
    rep = dict(photos=len(photos), ner_notes=ner, err=ne, notes=nt,
               correct=not a.no_correct, auto=a.auto, chose_on=chose_on,
               det_hist=dict(det_hist),
               v1_staves=v_ok[0], v2_staves=v_ok[1],
               expected_staves_per_voice=exp_staves,
               gate2_real_pass=bool(ner <= a.gate),
               ckpt_epoch=st.get('epoch'), per_photo=per_photo)
    json.dump(rep, open(os.path.join(a.out, f'gate2_canon_{tag}.json'), 'w',
                        encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"보고서 → {os.path.join(a.out, f'gate2_canon_{tag}.json')}")


if __name__ == '__main__':
    main()
