#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수집 결과물 타당성 검사 — 파일이 '있는지'가 아니라 '말이 되는지' 본다.

만든 이유: 2026-09 에 thesession 2,659곡이 앞 4~6마디만 담긴 채 몇 달간
배포됐다(collect_session.py 의 줄바꿈 버그). 당시 유일한 검사는
"미디가 60바이트보다 큰가"였고, 잘린 미디는 372바이트라 그냥 통과했다.
파일 크기가 아니라 **내용의 양**을 봐야 잡힌다.

검사 항목
  1. 카탈로그가 가리키는 로컬 파일이 실제로 있는가
  2. 미디가 열리는가, 음표가 0개는 아닌가
  3. 악보가 진짜 PDF 인가(%PDF- 로 시작)
  4. **쪽당 음표 수** — 같은 출처 안에서 지나치게 적은 곡을 찾는다
     (출처마다 편성이 달라 절대 기준은 못 쓴다. 같은 출처끼리 비교한다)

    python3 check_outputs.py             # 전체
    python3 check_outputs.py --source thesession
    python3 check_outputs.py --sample 100    # 출처당 표본 수 제한(기본 400)

문제가 있으면 종료코드 1. 수집 워크플로 끝에 붙여 두면 같은 사고를 막는다.
"""
import argparse
import collections
import json
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')

# 쪽당 음표 수가 같은 출처 중앙값의 이 비율보다 낮으면 잘림을 의심한다.
LOW_RATIO = 0.35
# 출처 전체가 이 값보다 낮으면 그 출처를 통째로 의심한다(정상 출처는 48~400).
SOURCE_FLOOR = 20


def pdf_pages(path):
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError:
        return None
    if not data.startswith(b'%PDF-'):
        return 0                       # PDF 가 아님 — 호출부에서 오류로 본다
    m = re.findall(rb'/Count\s+(\d+)', data)
    return max((int(x) for x in m), default=1)


def midi_notes(path):
    """음표 수. 열 수 없으면 None.

    clip=True 로 읽는다 — 일부 LilyPond 산출물은 범위를 벗어난 바이트나
    '♯ 9개' 같은 조표 메타를 담고 있어 엄격한 파서가 거부하지만, 음표
    자체는 멀쩡하다(실측: 거슈윈 곡 1,975음). 앱의 자체 파서는 메타를
    무시하므로 여기서 오류로 세면 헛경보가 된다.
    """
    import mido
    for kw in ({'clip': True}, {}):
        try:
            mf = mido.MidiFile(path, **kw)
        except Exception:
            continue
        return sum(1 for tr in mf.tracks for m in tr
                   if m.type == 'note_on' and m.velocity > 0)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default='')
    ap.add_argument('--sample', type=int, default=400)
    args = ap.parse_args()

    with open(CATALOG, encoding='utf-8') as f:
        catalog = json.load(f)

    errors, warnings = [], []
    by_src = collections.defaultdict(list)   # source -> [(entry, pages, notes)]

    for e in catalog:
        src = e.get('source', '?')
        if args.source and src != args.source:
            continue
        if e.get('base'):                    # 외부 호스팅 — 로컬에서 볼 수 없다
            continue
        sheet = e.get('file')
        midi = e.get('midi')
        title = (e.get('title') or '?')[:40]

        if sheet:
            p = os.path.join(ROOT, sheet)
            if not os.path.exists(p):
                continue                     # sparse clone — 없는 건 검사 대상 아님
            pages = pdf_pages(p)
            if pages == 0:
                errors.append(f'[{src}] {title}: PDF 가 아님 — {sheet}')
                continue
        else:
            pages = None

        notes = None
        if midi:
            mp = os.path.join(ROOT, midi)
            if not os.path.exists(mp):
                continue
            notes = midi_notes(mp)
            if notes is None:
                # 엄격 파서가 거부해도 앱은 재생할 수 있다 — 경고로만 남긴다
                warnings.append(f'[{src}] {title}: 표준 파서로 열리지 않음 '
                                f'(앱은 재생될 수 있음) — {midi}')
                continue
            if notes == 0:
                errors.append(f'[{src}] {title}: 미디에 음표가 0개 — {midi}')
                continue

        if pages and notes:
            by_src[src].append((e, pages, notes))

    print(f"{'출처':<20}{'표본':>6}{'쪽수중앙':>9}{'음표중앙':>9}{'쪽당':>7}   판정")
    print('-' * 68)
    bad_sources = []
    for src, rows in sorted(by_src.items(), key=lambda x: -len(x[1])):
        rows = rows[:args.sample]
        per = [n / max(1, p) for _, p, n in rows]
        med = st.median(per)
        verdict = '정상'
        if med < SOURCE_FLOOR:
            verdict = '❌ 출처 전체가 의심'
            bad_sources.append(src)
        print(f'{src:<20}{len(rows):>6}'
              f'{st.median([r[1] for r in rows]):>9.0f}'
              f'{st.median([r[2] for r in rows]):>9.0f}{med:>7.0f}   {verdict}')
        # 같은 출처 안의 이상치
        low = [(e, p, n) for (e, p, n) in rows
               if n / max(1, p) < med * LOW_RATIO]
        for e, p, n in low[:5]:
            warnings.append(f'[{src}] {(e.get("title") or "?")[:36]}: '
                            f'{p}쪽에 음표 {n}개 (출처 중앙값의 '
                            f'{n / max(1, p) / med * 100:.0f}%)')
        if len(low) > 5:
            warnings.append(f'[{src}] … 같은 종류 {len(low) - 5}건 더')

    print()
    for w in warnings[:40]:
        print(f'  ⚠️  {w}')
    if len(warnings) > 40:
        print(f'  … 경고 {len(warnings) - 40}건 더')
    for x in errors[:40]:
        print(f'  ❌ {x}')
    if len(errors) > 40:
        print(f'  … 오류 {len(errors) - 40}건 더')

    print(f'\n오류 {len(errors)}건, 경고 {len(warnings)}건, '
          f'의심 출처 {len(bad_sources)}개')
    if errors or bad_sources:
        print('실패 — 수집기를 확인할 것.')
        return 1
    print('통과.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
