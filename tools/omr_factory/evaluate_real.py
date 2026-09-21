#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관문 2 실물 폰사진 평가 — 곡 라벨 없는 사진의 자동 매칭 채점.

    python tools/omr_factory/evaluate_real.py \
        --photos C:/Users/me/omr_photo_real --model C:/Users/me/omr_model_g2 \
        --out C:/Users/me/omr_gate2_real [--no-correct]

사진에 곡명이 없으므로:
  ① 사진의 각 검출 줄을 인식 → 음표열을 **음정(Δ음높이) 열**로 바꿔
     조옮김 불변으로 라이브러리 전 곡(시프트 0 대표)과 대조한다.
     사전선별은 Δ음높이 3그램 겹침, 본판정은 안맞춤(infix) 편집거리 —
     짧은 쪽이 긴 쪽 안 어디에 끼어도 좋다(발췌·페이지 중간 줄 대응).
  ② 줄별 최적 곡의 다수결로 사진의 곡을 정하고, 그 곡의 12개 조 원본과
     절대 음높이로 재정렬해 최종 NER 을 잰다.
  ③ 잘 맞는 곡이 없는 줄(적합비 > 0.5)은 '미매칭'(반주 보표·정답 밖 구간)
     — NER 모수에서 빼되 개수를 정직하게 보고한다.
  ④ 매칭 줄이 2개 미만이거나 다수결 동률인 사진은 '애매' 목록으로 분리.

주의: 실물 NER 은 **우리 정답이 존재하는(매칭된) 멜로디 줄**에서만 잰
값이다 — 반주(왼손) 보표와 라이브러리 밖 구간은 채점 불가.
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
from evaluate_photo import decode_crops
from model import CRNN

TOPK = 40                # 사전선별 후보 수
FIT_MAX = 0.5            # 이보다 적합비 나쁘면 미매칭


def infix_edit(q, r):
    """q 를 r 안 어디든 끼워 맞추는 최소 편집거리(양끝 자유)."""
    if not q:
        return 0
    prev = [0] * (len(r) + 1)
    for i, x in enumerate(q, 1):
        cur = [i]
        for j, y in enumerate(r, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return min(prev)


def notes_of(tokens):
    return [(p, d) for p, d, _t in tokens if p > 0]


def iv_seq(notes):
    """[(pitch, dur)] → 조옮김 불변 [(Δpitch, dur)] (첫 음은 Δ=0)."""
    return [(0 if i == 0 else n[0] - notes[i - 1][0], n[1])
            for i, n in enumerate(notes)]


def build_refs(data):
    """index.jsonl → 곡별 참조. 반환: (곡 목록, 3그램 색인, 곡→시프트→음표열)."""
    by = collections.defaultdict(dict)          # song -> shift -> [(chunk, tokens)]
    for ln in open(os.path.join(data, 'index.jsonl'), encoding='utf-8'):
        r = json.loads(ln)
        by[r['song']].setdefault(r['shift'], []).append(
            (r['chunk'], [tuple(t) for t in r['tokens']]))
    songs, gram_idx, notes_by = [], collections.defaultdict(set), {}
    for song, shifts in by.items():
        per = {}
        for sh, chunks in shifts.items():
            seq = []
            for _c, toks in sorted(chunks):
                seq += notes_of(toks)
            if len(seq) >= 4:
                per[sh] = seq
        if 0 not in per:
            continue
        si = len(songs)
        songs.append(song)
        notes_by[song] = per
        iv = [dp for dp, _d in iv_seq(per[0])]
        for k in range(len(iv) - 2):
            gram_idx[tuple(iv[k:k + 3])].add(si)
    return songs, gram_idx, notes_by


def match_line(hyp_notes, songs, gram_idx, notes_by):
    """줄 하나 → (곡, 시프트, 오류수, 정답음수, 적합비) 또는 None."""
    if len(hyp_notes) < 4:
        return None
    q = iv_seq(hyp_notes)
    iv = [dp for dp, _d in q]
    votes = collections.Counter()
    for k in range(len(iv) - 2):
        for si in gram_idx.get(tuple(iv[k:k + 3]), ()):
            votes[si] += 1
    best = None
    for si, _v in votes.most_common(TOPK):
        song = songs[si]
        r = iv_seq(notes_by[song][0])
        a, b = (q, r) if len(q) <= len(r) else (r, q)
        fit = infix_edit(a, b) / max(1, len(a))
        if best is None or fit < best[1]:
            best = (song, fit)
    if best is None or best[1] > FIT_MAX:
        return None
    song = best[0]
    # 절대 음높이로 12개 조 재판정 — 최종 NER 은 여기서 나온다
    fin = None
    for sh, ref in notes_by[song].items():
        a, b = (hyp_notes, ref) if len(hyp_notes) <= len(ref) \
            else (ref, hyp_notes)
        e = infix_edit(a, b)
        if fin is None or e < fin[1]:
            fin = (sh, e, len(a))
    return (song, fin[0], fin[1], fin[2], best[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--photos', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--data', default='C:/Users/user/omr_lines')
    ap.add_argument('--out', required=True)
    ap.add_argument('--ckpt', default='best.pt')
    ap.add_argument('--gate', type=float, default=0.10)
    ap.add_argument('--no-correct', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    vocab = D.Vocab.load(os.path.join(a.model, 'vocab.json'))
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    st = torch.load(os.path.join(a.model, a.ckpt), map_location=dev)
    net = CRNN(len(vocab)).to(dev)
    net.load_state_dict(st['net'])
    net.eval()
    songs, gram_idx, notes_by = build_refs(a.data)
    print(f"곡 {len(songs)} 참조 구축 / 체크포인트 에폭 {st.get('epoch')} "
          f"/ 보정 {'끔' if a.no_correct else '켬'}", flush=True)

    photos = sorted(glob.glob(os.path.join(a.photos, '*.jpg')))
    ne = nt = 0
    matched = unmatched = 0
    per_photo, ambiguous = [], []
    for pi, ph in enumerate(photos):
        crops = photo_prep.load_photo_lines(ph, correct=not a.no_correct)
        hyps = decode_crops(net, crops, dev) if crops else []
        rows = []
        for h in hyps:
            toks = [tuple(vocab.itos[k]) for k in h if k > 0]
            m = match_line(notes_of(toks), songs, gram_idx, notes_by)
            rows.append(m)
        good = [m for m in rows if m]
        matched += len(good)
        unmatched += len(rows) - len(good)
        vote = collections.Counter(m[0] for m in good)
        top = vote.most_common(2)
        amb = (len(good) < 2
               or (len(top) > 1 and top[0][1] == top[1][1]))
        name = os.path.basename(ph)
        if amb:
            ambiguous.append(dict(photo=name, lines=len(rows),
                                  matched=len(good),
                                  votes={s: c for s, c in top}))
        song = top[0][0] if top else None
        pe = pt = 0
        for m in good:
            if song and m[0] == song:
                pe += m[2]
                pt += m[3]
        ne += pe
        nt += pt
        per_photo.append(dict(photo=name, song=song, lines=len(rows),
                              matched=len(good), err=pe, notes=pt,
                              ner=pe / max(1, pt), ambiguous=amb))
        if (pi + 1) % 10 == 0:
            print(f'  {pi + 1}/{len(photos)}', flush=True)

    ner = ne / max(1, nt)
    print()
    print(f'■ 실물 음표 NER(매칭 줄) {ner:.4%}   ({ne} / {nt}음)')
    print(f'■ 줄 매칭               {matched}줄 매칭 / {unmatched}줄 미매칭'
          f'(반주·정답밖·인식불능)')
    print(f'■ 애매한 사진           {len(ambiguous)}/{len(photos)}장')
    print(f'■ 관문 2 실물 (NER ≤ {a.gate:.0%}) '
          f'{"통과" if ner <= a.gate else "미달"}')
    sc = collections.Counter(p['song'] for p in per_photo
                             if p['song'] and not p['ambiguous'])
    print('\n매칭된 곡 분포:')
    for s, c in sc.most_common():
        print(f'  {c:2d}장  {s}')
    rep = dict(photos=len(photos), ner_notes=ner, err=ne, notes=nt,
               matched_lines=matched, unmatched_lines=unmatched,
               correct=not a.no_correct, gate=a.gate,
               gate2_real_pass=bool(ner <= a.gate),
               ckpt_epoch=st.get('epoch'), ambiguous=ambiguous,
               per_photo=per_photo)
    tag = 'off' if a.no_correct else 'on'
    json.dump(rep, open(os.path.join(a.out, f'gate2_real_{tag}.json'), 'w',
                        encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n보고서 → {os.path.join(a.out, f'gate2_real_{tag}.json')}")


if __name__ == '__main__':
    main()
