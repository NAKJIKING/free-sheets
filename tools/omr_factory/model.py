# -*- coding: utf-8 -*-
"""CRNN + CTC — 줄 이미지 한 장 → (음고, 길이) 토큰열.

왜 CTC 인가: 폰에서 autoregressive 대비 10~50배 빠르다(연구문서 결정).
왜 BiLSTM 인가: 조표·박자표가 줄 앞머리에 한 번만 나오고 그 뒤 모든
음표의 해석을 바꾼다 — 앞에서 뒤로 정보가 흘러야 한다. 순방향만으로는
붙임줄·점 같은 뒤따라오는 표기를 못 본다.

세로는 완전히 접어 없애고(오선 위 위치가 음고이므로 세로 해상도가 중요 →
가로만 1/4 로 줄인다), 가로 프레임 T = W/4 가 시간축이 된다.
"""
import torch
import torch.nn as nn


def block(cin, cout, pool):
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        nn.Conv2d(cout, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        nn.MaxPool2d(pool),
    )


class CRNN(nn.Module):
    #                              세로 160 → 80 → 40 → 20 → 10 → 5
    #                              가로  W  → W/2 → W/4 → W/4 → W/4 → W/4
    def __init__(self, n_class, height=160, hidden=256, layers=2, dropout=0.1):
        super().__init__()
        self.cnn = nn.Sequential(
            block(1, 32, (2, 2)),
            block(32, 64, (2, 2)),
            block(64, 128, (2, 1)),
            block(128, 192, (2, 1)),
            block(192, 256, (2, 1)),
        )
        self.down = 4                       # 가로 축소 배율
        hs = height
        for p in (2, 2, 2, 2, 2):
            hs //= p
        self.proj = nn.Conv2d(256, 256, (hs, 1))     # 남은 세로를 1 로 접는다
        self.rnn = nn.LSTM(256, hidden, layers, bidirectional=True,
                           batch_first=True, dropout=dropout)
        self.drop = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden * 2, n_class)

    def forward(self, x):
        f = self.proj(self.cnn(x))          # (B, 256, 1, T)
        f = f.squeeze(2).transpose(1, 2)    # (B, T, 256)
        f, _ = self.rnn(f)
        return self.fc(self.drop(f))        # (B, T, C) — 로짓

    def out_len(self, in_w):
        return torch.clamp(in_w // self.down, min=1)


def greedy_decode(logits, lens):
    """CTC 그리디 — (B, T, C) 로짓 → 토큰 인덱스열 목록."""
    best = logits.argmax(-1).cpu()
    out = []
    for b in range(best.shape[0]):
        prev, seq = -1, []
        for t in range(int(lens[b])):
            k = int(best[b, t])
            if k != prev and k != 0:
                seq.append(k)
            prev = k
        out.append(seq)
    return out
