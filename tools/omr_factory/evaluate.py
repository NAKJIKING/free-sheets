#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관문 1 판정 + 청음 증명물.

    python tools/omr_factory/evaluate.py --data C:/Users/me/omr_lines \
        --model C:/Users/me/omr_model --out C:/Users/me/omr_gate1

판정: **학습에 안 쓴 시험용 곡들의 깨끗한 렌더에서 음표 오류율(NER) 5% 이하.**
NER = Levenshtein(정답, 예측) / |정답음수|. DTW 는 쓰지 않는다 — 삽입·삭제를
표현 못 해 누락 음표를 은폐한다.

증명물: 엘리제(original:elise) 각 줄에 대해 예측 미디 / 정답 미디 두 개.
같은 빠르기·같은 악기로 내므로 귀로 바로 비교된다.
"""
import argparse
import collections
import json
import os
import struct
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as D
from model import CRNN, greedy_decode
from train import edit

Q = 12                       # 4분음표 = 12


# ───────────────────────────── 미디 쓰기 ─────────────────────────────

def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def write_midi(path, tokens, bpm=84, tpq=480, program=0):
    """(pitch, dur, tie) 토큰열 → 미디 한 트랙. 붙임줄은 한 음으로 병합한다."""
    # 병합
    merged, i = [], 0
    while i < len(tokens):
        p, d, tie = tokens[i]
        i += 1
        while tie and i < len(tokens) and tokens[i][0] == p:
            d += tokens[i][1]
            tie = tokens[i][2]
            i += 1
        merged.append((p, d))

    ev = bytearray()
    ev += b'\x00\xff\x51\x03' + struct.pack('>I', int(60_000_000 / bpm))[1:]
    ev += b'\x00\xc0' + bytes([program])
    rest = 0
    for p, d in merged:
        ticks = int(round(d * tpq / Q))
        if p == 0:
            rest += ticks
            continue
        ev += _vlq(rest) + bytes([0x90, p, 80])
        ev += _vlq(ticks) + bytes([0x80, p, 0])
        rest = 0
    ev += _vlq(rest) + b'\xff\x2f\x00'
    with open(path, 'wb') as f:
        f.write(b'MThd' + struct.pack('>IHHH', 6, 0, 1, tpq))
        f.write(b'MTrk' + struct.pack('>I', len(ev)) + bytes(ev))


# ───────────────────────────── 판정 ─────────────────────────────

@torch.no_grad()
def run(net, dl, dev):
    """(정답 인덱스열, 예측 인덱스열) 쌍 목록 — 줄 순서 유지."""
    out = []
    for x, xl, y, yl in dl:
        x = x.to(dev, non_blocking=True)
        with torch.autocast('cuda', dtype=torch.bfloat16, enabled=dev.type == 'cuda'):
            lg = net(x).float()
        hyp = greedy_decode(lg, net.out_len(xl))
        off = 0
        for i, n in enumerate(yl.tolist()):
            out.append((y[off:off + n].tolist(), hyp[i]))
            off += n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--split', default='test')
    ap.add_argument('--ckpt', default='best.pt')
    ap.add_argument('--batch', type=int, default=16)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--gate-song', default='original:elise')
    ap.add_argument('--bpm', type=int, default=84)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    vocab = D.Vocab.load(os.path.join(a.model, 'vocab.json'))
    # 시험에서는 어휘 밖 토큰이 있는 줄도 버리지 않는다 — 버리면 '아는 줄만'
    # 채점해 점수가 부풀려진다. 어휘 밖은 −1 로 남아 오류로 센다.
    rows, (drop, nunk) = D.load_rows(a.data, vocab, (a.split,), keep_unk=True)
    rows.sort(key=lambda r: (r['song'], r.get('var', ''), r['chunk'], r['shift']))
    print(f'{a.split} {len(rows)}줄 / 너무짧아 버림 {drop}줄 / '
          f'어휘밖 토큰 {nunk}개(오류로 계산) / 어휘 {len(vocab)}종')

    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    st = torch.load(os.path.join(a.model, a.ckpt), map_location=dev)
    net = CRNN(len(vocab)).to(dev)
    net.load_state_dict(st['net'])
    net.eval()
    print(f"체크포인트 에폭 {st.get('epoch')} 검증NER {st.get('ner')}")

    dl = D.ThreadLoader(D.Lines(a.data, rows, vocab, aug=0.0),
                        a.batch, D.collate, workers=a.workers)
    pairs = run(net, dl, dev)

    def notes_only(seq):
        return [k for k in seq if not vocab.is_rest(k)]

    ne = nt = ae = at = 0
    perfect = 0
    per_song = collections.defaultdict(lambda: [0, 0])
    for (ref, hyp), r in zip(pairs, rows):
        rn, hn = notes_only(ref), notes_only(hyp)
        e = edit(rn, hn)
        ne += e
        nt += len(rn)
        ae += edit(ref, hyp)
        at += len(ref)
        perfect += (e == 0)
        per_song[r['song']][0] += e
        per_song[r['song']][1] += len(rn)

    ner = ne / max(1, nt)
    ner_all = ae / max(1, at)
    print()
    print(f'■ 음표 NER          {ner:.4%}   ({ne} / {nt}음)')
    print(f'■ 쉼표포함 NER      {ner_all:.4%}   ({ae} / {at}토큰)')
    print(f'■ 무오류 줄         {perfect}/{len(rows)} = {perfect / max(1, len(rows)):.1%}')
    print(f'■ 시험 곡 수        {len(per_song)}')
    print(f'■ 관문 1 (NER ≤ 5%) {"통과" if ner <= 0.05 else "미달"}')

    worst = sorted(per_song.items(), key=lambda kv: -(kv[1][0] / max(1, kv[1][1])))[:10]
    print('\n오류율 높은 곡 10:')
    for s, (e, t) in worst:
        print(f'  {e / max(1, t):7.2%}  {s}  ({e}/{t})')

    # ── 증명물: 엘리제 예측/정답 미디
    made = []
    for (ref, hyp), r in zip(pairs, rows):
        if r['song'] != a.gate_song:
            continue
        tag = f"{r.get('var', 'x')}_c{r['chunk']:02d}_k{r['shift']:+d}".replace('+', 'p').replace('-', 'm')
        # 어휘 밖(−1)은 미디로 낼 수 없으므로 건너뛴다(개수는 보고에 남는다)
        gt = [tuple(vocab.itos[k]) for k in ref if k > 0]
        pr = [tuple(vocab.itos[k]) for k in hyp if k > 0]
        p1 = os.path.join(a.out, f'{tag}__정답.mid')
        p2 = os.path.join(a.out, f'{tag}__모델.mid')
        write_midi(p1, gt, bpm=a.bpm)
        write_midi(p2, pr, bpm=a.bpm)
        rn, hn = notes_only(ref), notes_only(hyp)
        made.append(dict(tag=tag, shift=r['shift'], notes=len(rn),
                         err=edit(rn, hn), gt=p1, pred=p2, png=r['cache']))

    if made:
        print(f'\n■ 엘리제 증명물 {len(made)}쌍 → {a.out}')
        for m in made:
            print(f"  {m['tag']}: 정답 {m['notes']}음 중 오류 {m['err']}"
                  f" ({m['err'] / max(1, m['notes']):.2%})")
    else:
        print(f'\n⚠ 시험곡 {a.gate_song} 이 {a.split} 에 없다')

    rep = dict(split=a.split, lines=len(rows), songs=len(per_song),
               ner_notes=ner, ner_all=ner_all, notes=nt, oov_tokens=nunk,
               perfect_lines=perfect, gate1_pass=bool(ner <= 0.05),
               ckpt_epoch=st.get('epoch'), elise=made,
               worst=[dict(song=s, ner=e / max(1, t), err=e, notes=t) for s, (e, t) in worst])
    json.dump(rep, open(os.path.join(a.out, 'gate1.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f"\n보고서 → {os.path.join(a.out, 'gate1.json')}")


if __name__ == '__main__':
    main()
