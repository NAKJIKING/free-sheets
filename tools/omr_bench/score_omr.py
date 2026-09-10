#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OMR 결과 채점 — 인식한 MusicXML 을 정답 MIDI 와 대조한다.

## 왜 이렇게 까다로운가 (전부 2026-09-09 에 실제로 겪은 함정)

1. **다악장** — Audiveris 는 한 PDF 를 `이름.mvt1.mxl`, `.mvt2.mxl` 로 쪼갠다.
   정답 MIDI 는 곡 전체다. 악장 하나만 전곡과 대조하면 참담한 점수가 나온다.
   → 같은 곡의 악장들을 **이어 붙여** 하나로 보고 대조한다.

2. **다성부** — 여러 성부를 한 줄로 납작하게 눌러 순서대로 비교하면,
   성부 간 아주 작은 시각 어긋남에도 순서가 뒤엉켜 오류가 폭발한다.
   → **단선율 곡만 편집거리로 채점**하고, 다성부는 개수 비교와
   '박자 맞음' 검사만 보고한다(정답 없이도 되는 검사).

3. **반복(도돌이표)** — MIDI 는 반복을 펼쳐 기록하고 악보는 한 번만 인쇄한다.
   → 예측을 그대로 / `expandRepeats()` 한 것 / 흔한 반복 구조(AABB 등)로
   만든 것 중 **가장 잘 맞는 것**을 쓴다.

4. **정답이 악보와 다른 경우** — 악보 PDF 가 곡의 일부만 담고 있는데 MIDI 는
   전곡인 사례가 실제로 있었다(thesession 잘림 사고). 이런 곡을 그대로 채점하면
   엔진 탓으로 오해한다. → 정답 음표 수가 인식 음표 수의 1.6배를 넘고 반복
   구조로도 설명이 안 되면 **'대조 불가'로 빼고 따로 센다.**

    python3 tools/omr_bench/score_omr.py --sample sample.json --pred out/ -o result.json
"""
import argparse
import collections
import glob
import json
import os
import statistics as st
import sys
import warnings
import zipfile
from fractions import Fraction

warnings.filterwarnings('ignore')

Q = 12  # 4분음표를 12 로 — 8분·16분·셋잇단 무손실


# ---------- 정답 쪽 ----------
def midi_pitches(path):
    import mido
    mf = mido.MidiFile(path, clip=True)
    ev = []
    for tr in mf.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == 'note_on' and m.velocity > 0:
                ev.append((t, m.note))
    ev.sort()
    return [p for _, p in ev]


# ---------- 예측 쪽 ----------
def _inner_xml(mxl):
    z = zipfile.ZipFile(mxl)
    n = [x for x in z.namelist() if x.endswith('.xml') and 'META-INF' not in x][0]
    out = mxl + '.x.xml'
    with open(out, 'wb') as f:
        f.write(z.read(n))
    return out


def xml_stats(path, expand=False):
    """(음높이 순서, 성부 수, 마디 수, 박자 안 맞는 마디 수)"""
    from music21 import converter, chord as m21chord, note as m21note
    p = _inner_xml(path) if path.endswith('.mxl') else path
    s = converter.parse(p)
    if expand:
        try:
            s = s.expandRepeats()
        except Exception:
            return None
    ev, bad, tot = [], 0, 0
    for part in s.parts:
        ms = list(part.getElementsByClass('Measure'))
        cur = None
        for k, m in enumerate(ms):
            if m.timeSignature:
                cur = m.timeSignature
            if cur and 0 < k < len(ms) - 1:      # 못갖춘마디·끝마디 제외
                tot += 1
                exp = Fraction(cur.numerator * 4, cur.denominator)
                got = Fraction(m.duration.quarterLength).limit_denominator(96)
                if abs(got - exp) > Fraction(1, 64):
                    bad += 1
        for e in part.flatten().notes:
            off = round(float(e.offset) * Q)
            if isinstance(e, m21chord.Chord):
                for pit in e.pitches:
                    ev.append((off, pit.midi))
            elif isinstance(e, m21note.Note):
                ev.append((off, e.pitch.midi))
    ev.sort()
    return [p_ for _, p_ in ev], len(s.parts), tot, bad


# ---------- 비교 ----------
def lev(a, b):
    n, m = len(a), len(b)
    if n * m > 4_000_000:
        return None
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ai != b[j - 1]))
        prev = cur
    return prev[m]


def repeat_variants(pred):
    """악보 1회분에서 만들 수 있는 흔한 반복 구조들."""
    n = len(pred)
    h, t = n // 2, n // 3
    out = {'as-is': pred, 'x2': pred * 2, 'x3': pred * 3}
    if h:
        A, B = pred[:h], pred[h:]
        out['AABB'] = A + A + B + B
        out['AAB'] = A + A + B
        out['ABB'] = A + B + B
    if t:
        X, Y, Z = pred[:t], pred[t:2 * t], pred[2 * t:]
        out['AABBCC'] = X + X + Y + Y + Z + Z
    return out


def best_ner(gt, pred, expanded=None):
    """반복 구조를 맞춰 본 뒤 가장 좋은 NER 과 그때의 구조 이름."""
    cands = repeat_variants(pred)
    if expanded:
        cands['expandRepeats'] = expanded
    best = (9e9, '?')
    for name, c in cands.items():
        d = lev(gt, c)
        if d is None:
            continue
        r = d / max(1, len(gt))
        if r < best[0]:
            best = (r, name)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', required=True)
    ap.add_argument('--pred', required=True, help='Audiveris -output 폴더')
    ap.add_argument('-o', '--out', default='')
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    args = ap.parse_args()

    with open(args.sample, encoding='utf-8') as f:
        sample = json.load(f)

    rows = []
    for e in sample:
        stem = os.path.splitext(os.path.basename(e['file']))[0]
        mxls = sorted(glob.glob(os.path.join(args.pred, stem + '.mxl')) +
                      glob.glob(os.path.join(args.pred, stem + '.mvt*.mxl')))
        rec = dict(title=e.get('title'), source=e.get('source'),
                   poly=e['poly'], pages=e['pages'], n_gt=None, n_pred=None,
                   parts=None, bars=None, bad_bars=None, ner=None,
                   fit=None, status='')
        if not mxls:
            rec['status'] = '인식 실패'
            rows.append(rec)
            continue
        try:
            gt = midi_pitches(os.path.join(args.root, e['midi']))
        except Exception:
            rec['status'] = '정답 읽기 실패'
            rows.append(rec)
            continue
        pred, parts, bars, bad = [], 0, 0, 0
        exp = []
        ok = True
        # 반복 펼치기는 편집거리를 쓸 단선율 곡에만 한다 — 다성부 대곡까지
        # 두 번 파싱하면 표본 300곡에 몇 시간이 더 걸린다.
        need_expand = e['poly'] == 1
        for m in mxls:                          # 함정 1 — 악장을 이어 붙인다
            try:
                a = xml_stats(m)
                b = xml_stats(m, expand=True) if need_expand else None
            except Exception:
                ok = False
                break
            pred += a[0]; parts = max(parts, a[1]); bars += a[2]; bad += a[3]
            exp += (b[0] if b else a[0])
        if not ok:
            rec['status'] = '인식 결과 파싱 실패'
            rows.append(rec)
            continue
        rec.update(n_gt=len(gt), n_pred=len(pred), parts=parts,
                   bars=bars, bad_bars=bad)
        if not gt or not pred:
            rec['status'] = '빈 결과'
            rows.append(rec)
            continue

        if e['poly'] == 1:                      # 함정 2 — 단선율만 편집거리로
            ner, fit = best_ner(gt, pred, exp)
            rec.update(ner=round(ner, 4), fit=fit)
            # 함정 4 — 정답이 악보보다 훨씬 많고 반복으로도 설명 안 되면 대조 불가
            if len(gt) > len(pred) * 1.6 and ner > 0.35:
                rec['status'] = '대조 불가(악보와 정답 범위 불일치)'
            else:
                rec['status'] = '채점됨'
        else:
            rec['status'] = '다성부(개수·박자만)'
        rows.append(rec)

    # ---- 요약 ----
    scored = [r for r in rows if r['status'] == '채점됨']
    print(f"\n{'출처':<18}{'성부':>5}{'표본':>5}{'채점':>5}{'중앙NER':>9}{'무오류':>7}{'박자오류':>9}")
    print('-' * 62)
    g = collections.defaultdict(list)
    for r in rows:
        g[(r['source'], '단선율' if r['poly'] == 1 else '다성부')].append(r)
    for (src, band), v in sorted(g.items()):
        sc = [x for x in v if x['status'] == '채점됨']
        ners = [x['ner'] for x in sc]
        bb = [x['bad_bars'] / x['bars'] for x in v if x.get('bars')]
        print(f"{src:<18}{band:>5}{len(v):>5}{len(sc):>5}"
              f"{(f'{st.median(ners):.3f}' if ners else '-'):>9}"
              f"{(f'{sum(1 for x in ners if x == 0)}' if ners else '-'):>7}"
              f"{(f'{st.median(bb) * 100:.1f}%' if bb else '-'):>9}")
    st_cnt = collections.Counter(r['status'] for r in rows)
    print('\n상태:', dict(st_cnt))
    if scored:
        ners = [r['ner'] for r in scored]
        print(f"채점된 {len(scored)}곡 — 중앙 NER {st.median(ners):.4f}, "
              f"평균 {st.mean(ners):.4f}, 무오류 {sum(1 for x in ners if x == 0)}곡")
        print('반복 구조 분포:', dict(collections.Counter(r['fit'] for r in scored)))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f'→ {args.out}')


if __name__ == '__main__':
    main()
