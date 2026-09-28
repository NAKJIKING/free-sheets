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


def crop_tempo(a, gap=None, xwin=None):
    """잉크배열(원본 해상도) → ♩=N 텍스트 크롭 (H,W) 또는 None.

    v2 (09-27): v1 은 x<22g 로 잘라 조표가 넓거나(올림표 6개) 오선이 작은
    판형에서 숫자가 창 밖에 잘렸다(val 78% 정체의 주범 — "♩ =" 까지만
    남은 크롭 실측). 지금은:
      ① 창을 x<45g 로 넓히고,
      ② 밴드에서 **가장 위의 진한 행 블록**을 고른다 — ♩=N 은 줄 머리
         구역에서 항상 최상단이고, 음자리표 꼭대기·올림표는 오선에 붙어
         아래쪽 블록이 된다(얇은 덧줄 기둥은 잉크 문턱에서 걸러짐),
      ③ 그 행 블록 안에서 열 클러스터(1.5g 넘는 공백으로 분리)를 만들어
         잉크가 가장 많은 덩어리(♩ = 숫자)만 남긴다.
    v3 (09-27): 높은 덧줄 음표 덩어리가 '최상단 블록'을 뺏는 사례(~10%,
    val 89% 정체의 주범)가 남아 **본체 마커의 CTC 프레임 x 를 앵커**로
    받는 xwin=(x0,x1) 을 지원 — 창 안에는 ♩=N 이 지배적이라 오인이 없다.
    학습·추론이 같은 앵커를 쓰므로 분포도 일치한다. xwin 없으면 v2 동작."""
    st = prep.find_staff(a)
    if st is None:
        return None
    cy, g = st
    if gap:
        g = gap
    top = cy - 2 * g
    y1 = int(max(0, top - 0.3 * g))
    y0 = int(max(0, top - 7.0 * g))
    if xwin is not None:
        wx0 = int(max(0, min(xwin[0], a.shape[1] - 12)))
        x1 = int(min(a.shape[1], max(xwin[1], wx0 + 12)))
    else:
        wx0 = 0
        x1 = int(min(a.shape[1], 45 * g))
    band = a[y0:y1, wx0:x1]
    if band.size == 0:
        return None
    prof = band.sum(axis=1)
    if prof.max() < 2:
        return None                     # 밴드가 비었다 — 빠르기 없음
    rows = prof >= max(2.0, prof.max() * 0.30)
    # 행 블록들 — 가장 위의, 충분히 진하고(피크 ≥ 0.45·최대) 충분히 높은
    # (≥0.5g) 블록을 고른다.
    blocks, cur = [], None
    for i, on in enumerate(list(rows) + [False]):
        if on and cur is None:
            cur = i
        elif not on and cur is not None:
            blocks.append((cur, i))
            cur = None
    pick = None
    for b0, b1 in blocks:
        if b1 - b0 >= 0.5 * g and prof[b0:b1].max() >= prof.max() * 0.45:
            pick = (b0, b1)
            break                       # 위에서부터 첫 후보 = 최상단
    if pick is None:
        return None
    cs = _cands_of_block(band, pick, g)
    return cs[0] if cs else None


def _cands_of_block(band, pick, g, k=2):
    """행 블록 하나 → 열 클러스터 상위 k 개의 최종 크롭 목록."""
    b0, b1 = pick
    pad = max(2, int(0.25 * g))
    b0, b1 = max(0, b0 - pad), min(band.shape[0], b1 + pad)
    blk0 = band[b0:b1]
    cprof = blk0.sum(axis=0)
    on = cprof >= max(1.0, cprof.max() * 0.05)
    clusters, cur, gap_run = [], None, 0
    for i, o in enumerate(list(on) + [False]):
        if o:
            if cur is None:
                cur = [i, i]
            cur[1] = i
            gap_run = 0
        elif cur is not None:
            gap_run += 1
            if gap_run > 1.5 * g or i == len(on):
                clusters.append(tuple(cur))
                cur = None
    clusters.sort(key=lambda c: -float(cprof[c[0]:c[1] + 1].sum()))
    out = []
    for c in clusters[:k]:
        blk = blk0[:, max(0, c[0] - pad):min(blk0.shape[1], c[1] + pad)]
        rp = blk.sum(axis=1)
        ys = np.nonzero(rp >= max(1.0, rp.max() * 0.05))[0]
        if len(ys):
            blk = blk[max(0, ys[0] - 2):min(blk.shape[0], ys[-1] + 3)]
        if blk.shape[0] < 6 or blk.shape[1] < 12:
            continue
        w = max(16, min(MAX_W, int(round(blk.shape[1] * H / blk.shape[0]))))
        img = Image.fromarray((np.clip(blk, 0, 1) * 255).astype(np.uint8))
        out.append(np.asarray(img.resize((w, H), Image.BILINEAR),
                              dtype=np.float32) / 255.0)
    return out


def crop_candidates(a, k=6):
    """줄 원본 → ♩=N 후보 크롭 목록 (행 블록 상위 2 × 열 클러스터 상위 2).

    v4 (09-27): 단일 휴리스틱(최상단/최대잉크)으로는 높은 덧줄 음표·음자리표
    와의 오인을 못 없앤다(v1 78%→v2 89% 정체). 후보를 여럿 만들고 판독기가
    자릿수 2개 이상 + 최고 신뢰도로 고른다 — bpm 은 40~208 이라 항상 2자리
    이상이고, 음표 덩어리가 자신있는 2자리 숫자로 읽히는 일은 드물다.
    (마커 CTC 프레임 앵커는 폐기 — BiLSTM CTC 는 마커를 글리프 위치가 아닌
    시퀀스 첫 프레임에 방출함을 실측.)
    실물 사진 크롭은 종이 톤(저강도 배경)을 **상시** 바닥 제거로 정규화
    (렌더는 바닥이 0이라 무변화)하고, 오선 찾기는 soft 모드로 폴백한다.
    학습 증강(_photo_wash)도 마지막에 같은 바닥 제거를 걸어 분포를 맞춘다."""
    lo = float(np.percentile(a, 60))
    if lo > 0.03:
        a = np.clip((a - lo) / max(1e-3, 1.0 - lo), 0, 1)
    st = prep.find_staff(a)
    if st is None:
        st = prep.find_staff(a, soft=True)
        if st is None:
            return []
    cy, g = st
    top = cy - 2 * g
    y1 = int(max(0, top - 0.3 * g))
    y0 = int(max(0, top - 7.0 * g))
    x1 = int(min(a.shape[1], 45 * g))
    band = a[y0:y1, :x1]
    if band.size == 0:
        return []
    prof = band.sum(axis=1)
    if prof.max() < 2:
        return []
    # 문턱은 상대(최대×비율)에 **절대 상한(오선간격 비례)** 을 건다 — 촘촘한
    # 16분음표 빔이 밴드에 들면 최대값을 지배해 얇은 ♩=N 텍스트 행이 문턱
    # 미달로 사라진다(elise 첼로 실측: 후보 전멸의 원인).
    rows = prof >= max(2.0, min(prof.max() * 0.22, 1.2 * g))
    blocks, cur = [], None
    for i, on in enumerate(list(rows) + [False]):
        if on and cur is None:
            cur = i
        elif not on and cur is not None:
            blocks.append((cur, i))
            cur = None
    qthr = max(2.0, min(prof.max() * 0.25, 2.5 * g))
    blocks = [(b0, b1) for b0, b1 in blocks
              if b1 - b0 >= 0.45 * g and prof[b0:b1].max() >= qthr]
    # 최상단 우선 + 잉크 최대 순 — 상위 3개 행 블록 × 클러스터 2 = 후보 ≤6.
    # 후보가 늘어도 안전한 근거: 선택기는 '자릿수 2개 이상 + 최고 신뢰도'라
    # 음표·볼타 숫자(1자리)는 탈락하고, 400줄 실측에서 선택 실수 0이었다.
    ordered = blocks[:1] + sorted(blocks[1:],
                                  key=lambda b: -float(prof[b[0]:b[1]].sum()))
    out = []
    for b in ordered[:3]:
        out.extend(_cands_of_block(band, b, g))
        if len(out) >= k:
            break
    return out[:k]


BPM_LO, BPM_HI = 30, 280        # 타당한 bpm 범위 — 부제목 숫자 등 쓰레기 차단


def repair_num(n):
    """자릿수열 → 타당 bpm. 범위 초과면 꼬리를 자른다 — 셋잇단 ₃ 가 숫자
    바로 옆에 붙어 같은 클러스터로 잘리는 실물 지면 실측('72'+'3'→723).
    72₃→723→72, 108₃→1083→108. 못 고치면 None."""
    s = str(n)
    while s and not (BPM_LO <= int(s) <= BPM_HI):
        s = s[:-1]
        if not s or len(s) < 2:
            return None
    return int(s) if s else None


@torch.no_grad()
def parse_num(net, crop, dev, min_digits=2):
    """크롭 하나 → (복원된 bpm 또는 None, 신뢰도).

    신뢰도 = 방출(비공백) 프레임들의 로그확률 평균."""
    x = torch.from_numpy(crop)[None, None].to(dev)
    lg = torch.log_softmax(net(x)[0], dim=-1).cpu()
    ids = lg.argmax(-1)
    ds, confs, prev = [], [], 0
    for t in range(ids.shape[0]):
        k_ = int(ids[t])
        if k_ != prev and k_ != 0:
            ds.append(str(k_ - 1))
            confs.append(float(lg[t, k_]))
        prev = k_
    if len(ds) < min_digits:
        return None, -1e9
    num = repair_num(int(''.join(ds)))
    if num is None:
        return None, -1e9
    return num, sum(confs) / len(confs)


def read_best(net, cands, dev, min_digits=2):
    """후보 크롭들 → 타당 bpm 최고 신뢰도 후보."""
    best = (None, -1e9)
    for c in cands:
        num, conf = parse_num(net, c, dev, min_digits)
        if num is not None and conf > best[1]:
            best = (num, conf)
    return best[0]


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


def anchor_window(arr, xn):
    """정규화 x(마커 CTC 프레임 중심) → 원본 좌표 크롭 창 (x0, x1)."""
    st = prep.find_staff(arr)
    if st is None or xn is None:
        return None
    g = st[1]
    xo = xn * g / 12.0                  # normalize 는 오선간격을 12px 로 맞춘다
    return (xo - 4 * g, xo + 13 * g)


@torch.no_grad()
def marker_anchors(net, vocab, data, rows, dev, batch=16):
    """본체 CRNN 으로 캐시 이미지를 디코드해 마커 프레임의 정규화 x 목록."""
    mid = vocab.stoi.get((-5, 0, 0))
    assert mid, '본체 어휘에 마커가 없다'
    out = []
    for k in range(0, len(rows), batch):
        ch = rows[k:k + batch]
        imgs = []
        for r in ch:
            with Image.open(os.path.join(data, r['cache'])) as im:
                imgs.append(np.asarray(im.convert('L'),
                                       dtype=np.float32) / 255.0)
        W = max(x.shape[1] for x in imgs)
        xs = torch.zeros(len(imgs), 1, imgs[0].shape[0], W)
        for i, x in enumerate(imgs):
            xs[i, 0, :, :x.shape[1]] = torch.from_numpy(x)
        best = net(xs.to(dev)).argmax(-1).cpu()
        for i, x in enumerate(imgs):
            T = max(1, x.shape[1] // net.down)
            xn = None
            for t in range(min(T, best.shape[1])):
                if int(best[i, t]) == mid:
                    xn = (t + 0.5) * net.down
                    break
            out.append(xn)
        if (k // batch) % 100 == 0:
            print(f'  앵커 {k + len(ch)}/{len(rows)}', flush=True)
    return out


def _cands_job(a):
    data, r = a
    try:
        with Image.open(os.path.join(data, r['cache'][6:])) as im:   # 원본
            arr = 1.0 - np.asarray(im.convert('L'), dtype=np.float32) / 255.0
        return r, crop_candidates(arr)
    except Exception:
        return r, []


def cmd_bake(a):
    """후보 크롭 생성 + (--reader 시) 정답 bpm 과 일치하는 후보 선택 저장.

    v4: 판독기로 후보 ≤4개를 읽어 **정답 bpm 을 읽어낸 후보만** 저장 —
    라벨과 그림이 어긋난 크롭(음자리표·높은 음표 오인)이 학습에서 사라진다.
    일치 후보가 없으면 그 줄은 버린다(개수 보고). --reader 없으면 첫
    후보(v2 휴리스틱)를 그대로 저장한다(부트스트랩 1회차용)."""
    from concurrent.futures import ThreadPoolExecutor
    rows = load_rows(a.data, ('train', 'val', 'test'))
    print(f'빠르기 줄 {len(rows)}개 크롭 (reader={bool(a.reader)})', flush=True)
    net = dev = None
    if a.reader:
        dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        net = TempoNet().to(dev)
        st = torch.load(os.path.join(a.reader, 'best.pt'), map_location=dev)
        net.load_state_dict(st['net'])
        net.eval()
    n_ok = n_drop = 0
    out = open(os.path.join(a.data, 'tempo_index.jsonl'), 'w', encoding='utf-8')
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for i, (r, cands) in enumerate(
                ex.map(_cands_job, ((a.data, x) for x in rows))):
            pick = None
            if not cands:
                n_drop += 1
            elif net is None:
                pick = cands[0]
            else:
                for c in cands:
                    if parse_num(net, c, dev)[0] == r['bpm']:
                        pick = c
                        break
                if pick is None:
                    n_drop += 1
            if pick is not None:
                dst = os.path.join(a.data, 'tempo_cache', r['cache'][6:])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                Image.fromarray((pick * 255).astype(np.uint8)) \
                     .save(dst, optimize=True)
                n_ok += 1
                out.write(json.dumps(dict(crop=os.path.relpath(
                    dst, a.data).replace('\\', '/'),
                    bpm=r['bpm'], split=r['split'])) + '\n')
            if (i + 1) % 2000 == 0:
                print(f'  {i + 1}/{len(rows)} ok {n_ok} drop {n_drop}',
                      flush=True)
    out.close()
    print(f'끝: {n_ok}/{len(rows)} (탈락 {n_drop})', flush=True)


def _photo_wash(x, rng):
    """실물 사진풍 열화 — 잉크 약화·배경 상승·종이결·기울임·블러·모션·JPEG.

    마지막에 crop_candidates 와 **같은 바닥 제거**를 걸어 추론 분포와 맞춘다.
    (실물 빠르기 벤치 5/43 의 처방 — 판독기가 렌더 전용 학습이던 것.)"""
    from PIL import ImageFilter
    h, w = x.shape
    x = x * rng.uniform(0.55, 0.95)                    # 잉크 약화
    bg = rng.uniform(0.03, 0.25)                       # 배경 상승
    small = rng.random((max(2, h // 8), max(2, w // 8))).astype(np.float32)
    tex = np.asarray(Image.fromarray((small * 255).astype(np.uint8))
                     .resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
    x = np.clip(x + bg * (1 - x) + (tex - 0.5) * 0.08, 0, 1)
    img = Image.fromarray((x * 255).astype(np.uint8))
    ang = rng.normal(0, 1.2)
    img = img.rotate(ang, resample=Image.BILINEAR, fillcolor=0, expand=False)
    r = abs(rng.normal(0, 0.7))
    if r > 0.15:
        img = img.filter(ImageFilter.GaussianBlur(r))
    x = np.asarray(img, dtype=np.float32) / 255.0
    if rng.random() < 0.3:                             # 손떨림
        L_ = rng.uniform(1.5, 4.0)
        steps = max(2, int(L_))
        th = rng.uniform(0, np.pi)
        dx, dy = np.cos(th), np.sin(th)
        acc = np.zeros_like(x)
        for k in range(steps):
            t = k - (steps - 1) / 2.0
            acc += np.roll(np.roll(x, int(round(t * dy)), 0),
                           int(round(t * dx)), 1)
        x = acc / steps
    x = np.clip(x + rng.normal(0, 0.03, x.shape).astype(np.float32), 0, 1)
    f = rng.uniform(1.0, 1.8)                          # 다운샘플/JPEG
    if f > 1.05:
        img = Image.fromarray((x * 255).astype(np.uint8))
        img = img.resize((max(12, int(w / f)), max(8, int(h / f))),
                         Image.BILINEAR)
        import io
        b = io.BytesIO()
        img.save(b, 'JPEG', quality=int(rng.uniform(40, 90)))
        b.seek(0)
        img = Image.open(b).convert('L').resize((w, h), Image.BILINEAR)
        x = np.asarray(img, dtype=np.float32) / 255.0
    lo = float(np.percentile(x, 60))                   # 추론과 동일 바닥 제거
    if lo > 0.03:
        x = np.clip((x - lo) / max(1e-3, 1.0 - lo), 0, 1)
    return x


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
                g2 = np.random.default_rng()
                if g2.random() < 0.5:              # 실물 사진풍 (v5)
                    x = _photo_wash(x, g2)
                else:                              # 기존 렌더 열화
                    x = D.augment(x, g2, s=float(rng.random()) * 0.8)
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
    ap.add_argument('--reader', default='',
                    help='후보 선택용 현 판독기 폴더(v4 부트스트랩)')
    ap.add_argument('--epochs', type=int, default=8)
    ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--jobs', type=int, default=8, help='bake 병렬 스레드')
    a = ap.parse_args()
    dict(bake=cmd_bake, train=cmd_train, eval=cmd_eval)[a.cmd](a)


if __name__ == '__main__':
    main()
