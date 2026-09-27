#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관문 3c — 빠르기 숫자 전용 판독기 (3차 설계).

본체 CRNN 은 오선간격 12px 정규화 입력이라 ~14px 숫자가 풀링에서 뭉개진다
(자릿수 NER 81.8% 실측). 여기서는 **원본(300DPI) 줄 이미지의 오선 위
밴드**에서 ♩=N 텍스트 블록을 잉크 프로파일로 꽉 잡아 잘라(숫자 높이
~25-35px) 소형 CRNN+CTC 가 자릿수를 읽는다. 본체는 마커([−5,0,0]) 검출만
맡는다(두 판 모두 100% 실측) — 판정은 마커 검출 × 숫자 판독 결합.

    # 1) 크롭 캐시
    python tools/omr_factory/tempo_head.py bake --data C:/Users/me/omr_lines3c
    # 2) 학습 (train/val 분할은 코퍼스 split 그대로)
    python tools/omr_factory/tempo_head.py train --data C:/Users/me/omr_lines3c \
        --out C:/Users/me/omr_tempo_head
    # 3) 시험 분할 숫자 정확도
    python tools/omr_factory/tempo_head.py eval --data C:/Users/me/omr_lines3c \
        --model C:/Users/me/omr_tempo_head
"""
import argparse
import json
import os
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep

H = 48                      # 크롭 정규화 높이 — 숫자가 ~25-35px 로 살아남는다
MAX_W = 640
N_CLASS = 11                # blank + 숫자 0..9


def crop_tempo(a, gap=None):
    """잉크배열(원본 해상도) → ♩=N 텍스트 크롭 (H,W) 또는 None.

    오선 위 [top−7g, top−0.3g] 밴드의 왼쪽(x<22g)에서 행 프로파일이 가장
    두꺼운 연속 블록(텍스트)을 찾아 세로로 꽉 잘라 높이 H 로 맞춘다.
    높은 덧줄 음의 기둥(1-2px)은 텍스트(≈8g 폭)보다 행 잉크가 훨씬 얇아
    문턱에서 걸러진다."""
    st = prep.find_staff(a)
    if st is None:
        return None
    cy, g = st
    if gap:
        g = gap
    top = cy - 2 * g
    y1 = int(max(0, top - 0.3 * g))
    y0 = int(max(0, top - 7.0 * g))
    x1 = int(min(a.shape[1], 22 * g))
    band = a[y0:y1, :x1]
    if band.size == 0:
        return None
    prof = band.sum(axis=1)
    if prof.max() < 2:
        return None                     # 밴드가 비었다 — 빠르기 없음
    rows = prof >= max(2.0, prof.max() * 0.25)
    # 가장 잉크가 많은 연속 블록
    best, cur, s0, acc = None, None, 0, 0.0
    for i, on in enumerate(list(rows) + [False]):
        if on:
            if cur is None:
                cur, acc = i, 0.0
            acc += prof[i]
        elif cur is not None:
            if best is None or acc > best[2]:
                best = (cur, i, acc)
            cur = None
    if best is None:
        return None
    b0, b1, _ = best
    pad = max(2, int(0.25 * g))
    b0, b1 = max(0, b0 - pad), min(band.shape[0], b1 + pad)
    blk = band[b0:b1]
    # 가로로도 꽉 자른다
    cprof = blk.sum(axis=0)
    xs = np.nonzero(cprof >= max(1.0, cprof.max() * 0.05))[0]
    if len(xs) == 0:
        return None
    blk = blk[:, max(0, xs[0] - pad):min(blk.shape[1], xs[-1] + pad)]
    if blk.shape[0] < 6 or blk.shape[1] < 12:
        return None
    w = max(16, min(MAX_W, int(round(blk.shape[1] * H / blk.shape[0]))))
    img = Image.fromarray((np.clip(blk, 0, 1) * 255).astype(np.uint8))
    return np.asarray(img.resize((w, H), Image.BILINEAR),
                      dtype=np.float32) / 255.0


class TempoNet(nn.Module):
    """소형 CRNN — (1, 48, W) → (T=W/8, 11) 로짓."""

    def __init__(self, n_class=N_CLASS, hidden=96):
        super().__init__()
        def blk(ci, co):
            return [nn.Conv2d(ci, co, 3, padding=1, bias=False),
                    nn.BatchNorm2d(co), nn.ReLU(inplace=True),
                    nn.MaxPool2d(2)]
        self.cnn = nn.Sequential(*blk(1, 32), *blk(32, 64), *blk(64, 96))
        self.proj = nn.Conv2d(96, 96, (H // 8, 1))
        self.rnn = nn.LSTM(96, hidden, 1, bidirectional=True, batch_first=True)
        self.fc = nn.Linear(hidden * 2, n_class)
        self.down = 8

    def forward(self, x):
        f = self.proj(self.cnn(x)).squeeze(2).transpose(1, 2)
        f, _ = self.rnn(f)
        return self.fc(f)

    def read(self, crop, dev):
        """크롭 (H,W) → 숫자 int 또는 None."""
        with torch.no_grad():
            x = torch.from_numpy(crop)[None, None].to(dev)
            lg = self(x)[0].argmax(-1).cpu().tolist()
        ds, prev = [], 0
        for k in lg:
            if k != prev and k != 0:
                ds.append(str(k - 1))
            prev = k
        return int(''.join(ds)) if ds else None


def load_rows(data, splits):
    out = []
    for ln in open(os.path.join(data, 'index.jsonl'), encoding='utf-8'):
        r = json.loads(ln)
        if r.get('bpm') and r['split'] in splits:
            out.append(r)
    return out


def bake(a):
    data, r = a
    dst = os.path.join(data, 'tempo_cache', r['cache'][6:])
    if os.path.exists(dst):
        return dict(ok=True, crop=dst, bpm=r['bpm'], split=r['split'])
    try:
        with Image.open(os.path.join(data, r['cache'][6:])) as im:   # 원본
            arr = 1.0 - np.asarray(im.convert('L'), dtype=np.float32) / 255.0
        c = crop_tempo(arr)
    except Exception:
        return dict(ok=False)
    if c is None:
        return dict(ok=False)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray((c * 255).astype(np.uint8)).save(dst, optimize=True)
    return dict(ok=True, crop=dst, bpm=r['bpm'], split=r['split'])


def cmd_bake(a):
    from concurrent.futures import ThreadPoolExecutor
    rows = load_rows(a.data, ('train', 'val', 'test'))
    print(f'빠르기 줄 {len(rows)}개 크롭', flush=True)
    n_ok = 0
    out = open(os.path.join(a.data, 'tempo_index.jsonl'), 'w', encoding='utf-8')
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, r in enumerate(ex.map(bake, ((a.data, x) for x in rows))):
            if r.get('ok'):
                n_ok += 1
                out.write(json.dumps(dict(crop=os.path.relpath(
                    r['crop'], a.data).replace('\\', '/'),
                    bpm=r['bpm'], split=r['split'])) + '\n')
            if (i + 1) % 2000 == 0:
                print(f'  {i + 1}/{len(rows)} ok {n_ok}', flush=True)
    out.close()
    print(f'끝: {n_ok}/{len(rows)}', flush=True)


def _load_index(data):
    rows = [json.loads(l) for l in
            open(os.path.join(data, 'tempo_index.jsonl'), encoding='utf-8')]
    for r in rows:
        with Image.open(os.path.join(data, r['crop'])) as im:
            r['_img'] = np.asarray(im, dtype=np.uint8)
    return rows


def _batchify(rows, bs, rng, aug):
    import dataset as D
    order = list(range(len(rows)))
    if rng is not None:
        rng.shuffle(order)
    for i in range(0, len(order), bs):
        ch = [rows[j] for j in order[i:i + bs]]
        W = max(r['_img'].shape[1] for r in ch)
        xs = np.zeros((len(ch), 1, H, W), dtype=np.float32)
        ys, yl = [], []
        for k, r in enumerate(ch):
            x = r['_img'].astype(np.float32) / 255.0
            if aug and rng is not None:
                x = D.augment(x, np.random.default_rng(), s=float(rng.random()) * 0.8)
                if x.shape != r['_img'].shape:
                    x = np.asarray(Image.fromarray((x * 255).astype(np.uint8))
                                   .resize(r['_img'].shape[::-1]),
                                   dtype=np.float32) / 255.0
            xs[k, 0, :, :x.shape[1]] = x
            ds = [int(c) + 1 for c in str(r['bpm'])]
            ys += ds
            yl.append(len(ds))
        yield (torch.from_numpy(xs), torch.tensor(ys, dtype=torch.long),
               torch.tensor(yl, dtype=torch.long),
               torch.tensor([r['_img'].shape[1] for r in ch]))


@torch.no_grad()
def _acc(net, rows, dev, bs=64):
    net.eval()
    ok = 0
    for xs, ys, yl, xw in _batchify(rows, bs, None, False):
        lg = net(xs.to(dev))
        best = lg.argmax(-1).cpu()
        off = 0
        for b in range(xs.shape[0]):
            T = max(1, int(xw[b]) // net.down)
            prev, ds = 0, []
            for t in range(min(T, best.shape[1])):
                k = int(best[b, t])
                if k != prev and k != 0:
                    ds.append(k - 1)
                prev = k
            want = ys[off:off + int(yl[b])].tolist()
            off += int(yl[b])
            ok += (ds == [w - 1 for w in want])
    net.train()
    return ok / max(1, len(rows))


def cmd_train(a):
    rows = _load_index(a.data)
    tr = [r for r in rows if r['split'] == 'train']
    va = [r for r in rows if r['split'] == 'val']
    print(f'학습 {len(tr)} / 검증 {len(va)}', flush=True)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    net = TempoNet().to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=1e-4)
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(1234)
    best = -1
    import random
    prng = random.Random(1234)
    for ep in range(a.epochs):
        run = nb = 0
        idx = list(range(len(tr)))
        prng.shuffle(idx)
        for xs, ys, yl, xw in _batchify(tr, a.batch, np.random.default_rng(ep),
                                        True):
            lg = net(xs.to(dev))
            lp = F.log_softmax(lg, dim=-1).transpose(0, 1)
            ol = torch.clamp(xw // net.down, min=1)
            loss = F.ctc_loss(lp, ys.to(dev), ol, yl, blank=0,
                              zero_infinity=True)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
            opt.step()
            run += loss.item()
            nb += 1
        acc = _acc(net, va, dev)
        print(f'ep{ep} loss {run / max(1, nb):.4f} val숫자정확도 {acc:.4f}',
              flush=True)
        torch.save(dict(net=net.state_dict(), epoch=ep, acc=acc),
                   os.path.join(a.out, 'last.pt'))
        if acc > best:
            best = acc
            torch.save(dict(net=net.state_dict(), epoch=ep, acc=acc),
                       os.path.join(a.out, 'best.pt'))
    print(f'끝. 최고 val 숫자정확도 {best:.4f}', flush=True)


def cmd_eval(a):
    rows = [r for r in _load_index(a.data) if r['split'] == 'test']
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    net = TempoNet().to(dev)
    st = torch.load(os.path.join(a.model, 'best.pt'), map_location=dev)
    net.load_state_dict(st['net'])
    net.eval()
    acc = _acc(net, rows, dev)
    print(json.dumps(dict(lines=len(rows), digit_num_acc=round(acc, 4),
                          ckpt_epoch=st.get('epoch')), ensure_ascii=False),
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['bake', 'train', 'eval'])
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default='C:/Users/user/omr_tempo_head')
    ap.add_argument('--model', default='C:/Users/user/omr_tempo_head')
    ap.add_argument('--epochs', type=int, default=8)
    ap.add_argument('--batch', type=int, default=32)
    a = ap.parse_args()
    dict(bake=cmd_bake, train=cmd_train, eval=cmd_eval)[a.cmd](a)


if __name__ == '__main__':
    main()
