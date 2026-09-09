#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""thesession 악보·미디 재생성 — 잘림 사고 복구용.

경위: collect_session.py 의 줄바꿈 정규화 버그로 ABC 본문에 빈 줄이 섞였고,
ABC 에서 빈 줄은 곡의 끝이라 abcm2ps·abc2midi 가 **첫 줄만** 읽고 멈췄다.
수집된 2,659곡 전부가 앞 4~6마디짜리 조각으로 저장돼 있었다.

이 스크립트는 카탈로그의 thesession 항목을 원본 덤프와 다시 맞춰
PDF·MIDI 를 제자리에서 다시 만든다. 몇 번을 돌려도 결과가 같다.

    python3 regen_session.py            # 전체
    python3 regen_session.py --limit 20 # 앞 20곡만(시험)

필요 도구: abcm2ps, ps2pdf(ghostscript), abc2midi
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed

from collect_session import normalize_abc_body, abc_key

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')
DUMP = 'https://raw.githubusercontent.com/adactio/TheSession-data/main/json/tunes.json'
CACHE = os.path.join(tempfile.gettempdir(), 'thesession_tunes.json')


def load_dump():
    if not os.path.exists(CACHE) or os.path.getsize(CACHE) < 1_000_000:
        print('덤프 내려받는 중…', flush=True)
        req = urllib.request.Request(DUMP, headers={'User-Agent': 'free-sheets'})
        with urllib.request.urlopen(req, timeout=300) as r, open(CACHE, 'wb') as f:
            f.write(r.read())
    with open(CACHE, encoding='utf-8') as f:
        tunes = json.load(f)
    by_tune = {}
    for t in tunes:                       # 곡별 첫 세팅 — 수집 때와 같은 규칙
        tid = str(t.get('tune_id') or t.get('tune') or '')
        if tid and tid not in by_tune:
            by_tune[tid] = t
    return by_tune


def build_abc(t):
    body = normalize_abc_body(t.get('abc') or '')
    return (f"X:1\nT:{t.get('name')}\nR:{t.get('type') or ''}\n"
            f"M:{t.get('meter') or '4/4'}\nL:1/8\n"
            f"K:{abc_key(t.get('mode'))}\n{body}\n")


def regen(job):
    """(tid, abc, pdf경로, mid경로) → (tid, ok, 메시지)"""
    tid, abc, out_pdf, out_mid = job
    d = tempfile.mkdtemp(prefix='abc_')
    a = os.path.join(d, 'a.abc'); ps = os.path.join(d, 'a.ps')
    p_tmp = out_pdf + '.tmp'; m_tmp = (out_mid + '.tmp') if out_mid else None
    try:
        with open(a, 'w', encoding='utf-8') as f:
            f.write(abc)
        r = subprocess.run(['abcm2ps', a, '-O', ps], capture_output=True, timeout=120)
        # abcm2ps 는 원본 ABC 에 문법 오류가 있어도 그 부분만 건너뛰고 나머지를
        # 그려낸다(rc=1 이지만 PS 는 정상 생성). 종료코드가 아니라 결과물로 판단한다.
        if not os.path.exists(ps) or os.path.getsize(ps) < 2000:
            return tid, False, f'abcm2ps 결과 없음(rc={r.returncode})'
        r = subprocess.run(['ps2pdf', ps, p_tmp], capture_output=True, timeout=120)
        if r.returncode != 0 or not os.path.exists(p_tmp):
            return tid, False, 'ps2pdf 실패'
        if m_tmp:
            r = subprocess.run(['abc2midi', a, '-o', m_tmp], capture_output=True, timeout=120)
            if r.returncode != 0 or not os.path.exists(m_tmp) or os.path.getsize(m_tmp) < 60:
                if os.path.exists(m_tmp):
                    os.remove(m_tmp)
                m_tmp = None
        os.replace(p_tmp, out_pdf)         # 원자적 교체 — 중간에 죽어도 원본이 남는다
        if m_tmp and os.path.exists(m_tmp):
            os.replace(m_tmp, out_mid)
        return tid, True, ''
    except Exception as e:
        return tid, False, f'{type(e).__name__}: {e}'
    finally:
        for f in (a, ps, p_tmp, m_tmp):
            if f and os.path.exists(f):
                try: os.remove(f)
                except OSError: pass
        try: os.rmdir(d)
        except OSError: pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--ids', default='', help='쉼표로 구분한 tune_id 만 처리')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    by_tune = load_dump()
    with open(CATALOG, encoding='utf-8') as f:
        catalog = json.load(f)

    only = {x for x in args.ids.split(',') if x}
    jobs, skipped = [], 0
    for e in catalog:
        if e.get('source') != 'thesession':
            continue
        m = re.search(r'-(\d+)\.pdf$', e.get('file', ''))
        if not m or m.group(1) not in by_tune:
            skipped += 1
            continue
        if only and m.group(1) not in only:
            continue
        t = by_tune[m.group(1)]
        pdf = os.path.join(ROOT, e['file'])
        mid = os.path.join(ROOT, e['midi']) if e.get('midi') else None
        jobs.append((m.group(1), build_abc(t), pdf, mid))
        if args.limit and len(jobs) >= args.limit:
            break

    print(f'재생성 대상 {len(jobs)}곡 (원본 대조 불가 {skipped}곡은 건너뜀)', flush=True)
    ok = fail = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = [ex.submit(regen, j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            tid, good, msg = fut.result()
            if good:
                ok += 1
            else:
                fail += 1
                if fail <= 10:
                    print(f'  ! {tid}: {msg}', flush=True)
            if i % 250 == 0:
                print(f'  … {i}/{len(jobs)}', flush=True)
    print(f'완료: 성공 {ok}, 실패 {fail}', flush=True)
    return 1 if fail and not ok else 0


if __name__ == '__main__':
    sys.exit(main())
