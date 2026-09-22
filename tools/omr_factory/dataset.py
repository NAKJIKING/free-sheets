# -*- coding: utf-8 -*-
"""학습 데이터셋 + 증강.

증강 순서는 연구문서의 실측 순서를 그대로 따른다 — **바꾸면 안 된다**:
  기하 → 잉크 → 종이결 → 조명 → 광학 → 센서 → 다운샘플/JPEG (마지막)
순서가 중요한 이유: 실제 카메라가 그 순서로 망가뜨린다. 잡음을 먼저 넣고
흐리면 잡음이 번져 실사와 다른 그림이 된다.

토큰 어휘는 **학습 조각에 실제로 나온 (음고, 길이) 조합만** 쓴다
(연구문서 실측 고유 토큰 394종). 안 나온 조합까지 넣으면 출력층이 헛돈다.
"""
import json
import os

import numpy as np
import torch
from PIL import Image, ImageFilter
from torch.utils.data import Dataset

import prep

BLANK = 0                       # CTC 공백


class Vocab:
    def __init__(self, toks):
        self.itos = [None] + list(toks)          # 0 = blank
        self.stoi = {t: i for i, t in enumerate(self.itos) if t is not None}

    def __len__(self):
        return len(self.itos)

    def encode(self, tokens, unk=None):
        """unk=None: 어휘 밖 토큰이 하나라도 있으면 None(그 줄을 버린다).
        unk=-1:   어휘 밖 토큰을 −1 로 둔다 — **시험·검증에서 이걸 쓴다.**
                  버리면 '어휘가 아는 줄만' 채점해 점수가 부풀려진다.
                  −1 은 어떤 예측과도 같지 않으므로 정직하게 오류로 센다."""
        out = []
        for p, d, tie in tokens:
            # 붙임줄도 악보에 보이는 표기이므로 토큰에 넣는다 — 안 넣으면
            # 재생 미디에서 이어진 두 음이 끊겨 다시 소리난다.
            i = self.stoi.get((p, d, tie))
            if i is None:
                if unk is None:
                    return None
                i = unk
            out.append(i)
        return out

    def is_rest(self, k):
        return k > 0 and self.itos[k][0] == 0

    def save(self, path):
        json.dump([list(t) for t in self.itos[1:]], open(path, 'w'), indent=0)

    @staticmethod
    def load(path):
        return Vocab([tuple(t) for t in json.load(open(path))])


def build_vocab(rows):
    seen = {}
    for r in rows:
        for p, d, t in r['tokens']:
            seen[(p, d, t)] = seen.get((p, d, t), 0) + 1
    toks = sorted(seen, key=lambda t: (-seen[t], t))
    return Vocab(toks), seen


# ───────────────────────────── 증강 ─────────────────────────────

def _geom(img, rng, s):
    """기하 — 기울임·전단·가로세로 비율. 종이가 비뚤게 놓인 것."""
    ang = rng.normal(0, 0.8 * s)
    sh = rng.normal(0, 0.012 * s)
    w, h = img.size
    img = img.rotate(ang, resample=Image.BILINEAR, fillcolor=0, expand=False)
    if abs(sh) > 1e-4:
        img = img.transform((w, h), Image.AFFINE, (1, sh, -sh * h / 2, 0, 1, 0),
                            resample=Image.BILINEAR, fillcolor=0)
    return img


def _ink(a, rng, s):
    """잉크 — 선 굵기. 토너 농담·복사 세대차."""
    k = rng.uniform(-1, 1) * s
    if k > 0.25:
        a = np.clip(a * (1 + 0.6 * k), 0, 1)      # 번짐
    elif k < -0.25:
        a = np.clip((a - 0.25 * -k) / (1 - 0.25 * -k), 0, 1)   # 가늘어짐
    return a


def _paper(a, rng, s):
    """종이결 — 저주파 얼룩 + 미세 결. ScoreAug 의 실제 빈 종이 질감 대용."""
    h, w = a.shape
    small = rng.random((max(2, h // 24), max(2, w // 24))).astype(np.float32)
    tex = np.asarray(Image.fromarray((small * 255).astype(np.uint8))
                     .resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
    return np.clip(a + (tex - 0.5) * 0.10 * s * (1 - a), 0, 1)


def _light(a, rng, s):
    """조명 — 한쪽이 어두운 그라데이션(그림자·플래시 반사)."""
    h, w = a.shape
    gx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    gy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    amp = 0.25 * s
    g = 1.0 - amp * (rng.uniform(-1, 1) * gx + rng.uniform(-1, 1) * gy)
    return np.clip(a * g, 0, 1)


def _optics(img, rng, s):
    """광학 — 초점 흐림."""
    r = abs(rng.normal(0, 0.55 * s))
    return img.filter(ImageFilter.GaussianBlur(r)) if r > 0.12 else img


def _sensor(a, rng, s):
    """센서 — 가우시안 잡음."""
    return np.clip(a + rng.normal(0, 0.035 * s, a.shape).astype(np.float32), 0, 1)


def _down_jpeg(img, rng, s):
    """다운샘플/JPEG — **반드시 마지막**. 저해상도 촬영 + 압축 얼룩."""
    w, h = img.size
    f = rng.uniform(1.0, 1.0 + 0.6 * s)
    if f > 1.03:
        img = img.resize((max(8, int(w / f)), max(8, int(h / f))), Image.BILINEAR)
    q = int(rng.uniform(95 - 45 * s, 96))
    if q < 94:
        import io
        b = io.BytesIO()
        img.convert('L').save(b, 'JPEG', quality=max(20, q))
        b.seek(0)
        img = Image.open(b).convert('L')
    if img.size != (w, h):
        img = img.resize((w, h), Image.BILINEAR)
    return img


def augment(x, rng, s=1.0):
    """(H, W) 잉크배열 0~1 → 증강된 같은 모양 배열. s 는 세기(0 이면 원본)."""
    if s <= 0:
        return x
    img = Image.fromarray((x * 255).astype(np.uint8))
    img = _geom(img, rng, s)                                  # 1 기하
    a = np.asarray(img, dtype=np.float32) / 255.0
    a = _ink(a, rng, s)                                       # 2 잉크
    a = _paper(a, rng, s)                                     # 3 종이결
    a = _light(a, rng, s)                                     # 4 조명
    img = Image.fromarray((a * 255).astype(np.uint8))
    img = _optics(img, rng, s)                                # 5 광학
    a = np.asarray(img, dtype=np.float32) / 255.0
    a = _sensor(a, rng, s)                                    # 6 센서
    img = Image.fromarray((a * 255).astype(np.uint8))
    img = _down_jpeg(img, rng, s)                             # 7 다운샘플/JPEG
    return np.asarray(img, dtype=np.float32) / 255.0


# ──────────────────── 사진 증강 (관문 2, 300DPI 원본용) ────────────────────
# 기존 augment 는 정규화 뒤(줄간격 12px) 이미지에서 돌아 원근·해상도 열화를
# 제대로 못 흉내낸다. 여기서는 **300DPI 원본(줄간격 ~21‑27px) 위에서**
# 기하(원근 포함) → 잉크 → 종이결 → 조명(그늘 포함) → 광학 → 센서 →
# 다운샘플/JPEG 순서로 걸고, 마지막에 실사 추론과 같은
# `prep.normalize_photo` 를 통과시킨다 — 학습·추론 동일 전처리 원칙 유지.

def _persp(img, rng, s):
    """원근 + 회전 — 폰 카메라가 종이를 비스듬히 내려다본 것."""
    w, h = img.size
    j = 0.02 * s * h
    quad = []
    for cx, cy in ((0, 0), (0, h), (w, h), (w, 0)):
        quad += [cx + rng.uniform(-j, j), cy + rng.uniform(-j, j)]
    img = img.transform((w, h), Image.QUAD, quad,
                        resample=Image.BILINEAR, fillcolor=0)
    ang = rng.normal(0, 1.0 * s)
    return img.rotate(ang, resample=Image.BILINEAR, fillcolor=0, expand=False)


def _paper_photo(a, rng, s):
    """종이결 — 원본 해상도에 맞춘 큰 셀 + 강한 얼룩."""
    h, w = a.shape
    small = rng.random((max(2, h // 10), max(2, w // 10))).astype(np.float32)
    tex = np.asarray(Image.fromarray((small * 255).astype(np.uint8))
                     .resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
    return np.clip(a + (tex - 0.5) * 0.12 * s * (1 - a), 0, 1)


def _light_photo(g, rng, s):
    """조명 — 밝기 그라데이션 + 국소 그림자 덩어리(손·폰 그림자). g 는 회색(1=밝음)."""
    h, w = g.shape
    gx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    gy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    amp = 0.30 * s
    g = g * (1.0 - amp * np.clip(rng.uniform(-1, 1) * gx + rng.uniform(-1, 1) * gy,
                                 -1, 1))
    if rng.random() < 0.6 * s:
        cx, cy = rng.uniform(0, 1), rng.uniform(0, 1)
        sx, sy = rng.uniform(0.15, 0.5), rng.uniform(0.3, 1.0)
        depth = rng.uniform(0.1, 0.3) * s
        blob = np.exp(-(((gx - cx) / sx) ** 2 + ((gy - cy) / sy) ** 2))
        g = g * (1.0 - depth * blob.astype(np.float32))
    return np.clip(g, 0, 1)


def augment_photo(a, rng, s=1.0, gap=22.0):
    """(H, W) 원본 잉크배열(0~1, 300DPI) → 실사풍 열화 후 정규화된 (160, W')."""
    img = Image.fromarray((a * 255).astype(np.uint8))
    img = _persp(img, rng, s)                                 # 1 기하(원근)
    a = np.asarray(img, dtype=np.float32) / 255.0
    a = _ink(a, rng, s)                                       # 2 잉크
    a = _paper_photo(a, rng, s)                               # 3 종이결
    g = np.clip(1.0 - a, 0, 1) * rng.uniform(1.0 - 0.20 * s, 1.0)   # 종이 톤
    g = _light_photo(g, rng, s)                               # 4 조명·그늘
    img = Image.fromarray((g * 255).astype(np.uint8))
    r = abs(rng.normal(0, 0.5 * s)) * (gap / 12.0)
    if r > 0.15:
        img = img.filter(ImageFilter.GaussianBlur(r))         # 5 광학
    g = np.asarray(img, dtype=np.float32) / 255.0
    # 5.5 손떨림(모션블러) — 방향성 흐림. 실물 53장에서 중간화질 사진의
    # 인식 붕괴가 병목으로 남아 추가(관문2 ⑦ 진단).
    if rng.random() < 0.35 * s:
        L = rng.uniform(2.0, 7.0) * s * (gap / 22.0)
        steps = max(2, int(L))
        th = rng.uniform(0, np.pi)
        dx, dy = np.cos(th), np.sin(th)
        acc = np.zeros_like(g)
        for k in range(steps):
            t = (k - (steps - 1) / 2.0)
            sx, sy = int(round(t * dx)), int(round(t * dy))
            acc += np.roll(np.roll(g, sy, axis=0), sx, axis=1)
        g = acc / steps
    g = np.clip(g + rng.normal(0, 0.03 * s, g.shape).astype(np.float32), 0, 1)  # 6 센서
    w, h = img.size
    # 6.5 리샘플 체인 — 실물 파이프라인은 원근 워프·되펴기·정규화로
    # 보간을 여러 번 거쳐 획이 물러진다(실측: 보정 켬에서 인식 저하).
    # 축소↔복원 한 번으로 그 물러짐을 흉내낸다.
    if rng.random() < 0.6 * s:
        f2 = rng.uniform(1.1, 1.6)
        img = Image.fromarray((g * 255).astype(np.uint8))
        img = img.resize((max(16, int(w / f2)), max(16, int(h / f2))),
                         Image.BILINEAR).resize((w, h), Image.BILINEAR)
        g = np.asarray(img, dtype=np.float32) / 255.0
    f = rng.uniform(1.15, 1.15 + 1.45 * s)                    # 7 다운샘플/JPEG (마지막)
    img = Image.fromarray((g * 255).astype(np.uint8)) \
               .resize((max(16, int(w / f)), max(16, int(h / f))), Image.BILINEAR)
    q = int(rng.uniform(45, 92))
    if q < 90:
        import io
        b = io.BytesIO()
        img.save(b, 'JPEG', quality=max(30, q))
        b.seek(0)
        img = Image.open(b).convert('L')
    # 되돌려 키우지 않는다 — 실제 사진도 저해상도 그대로 들어오고,
    # normalize_photo 가 줄간격 12px 로 맞춘다.
    return prep.normalize_photo(img)


# ───────────────────────────── 데이터셋 ─────────────────────────────

class Lines(Dataset):
    def __init__(self, data, rows, vocab, aug=0.0, max_w=2600, photo=0.0,
                 photo_s=1.0):
        """photo: 표본마다 이 확률로 300DPI 원본 + 사진 증강 경로를 탄다.
        나머지는 기존 캐시 + 기존 증강(빠름) — 깨끗한 렌더 성능을 지키면서
        실사 내성을 얹는 혼합 학습."""
        self.data, self.rows, self.vocab, self.aug, self.max_w = \
            data, rows, vocab, aug, max_w
        self.photo, self.photo_s = photo, photo_s

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        rng = np.random.default_rng()
        if self.photo > 0 and rng.random() < self.photo:
            # 원본 경로 = 캐시 경로에서 'cache/' 접두사 제거
            orig = os.path.join(self.data, r['cache'][6:])
            with Image.open(orig) as im:
                a = 1.0 - np.asarray(im.convert('L'), dtype=np.float32) / 255.0
            st = prep.find_staff(a)
            gap = st[1] if st else 22.0
            x = augment_photo(a, rng, self.photo_s, gap=gap)
        else:
            with Image.open(os.path.join(self.data, r['cache'])) as im:
                x = np.asarray(im.convert('L'), dtype=np.float32) / 255.0
            if self.aug > 0:
                x = augment(x, rng, self.aug)
        if x.shape[1] > self.max_w:
            x = x[:, :self.max_w]
        y = r['_y']
        return torch.from_numpy(x)[None], torch.tensor(y, dtype=torch.long)


def collate(batch):
    ws = [b[0].shape[2] for b in batch]
    h = batch[0][0].shape[1]
    W = max(ws)
    xs = torch.zeros(len(batch), 1, h, W)
    for i, (x, _y) in enumerate(batch):
        xs[i, :, :, :x.shape[2]] = x
    ys = torch.cat([b[1] for b in batch])
    yl = torch.tensor([len(b[1]) for b in batch], dtype=torch.long)
    xl = torch.tensor(ws, dtype=torch.long)
    return xs, xl, ys, yl


class ThreadLoader:
    """스레드 기반 배치 공급기 — torch DataLoader 대용.

    윈도우 + 제한된 실행 환경에서 DataLoader 의 워커 프로세스가
    `PermissionError: [WinError 5]`(큐 세마포어) 로 죽는다. 우리 전처리는
    PIL·numpy 라 GIL 을 놓으므로 스레드로도 충분히 병렬화된다
    (실측: 단일 92줄/초 → 8스레드에서 수배).
    """

    def __init__(self, ds, batch_size, collate, shuffle=False, workers=8,
                 prefetch=6, drop_last=False, seed=None):
        self.ds, self.bs, self.collate = ds, batch_size, collate
        self.shuffle, self.workers, self.prefetch = shuffle, workers, prefetch
        self.drop_last, self.seed, self.epoch = drop_last, seed, 0

    def _batches(self):
        import random
        order = list(range(len(self.ds)))
        if self.shuffle:
            random.Random(None if self.seed is None else self.seed + self.epoch
                          ).shuffle(order)
        bs = [order[i:i + self.bs] for i in range(0, len(order), self.bs)]
        if self.drop_last and bs and len(bs[-1]) < self.bs:
            bs.pop()
        return bs

    def __len__(self):
        n = len(self.ds) // self.bs if self.drop_last else \
            -(-len(self.ds) // self.bs)
        return max(0, n)

    def __iter__(self):
        from collections import deque
        from concurrent.futures import ThreadPoolExecutor
        batches = iter(self._batches())
        self.epoch += 1
        with ThreadPoolExecutor(max_workers=max(1, self.workers)) as ex:
            q = deque()

            def push():
                try:
                    q.append(ex.submit(lambda ix: self.collate([self.ds[i] for i in ix]),
                                       next(batches)))
                    return True
                except StopIteration:
                    return False
            for _ in range(max(1, self.prefetch)):
                if not push():
                    break
            while q:
                fut = q.popleft()
                push()
                yield fut.result()


def load_rows(data, vocab=None, splits=('train',), min_tok=2, keep_unk=False):
    """index.jsonl → 어휘로 인코딩된 줄 목록.

    keep_unk=False (학습용): 어휘 밖 토큰이 있는 줄은 버린다 — CTC 목표가
      어휘 안에 있어야 하고, 학습 신호를 깨끗하게 둔다.
    keep_unk=True (검증·시험용): 버리지 않고 −1 로 남긴다. 돌려주는
      두 번째 값은 (버린 줄 수, 어휘밖 토큰 수) 다.
    """
    rows = []
    for ln in open(os.path.join(data, 'index.jsonl'), encoding='utf-8'):
        r = json.loads(ln)
        if r['split'] not in splits:
            continue
        rows.append(r)
    if vocab is None:
        return rows
    out, drop, nunk = [], 0, 0
    for r in rows:
        y = vocab.encode(r['tokens'], unk=-1 if keep_unk else None)
        if y is None or len(y) < min_tok:
            drop += 1
            continue
        nunk += sum(1 for k in y if k < 0)
        r['_y'] = y
        out.append(r)
    return (out, (drop, nunk)) if keep_unk else (out, drop)
