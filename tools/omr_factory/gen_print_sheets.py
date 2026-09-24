#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실물 촬영용 인쇄 악보 생성 — 관문 2 실물 간극 해소용 (2026-09-24).

코퍼스 소스(퍼블릭 도메인 lieder 미디)에서 **train 분할 곡만** 골라
A4 한 페이지짜리 악보를 우리 렌더러(LilyPond)로 조판한다. 인쇄→폰 촬영하면
정답 토큰이 이미 있는 실물 도메인 학습 데이터가 된다.

곡 배분은 실패 분석 기준(모델이 약한 요소):
  A 셋잇단 4곡 / B 임시표·먼 조 3곡 / C 16분 밀집 3곡
  D 쉼표 조합 2곡 / E 빽빽한 마디(작은 보표) 3곡

시험 오염 방지: test 분할 곡 제외(곡 단위), 캐논(자가 조판·코퍼스 밖)과 무관.
정답 대조: 코퍼스와 같은 장치 — LilyPond 미디의 음고열과 토큰 병합 음고열 대조.

    $env:LILYPOND='...lilypond.exe'
    python tools/omr_factory/gen_print_sheets.py --data C:/Users/me/omr_lines3a \
        --out C:/Users/me/omr_print

출력: OUT/01.pdf..15.pdf (+.png 미리보기, truth.json)
주의: PDF·PNG 출력물은 커밋 금지(데이터 규칙). 코드·일지만 커밋.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_lines as L

LILY = os.environ.get('LILYPOND', 'lilypond')

A4_SNIPPET = r'''\version "2.24.4"
#(set-global-staff-size %(staff)d)
\paper {
  #(set-paper-size "a4")
  indent = 0\mm
  top-margin = 10\mm bottom-margin = 10\mm
  left-margin = 12\mm right-margin = 12\mm
  ragged-last-bottom = ##t
  print-page-number = ##f
}
\header { title = "%(pid)s" subtitle = "%(sub)s" tagline = ##f }
\score {
  { \transpose c %(shift)s { \clef %(clef)s \key %(key)s \time %(time)s \tempo 4 = %(tempo)d %(notes)s } }
  \layout { \context { \Score \omit BarNumber } }
  \midi { }
}
'''


def scale_pcs(fifths):
    tonic = (fifths * 7) % 12
    return {(tonic + i) % 12 for i in (0, 2, 4, 5, 7, 9, 11)}


def song_stats(bars, ks):
    toks = [t for bar in bars for t in bar]
    notes = [t for t in toks if t[0]]
    if not notes:
        return None
    n = len(toks)
    pcs = scale_pcs(L.KEY_FIFTHS.get(ks, 0))
    return dict(
        bars=len(bars), toks=n, notes=len(notes),
        tri=sum(1 for t in toks if t[1] in (4, 8)) / n,
        six=sum(1 for t in toks if t[1] == 3) / n,
        rest=sum(1 for t in toks if not t[0]) / n,
        dens=len(notes) / len(bars),
        chrom=sum(1 for t in notes if t[0] % 12 not in pcs) / len(notes))


def far_shift(ks):
    """조표·임시표가 많아지는 조옮김 — |파이브스| 5~7 을 노린다."""
    f0 = L.KEY_FIFTHS.get(ks, 0)
    best, bv = 0, -1
    for sh, df in L.SHIFT_FIFTHS.items():
        if not L.key_ok(ks, sh):
            continue
        v = abs(f0 + df)
        if v > bv:
            best, bv = sh, v
    return best


def typeset_page(mid_path, pid, sub, shift, staff, out_dir):
    """미디 → A4 1페이지 조판(+미디 대조). 마디를 줄여가며 1페이지에 맞춘다.
    반환: (tokens, bars_used, ts, ks) 또는 (None, 이유)."""
    got = L.melody_of(mid_path)
    if not got:
        return None, '단선율없음'
    notes, ts, ks = got
    if tuple(ts) not in L.TIMESIGS or not L.key_ok(ks, shift):
        return None, '박자표/조 제외'
    bars = L.to_bars(notes, L.bar_ticks(ts))
    if not bars or len(bars) < 12:
        return None, '마디 부족'
    key, sharps = L.KEYSIG.get(ks, ('c \\major', True))
    med = sorted(p for p, _s, _d in notes)[len(notes) // 2]
    clef = 'bass' if med + shift < 55 else 'treble'
    tempo = (72, 84, 90, 96, 108)[sum(ord(c) for c in pid) % 5]
    cap = min(len(bars), int(3600 / L.bar_ticks(ts)))   # 4/4 기준 ~75마디 시도
    for _try in range(6):
        sl = bars[:cap]
        ns, tokens = L.bars_to_ly([[tuple(e) for e in bar] for bar in sl], sharps)
        if ns is None:
            return None, '조판 실패(비격자)'
        src = A4_SNIPPET % dict(staff=staff, pid=pid, sub=sub,
                                shift=L.SHIFT_NAME[shift], clef=clef, key=key,
                                time=f'{ts[0]}/{ts[1]}', tempo=tempo, notes=ns)
        stem = os.path.join(out_dir, pid)
        with open(stem + '.ly', 'w', encoding='utf-8') as f:
            f.write(src)
        r = subprocess.run([LILY, '-dresolution=300', '--png', '--pdf',
                            '-dno-point-and-click', '-o', stem, stem + '.ly'],
                           capture_output=True, text=True, timeout=300)
        multi = glob.glob(stem + '-page*.png')
        if os.path.exists(stem + '.pdf') and not multi:
            break                                   # 1페이지 성공
        for p in multi:
            os.remove(p)
        cap = max(12, int(cap * 0.78))              # 넘치면 마디를 줄여 재시도
    else:
        return None, '1페이지 맞춤 실패'
    if not os.path.exists(stem + '.png'):
        return None, '렌더 실패 ' + (r.stderr or '')[-120:]
    mid_out = L.found_midi(stem)
    if not mid_out:
        return None, '미디 없음'
    # 토큰은 이미지에 보이는 음(조옮김 후)으로 저장 — 코퍼스와 같은 규칙
    # (make_lib_lines run_job 의 🔴 주석 참조: 여기가 라벨의 유일한 진실 지점).
    tokens = [[(tp + shift) if tp else 0, td, tt] for tp, td, tt in tokens]
    want = L.merged_pitches([tuple(t) for t in tokens])
    have = L.midi_notes(mid_out)
    if want != have:
        return None, f'미디 대조 불일치({len(have)} vs {len(want)})'
    os.remove(stem + '.ly')
    os.remove(mid_out)
    return dict(tokens=tokens, bars_used=len(sl), ts=list(ts), ks=ks,
                clef=clef, tempo=tempo), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='분할 정보를 읽을 코퍼스')
    ap.add_argument('--out', required=True)
    ap.add_argument('--mids', default='mids')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    split_of = {}
    for ln in open(os.path.join(a.data, 'index.jsonl'), encoding='utf-8'):
        r = json.loads(ln)
        split_of.setdefault(r['song'], r['split'])

    # 후보 스캔 — train 분할 lieder 만
    cands = []
    files = sorted(glob.glob(os.path.join(a.mids, '*.mid')))
    print(f'lieder 미디 {len(files)}개 스캔…', flush=True)
    for i, p in enumerate(files):
        if split_of.get(L.song_key(p)) != 'train':
            continue
        got = L.melody_of(p)
        if not got:
            continue
        notes, ts, ks = got
        if tuple(ts) not in L.TIMESIGS:
            continue
        bars = L.to_bars(notes, L.bar_ticks(ts))
        if not bars or len(bars) < 16:
            continue
        st = song_stats(bars, ks)
        if st:
            st.update(path=p, ks=ks)
            cands.append(st)
        if (i + 1) % 500 == 0:
            print(f'  {i + 1}/{len(files)} (후보 {len(cands)})', flush=True)
    print(f'후보 {len(cands)}곡', flush=True)

    # 카테고리 배분 — 위 카테고리부터 그리디, 곡 중복 없음
    plan = [('A셋잇단', 'tri', 4, 20), ('C16분밀집', 'six', 3, 18),
            ('E빽빽', 'dens', 3, 16), ('D쉼표', 'rest', 2, 20),
            ('B임시표', 'chrom', 3, 20)]
    taken, picks = set(), []
    for cat, keyf, n, staff in plan:
        pool = sorted((c for c in cands if c['path'] not in taken),
                      key=lambda c: -c[keyf])
        for c in pool:
            if n == 0:
                break
            sh = far_shift(c['ks']) if cat.startswith('B') else 0
            picks.append((cat, c, sh, staff))
            taken.add(c['path'])
            n -= 1

    truth, num = {}, 0
    for cat, c, sh, staff in picks:
        pid = f'OMR-{num + 1:02d}'
        base = os.path.splitext(os.path.basename(c['path']))[0]
        sub = base.replace('__', ' ').replace('_', ' ')[:48]
        res, err = typeset_page(c['path'], pid, sub, sh, staff, a.out)
        if err:
            print(f'  {pid} {cat} {base}: 실패({err}) — 다음 후보로', flush=True)
            # 같은 카테고리의 다음 후보로 대체
            keyf = dict(A='tri', C='six', E='dens', D='rest', B='chrom')[cat[0]]
            for c2 in sorted((x for x in cands if x['path'] not in taken),
                             key=lambda x: -x[keyf]):
                sh2 = far_shift(c2['ks']) if cat.startswith('B') else 0
                res, err = typeset_page(c2['path'], pid,
                                        os.path.splitext(os.path.basename(
                                            c2['path']))[0][:48],
                                        sh2, staff, a.out)
                taken.add(c2['path'])
                if not err:
                    c, sh = c2, sh2
                    break
            if err:
                print(f'  {pid} 대체도 실패 — 건너뜀', flush=True)
                continue
        num += 1
        nn = f'{num:02d}'
        for ext in ('.pdf', '.png'):
            os.replace(os.path.join(a.out, pid + ext),
                       os.path.join(a.out, nn + ext))
        truth[nn] = dict(category=cat, song=L.song_key(c['path']),
                         file=os.path.basename(c['path']), shift=sh,
                         staff=staff, stats={k: round(c[k], 3) for k in
                                             ('tri', 'six', 'rest', 'dens',
                                              'chrom')}, **res)
        print(f'  {nn} [{cat}] {truth[nn]["song"]} shift={sh} staff={staff} '
              f'마디 {res["bars_used"]} 토큰 {len(res["tokens"])}', flush=True)
        if num >= 15:
            break

    json.dump(truth, open(os.path.join(a.out, 'truth.json'), 'w',
                          encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'끝: {num}곡 → {a.out}', flush=True)


if __name__ == '__main__':
    main()
