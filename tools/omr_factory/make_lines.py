#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4단계 데이터 공장 ① — 줄 단위 학습쌍 생성기.

우리 조판 원본(.ly, tools/original_src/all_out)에서 멜로디를 꺼내
몇 마디씩 끊고, 12개 조로 옮겨, **한 줄짜리 악보 이미지 + 정답 미디**
쌍을 찍어낸다. 잘라내기가 아니라 처음부터 한 줄로 조판하므로
이미지와 정답이 어긋날 수 없다(층정렬 문제 원천 차단).

    python3 tools/omr_factory/make_lines.py --out /tmp/lines --limit 3 --keys 0,3   # 연기 시험
    python3 tools/omr_factory/make_lines.py --out DIR                               # 전체 (~24,000쌍)

출력: DIR/<곡>__<악기>/c<청크>_k<시프트>.png + .midi + manifest.jsonl
주의: 전체 실행은 이미지 ~1.2GB — 개발 컨테이너 말고 액션/집PC/캐글에서.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'original_src', 'all_out')
LILY = os.environ.get('LILYPOND', '/opt/lily/lilypond-2.24.4/bin/lilypond')

# 반음 시프트 → \transpose c <목표>. 위·아래로 고르게 12개 조 —
# 멀리 옮기면 덧줄투성이 비현실 악보가 되므로 −5..+6 반음으로 제한.
SHIFT_NAME = {0: 'c', 1: 'des', 2: 'd', 3: 'ees', 4: 'e', 5: 'f', 6: 'fis',
              -1: 'b,', -2: 'bes,', -3: 'a,', -4: 'aes,', -5: 'g,'}

SNIPPET = r'''\version "2.24.4"
#(set-global-staff-size %(staff)d)
\paper {
  #(set! paper-width (* 400 mm)) #(set! paper-height (* 60 mm))
  indent = 0\mm line-width = 380\mm
  top-margin = 4\mm bottom-margin = 4\mm left-margin = 6\mm right-margin = 6\mm
  ragged-right = ##t page-breaking = #ly:one-line-auto-height-breaking
  oddHeaderMarkup = ##f evenHeaderMarkup = ##f
  oddFooterMarkup = ##f evenFooterMarkup = ##f
}
\score {
  { \transpose c %(key)s { %(head)s %(notes)s } }
  \layout { \context { \Score \omit BarNumber } }
  \midi { }
}
'''


def parse_melody(path):
    """(지시부, 빠르기표, 마디 목록) — 지시부에서 악기 조옮김 표기는 뗀다
    (정답 미디가 '보이는 음'과 같아지게 — 채점기와 같은 규칙). 빠르기표는
    실제 악보처럼 첫 줄(청크 0)에만 붙이도록 따로 돌려준다."""
    txt = open(path, encoding='utf-8').read()
    m = re.search(r'melody\s*=\s*\\absolute\s*\{(.*?)\n\}', txt, re.S)
    if not m:
        return None, None, None
    body = m.group(1).strip()
    body = re.sub(r'\\transposition\s+\S+\s*', '', body)
    body = re.sub(r'\\bar\s+"\|\."', '', body)
    lines = body.split('\n', 1)
    head = lines[0].strip()
    tm = re.search(r'\\tempo\s+\d+\s*=\s*\d+', head)
    tempo = tm.group(0) if tm else ''
    head = re.sub(r'\\tempo\s+\d+\s*=\s*\d+\s*', '', head).strip()
    notes = lines[1] if len(lines) > 1 else ''
    bars = [b.strip() for b in notes.replace('\n', ' ').split('|') if b.strip()]
    return head, tempo, bars


def chunks_of(bars, size=4):
    """마디를 size개씩 — 단, 붙임줄(~)이 경계를 넘으면 다음 마디까지 흡수."""
    out, i = [], 0
    while i < len(bars):
        j = min(i + size, len(bars))
        while j < len(bars) and bars[j - 1].rstrip().endswith('~'):
            j += 1
        out.append(' | '.join(bars[i:j]) + ' |')
        i = j
    return out


def midi_path(ly_dir, stem):
    """리눅스 LilyPond 는 `.midi`, 윈도우판은 `.mid` 를 낸다 — 있는 쪽을 쓴다."""
    for ext in ('.midi', '.mid'):
        p = os.path.join(ly_dir, stem + ext)
        if os.path.exists(p):
            return p
    return None


def render_one(job):
    ly_dir, name, head, chunk_i, chunk, shift = job
    # head 는 이미 청크별로 완성돼 들어온다(첫 청크에만 빠르기표 포함)
    stem = f'c{chunk_i:02d}_k{shift:+d}'.replace('+', 'p').replace('-', 'm')
    png = os.path.join(ly_dir, stem + '.png')
    if os.path.exists(png) and midi_path(ly_dir, stem):
        return ('skip', name, stem)
    # 조판 다양성: 곡·청크·조로 결정되는 보표 크기(난수 없이 재현 가능)
    h = int(hashlib.md5(f'{name}/{stem}'.encode()).hexdigest(), 16)
    staff = (20, 22, 24, 26)[h % 4]
    ly = SNIPPET % dict(staff=staff, key=SHIFT_NAME[shift], head=head, notes=chunk)
    src = os.path.join(ly_dir, stem + '.ly')
    open(src, 'w', encoding='utf-8').write(ly)
    r = subprocess.run([LILY, '-dresolution=300', '--png', '-dno-point-and-click',
                        '-o', os.path.join(ly_dir, stem), src],
                       capture_output=True, text=True, timeout=120)
    ok = os.path.exists(png) and midi_path(ly_dir, stem) is not None
    if ok:
        os.remove(src)                      # 렌더 성공하면 중간물 정리
        return ('ok', name, stem)
    return ('fail', name, stem + ' ' + (r.stderr or '')[-200:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0, help='곡 수 제한(연기 시험용)')
    ap.add_argument('--keys', default=','.join(str(k) for k in SHIFT_NAME),
                    help='반음 시프트 목록, 예: 0,3,-2')
    ap.add_argument('--bars', type=int, default=4, help='한 줄에 넣을 마디 수')
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    args = ap.parse_args()
    shifts = [int(k) for k in args.keys.split(',')]
    for s in shifts:
        assert s in SHIFT_NAME, f'시프트 {s} 는 −5..+6 범위 밖'

    # 언어판은 음이 같으므로 기본판(언어 접미사 없는 것)만 쓴다
    bases = sorted(f for f in os.listdir(SRC) if f.endswith('.ly')
                   and not re.search(r'__(de|en|es|fr|ind|pt|zh)\.ly$', f))
    if args.limit:
        bases = bases[:args.limit]

    jobs, manifest = [], []
    for f in bases:
        name = f[:-3]
        head, tempo, bars = parse_melody(os.path.join(SRC, f))
        if not head or not bars:
            print(f'건너뜀(구조 불일치): {f}', file=sys.stderr)
            continue
        ly_dir = os.path.join(args.out, name)
        os.makedirs(ly_dir, exist_ok=True)
        for ci, chunk in enumerate(chunks_of(bars, args.bars)):
            chunk_head = f'{head} {tempo}'.strip() if ci == 0 else head
            for sh in shifts:
                jobs.append((ly_dir, name, chunk_head, ci, chunk, sh))
                stem = f'c{ci:02d}_k{sh:+d}'.replace('+', 'p').replace('-', 'm')
                manifest.append(dict(song=name, chunk=ci, shift=sh,
                                     png=f'{name}/{stem}.png', midi=f'{name}/{stem}.midi'))

    print(f'곡 {len(bases)} → 학습쌍 {len(jobs)}건 렌더 시작 (병렬 {args.jobs})')
    ok = fail = skip = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for st, name, info in ex.map(render_one, jobs, chunksize=4):
            if st == 'ok':
                ok += 1
            elif st == 'skip':
                skip += 1
            else:
                fail += 1
                print(f'실패: {name}/{info}', file=sys.stderr)
            done = ok + fail + skip
            if done % 200 == 0:
                print(f'  {done}/{len(jobs)} (성공 {ok} 실패 {fail} 재개생략 {skip})')
    with open(os.path.join(args.out, 'manifest.jsonl'), 'w', encoding='utf-8') as f:
        for row in manifest:
            # 윈도우판 LilyPond 는 `.mid` 를 내므로 실제 파일명으로 교정한다
            if not os.path.exists(os.path.join(args.out, row['midi'])):
                alt = row['midi'][:-5] + '.mid'
                if os.path.exists(os.path.join(args.out, alt)):
                    row['midi'] = alt
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'끝: 성공 {ok} / 실패 {fail} / 재개생략 {skip} → {args.out}/manifest.jsonl')


if __name__ == '__main__':
    main()
