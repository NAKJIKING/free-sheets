#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""데이터 공장 산출물 표본 검증 — 학습을 시작하기 전에 돌린다.

    python tools/omr_factory/verify_data.py --data C:/Users/me/omr_lines

검사 3종:
  1. **조옮김 정합** — 같은 (곡·악기·청크) 의 shift=k 토큰이 shift=0 보다
     정확히 k 반음 높은가. 지시서의 "_kp0 vs _kp3 는 +3 반음" 검사다.
     음고뿐 아니라 **길이·붙임줄도 같아야** 한다(조옮김은 리듬을 안 바꾼다).
  2. **이미지↔정답 동기** — PNG 가 실제로 있고 비어 있지 않은가.
  3. **렌더 미디 대조** — LilyPond 가 같이 낸 .mid 의 음고열이 우리 토큰의
     붙임줄 병합 음고열과 같은가. 생성기가 이미 보지만, 여기서 독립적으로
     다시 본다(생성기 버그가 자기 검사까지 같이 틀릴 수 있으므로).

메타를 해석하지 않는 최소 미디 파서를 쓴다 — mido 는 LilyPond 가 먼 조로
옮길 때 내는 조표(플랫 8개↑)에 KeySignatureError 를 던진다.
"""
import argparse
import collections
import json
import os
import random
import struct
import sys


# ───────────────────── 최소 미디 파서 (메타 해석 안 함) ─────────────────────

def midi_notes(path):
    """.mid → 온셋 순 음고열. 메타 이벤트는 길이만 읽고 건너뛴다."""
    b = open(path, 'rb').read()
    if b[:4] != b'MThd':
        raise ValueError('MThd 아님')
    ntrk = struct.unpack('>H', b[10:12])[0]
    pos = 8 + struct.unpack('>I', b[4:8])[0]
    ev = []
    for _ in range(ntrk):
        if b[pos:pos + 4] != b'MTrk':
            break
        ln = struct.unpack('>I', b[pos + 4:pos + 8])[0]
        p, end, t, run = pos + 8, pos + 8 + ln, 0, 0
        while p < end:
            d = 0                                     # 가변길이 델타
            while True:
                c = b[p]; p += 1
                d = (d << 7) | (c & 0x7F)
                if not c & 0x80:
                    break
            t += d
            st = b[p]
            if st & 0x80:
                p += 1
                run = st
            else:
                st = run                              # 러닝 스테이터스
            if st == 0xFF:
                p += 1                                # 메타 종류
                ln2 = 0
                while True:
                    c = b[p]; p += 1
                    ln2 = (ln2 << 7) | (c & 0x7F)
                    if not c & 0x80:
                        break
                p += ln2                              # 내용은 해석하지 않는다
            elif st in (0xF0, 0xF7):
                ln2 = 0
                while True:
                    c = b[p]; p += 1
                    ln2 = (ln2 << 7) | (c & 0x7F)
                    if not c & 0x80:
                        break
                p += ln2
            else:
                hi = st & 0xF0
                n = 1 if hi in (0xC0, 0xD0) else 2
                if hi == 0x90 and b[p + 1] > 0:
                    ev.append((t, b[p]))              # note on (벨로시티>0)
                p += n
        pos = end
    ev.sort()
    return [p for _t, p in ev]


def merged_pitches(tokens):
    """토큰열 → 붙임줄 병합·쉼표 제거 음고열 (미디가 내는 것과 같은 모양)."""
    out, i = [], 0
    while i < len(tokens):
        p, _d, tie = tokens[i]
        i += 1
        while tie and i < len(tokens) and tokens[i][0] == p:
            tie = tokens[i][2]
            i += 1
        if p:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--samples', type=int, default=400, help='표본 곡 수')
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()

    rows = [json.loads(l) for l in
            open(os.path.join(a.data, 'manifest.jsonl'), encoding='utf-8')]
    print(f'줄 {len(rows)}개')

    by = collections.defaultdict(dict)                # (var, chunk) → {shift: row}
    for r in rows:
        by[(r.get('var', ''), r['chunk'])][r['shift']] = r
    print(f'(악기판본, 청크) 묶음 {len(by)}개')

    rnd = random.Random(a.seed)
    groups = sorted(by)
    rnd.shuffle(groups)

    # ── 1. 조옮김 정합
    ok = bad = pairs = nobase = 0
    fails = []
    for g in groups[:a.samples * 4]:
        d = by[g]
        if 0 not in d:
            nobase += 1
            continue
        base = d[0]['tokens']
        for k, r in d.items():
            if k == 0:
                continue
            pairs += 1
            t = r['tokens']
            if len(t) != len(base):
                bad += 1; fails.append((g, k, f'토큰수 {len(t)}≠{len(base)}')); continue
            why = None
            for (p0, d0, i0), (p1, d1, i1) in zip(base, t):
                if (d0, i0) != (d1, i1):
                    why = f'길이/붙임줄 다름 {(d0,i0)}→{(d1,i1)}'; break
                if p0 == 0 and p1 == 0:
                    continue                          # 쉼표
                if p1 - p0 != k:
                    why = f'{p0}→{p1} 는 {p1-p0}반음 (기대 {k})'; break
            if why:
                bad += 1
                if len(fails) < 10:
                    fails.append((g, k, why))
            else:
                ok += 1
    print(f'\n■ 조옮김 정합: 검사 {pairs}쌍 / 일치 {ok} / 불일치 {bad}'
          f'  (shift 0 없는 묶음 {nobase}개는 건너뜀)')
    for f in fails[:10]:
        print('   [X]', f)

    # ── 2·3. 이미지 존재 + 렌더 미디 대조
    sample = []
    for g in groups[:a.samples]:
        sample.extend(by[g].values())
    rnd.shuffle(sample)
    sample = sample[:a.samples * 2]
    nopng = emptypng = nomid = midbad = midok = 0
    mfails = []
    for r in sample:
        p = os.path.join(a.data, r['png'])
        if not os.path.exists(p):
            nopng += 1; continue
        if os.path.getsize(p) < 200:
            emptypng += 1; continue
        m = os.path.join(a.data, r['midi']) if r.get('midi') else None
        if not m or not os.path.exists(m):
            nomid += 1; continue
        try:
            got = midi_notes(m)
        except Exception as e:
            midbad += 1
            if len(mfails) < 6:
                mfails.append((r['png'], repr(e)[:60]))
            continue
        want = merged_pitches(r['tokens'])
        if got == want:
            midok += 1
        else:
            midbad += 1
            if len(mfails) < 6:
                mfails.append((r['png'], f'미디 {len(got)}음 vs 토큰 {len(want)}음'))
    print(f'\n■ 이미지: 검사 {len(sample)} / 없음 {nopng} / 빈파일 {emptypng}')
    print(f'■ 렌더 미디 대조: 일치 {midok} / 불일치 {midbad} / 미디없음 {nomid}')
    for f in mfails:
        print('   [X]', f)

    hard = bad or nopng or emptypng or midbad
    print('\n' + ('✅ 표본 검증 통과' if not hard else '❌ 결함 있음 — 학습 금지'))
    return 1 if hard else 0


if __name__ == '__main__':
    sys.exit(main())
