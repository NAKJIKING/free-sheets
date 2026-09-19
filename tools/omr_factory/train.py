#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRNN+CTC 학습.

    python tools/omr_factory/train.py --data C:/Users/me/omr_lines \
        --out C:/Users/me/omr_model --epochs 30 --batch 16 --aug 0.35

  - 곡 단위 분할(split.json)을 그대로 쓴다 — 여기서 섞지 않는다.
  - 증강은 학습 시점에 즉석 적용(dataset.augment, 순서 고정).
  - 에폭마다 검증 NER 을 재고 최고점만 저장(best.pt) + 매 에폭 last.pt
    → 중간에 끊겨도 이어서 할 수 있다(--resume).
"""
import argparse
import json
import os
import sys
import time

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as D
from model import CRNN, greedy_decode


def edit(a, b):
    """Levenshtein — 삽입·삭제를 세야 누락 음표가 드러난다(DTW 금지)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


@torch.no_grad()
def validate(net, dl, dev, vocab, cap=None):
    net.eval()
    err = tot = lines = perfect = 0
    for bi, (x, xl, y, yl) in enumerate(dl):
        if cap and bi >= cap:
            break
        x = x.to(dev, non_blocking=True)
        with torch.autocast('cuda', dtype=torch.bfloat16, enabled=dev.type == 'cuda'):
            lg = net(x).float()
        ol = net.out_len(xl)
        hyp = greedy_decode(lg, ol)
        off = 0
        for i, n in enumerate(yl.tolist()):
            ref = y[off:off + n].tolist()
            off += n
            # 음표만 세는 NER — 쉼표 토큰은 뺀다(보고에는 둘 다 적는다)
            rn = [k for k in ref if not vocab.is_rest(k)]
            hn = [k for k in hyp[i] if not vocab.is_rest(k)]
            e = edit(rn, hn)
            err += e
            tot += len(rn)
            lines += 1
            perfect += (e == 0)
    net.train()
    if lines == 0 or tot == 0:
        return None, None, 0        # 검증셋이 비었다 — 0.0 으로 보고하면 안 된다
    return err / tot, perfect / lines, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--epochs', type=int, default=30)
    ap.add_argument('--batch', type=int, default=16)
    ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--aug', type=float, default=0.35)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--hidden', type=int, default=256)
    ap.add_argument('--max-w', type=int, default=2600)
    ap.add_argument('--val-batches', type=int, default=60)
    ap.add_argument('--resume', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    raw = D.load_rows(a.data, None, ('train',))
    vpath = os.path.join(a.out, 'vocab.json')
    if a.resume and os.path.exists(vpath):
        vocab = D.Vocab.load(vpath)
    else:
        vocab, seen = D.build_vocab(raw)
        vocab.save(vpath)
        print(f'어휘 {len(vocab)}종 (blank 포함) / 최빈 {list(seen.items())[:3]}')
    tr, d1 = D.load_rows(a.data, vocab, ('train',))
    va, (d2, u2) = D.load_rows(a.data, vocab, ('val',), keep_unk=True)
    print(f'학습 {len(tr)}줄(버림 {d1}) / 검증 {len(va)}줄(버림 {d2}, 어휘밖 토큰 {u2})')
    if not va:
        print('⚠ 검증셋이 비었다 — split.json 을 확인할 것', flush=True)

    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    net = CRNN(len(vocab), hidden=a.hidden).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    start, best = 0, 9e9
    ck = os.path.join(a.out, 'last.pt')
    if a.resume and os.path.exists(ck):
        s = torch.load(ck, map_location=dev)
        net.load_state_dict(s['net'])
        opt.load_state_dict(s['opt'])
        start, best = s['epoch'] + 1, s.get('best', 9e9)
        print(f'이어서 학습: 에폭 {start} 부터, 최고 NER {best:.4f}')

    # 긴 줄이 한 배치에 몰리면 패딩이 낭비된다 → 폭으로 정렬해 묶는다
    tr.sort(key=lambda r: r['w'])
    dtr = D.ThreadLoader(D.Lines(a.data, tr, vocab, aug=a.aug, max_w=a.max_w),
                         a.batch, D.collate, shuffle=True, workers=a.workers,
                         drop_last=True, seed=1234)
    dva = D.ThreadLoader(D.Lines(a.data, va, vocab, aug=0.0, max_w=a.max_w),
                         a.batch, D.collate, workers=max(2, a.workers // 2))
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=a.lr, total_steps=max(1, a.epochs * len(dtr)),
        pct_start=0.08, last_epoch=start * len(dtr) - 1 if start else -1)

    log = open(os.path.join(a.out, 'train_log.jsonl'), 'a', encoding='utf-8')
    for ep in range(start, a.epochs):
        t0, run, nb = time.time(), 0.0, 0
        for x, xl, y, yl in dtr:
            x = x.to(dev, non_blocking=True)
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=dev.type == 'cuda'):
                lg = net(x)
            lp = F.log_softmax(lg.float(), dim=-1).transpose(0, 1)   # (T, B, C)
            ol = net.out_len(xl)
            loss = F.ctc_loss(lp, y, ol, yl, blank=D.BLANK,
                              zero_infinity=True, reduction='mean')
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
            opt.step()
            sched.step()
            run += loss.detach().item()
            nb += 1
            if nb % 200 == 0:
                print(f'  ep{ep} {nb}/{len(dtr)} loss {run / nb:.4f} '
                      f'{(time.time() - t0) / nb:.3f}s/step', flush=True)
        ner, perf, nl = validate(net, dva, dev, vocab, cap=a.val_batches)
        msg = dict(epoch=ep, loss=round(run / max(1, nb), 4),
                   val_ner=None if ner is None else round(ner, 5),
                   val_perfect=None if perf is None else round(perf, 4),
                   val_lines=nl, sec=round(time.time() - t0))
        print('에폭', msg, flush=True)
        log.write(json.dumps(msg) + '\n')
        log.flush()
        torch.save(dict(net=net.state_dict(), opt=opt.state_dict(), epoch=ep,
                        best=best if ner is None else min(best, ner),
                        vocab=len(vocab)), ck)
        if ner is not None and ner < best:
            best = ner
            torch.save(dict(net=net.state_dict(), epoch=ep, ner=ner,
                            vocab=len(vocab)), os.path.join(a.out, 'best.pt'))
            print(f'  ↑ 최고 갱신 NER {ner:.4f}', flush=True)
        # 윈도우에서 프로세스 커밋이 에폭당 수 GB 씩 비대해져(힙 단편화 양상) 페이지파일을
        # 부풀린다 → OMR_EPOCHS_PER_RUN 에폭마다 계획 종료하고 감독기가 --resume 재시작해
        # 커밋을 리셋한다. 0/미설정이면 기존처럼 끝까지 돈다.
        per_run = int(os.environ.get('OMR_EPOCHS_PER_RUN', '0'))
        if per_run and ep - start + 1 >= per_run:
            print(f'에폭 {ep} 저장 완료 — 계획 종료(OMR_EPOCHS_PER_RUN={per_run}), 감독기가 재시작한다', flush=True)
            break
    print('끝. 최고 검증 NER ' + ('없음' if best > 8e8 else f'{best:.4f}'), flush=True)


if __name__ == '__main__':
    main()
