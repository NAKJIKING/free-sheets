#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The Session 수집 — 아일랜드 전통곡(퍼블릭 도메인) 인기순 상위를
ABC 공식 데이터 덤프에서 받아 PDF+미디로 변환.

덤프: github.com/adactio/TheSession-data (주간 갱신, 스크래핑 불필요)
"""
import json
import os
import re
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw', 'thesession')
MIDS = os.path.join(ROOT, 'mids')
CATALOG = os.path.join(ROOT, 'catalog.json')
LIMIT = int(os.environ.get('SESSION_LIMIT', '1500'))
DUMP = 'https://raw.githubusercontent.com/adactio/TheSession-data/main/json/tunes.json'
POP = 'https://raw.githubusercontent.com/adactio/TheSession-data/main/json/tune_popularity.json'


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'free-sheets'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def load_catalog():
    if os.path.exists(CATALOG):
        with open(CATALOG, encoding='utf-8') as f:
            return json.load(f)
    return []


def save_catalog(c):
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


def abc_key(mode):
    """'Gmajor'/'Edorian' → 'G'/'Edor' (abc 표준 조성 표기)."""
    m = re.match(r'([A-G][b#]?)(\w*)', mode or '')
    if not m:
        return 'C'
    tonic, kind = m.group(1), (m.group(2) or '').lower()
    suffix = {
        'major': '', 'minor': 'min', 'dorian': 'dor', 'mixolydian': 'mix',
        'phrygian': 'phr', 'lydian': 'lyd', 'aeolian': 'min', 'ionian': '',
    }.get(kind, '')
    return tonic + suffix


def convert(abc_text, out_pdf, out_mid):
    tmp_abc = os.path.join(ROOT, '_tmp_s.abc')
    tmp_ps = os.path.join(ROOT, '_tmp_s.ps')
    with open(tmp_abc, 'w', encoding='utf-8') as f:
        f.write(abc_text)
    try:
        r = subprocess.run(['abcm2ps', tmp_abc, '-O', tmp_ps],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not os.path.exists(tmp_ps):
            return False
        r = subprocess.run(['ps2pdf', tmp_ps, out_pdf],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not os.path.exists(out_pdf):
            return False
        r = subprocess.run(['abc2midi', tmp_abc, '-o', out_mid],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not os.path.exists(out_mid) \
                or os.path.getsize(out_mid) < 60:
            if os.path.exists(out_mid):
                os.remove(out_mid)
        return True
    finally:
        for p in (tmp_abc, tmp_ps):
            if os.path.exists(p):
                os.remove(p)


def main():
    print('덤프 내려받는 중…', flush=True)
    tunes = fetch_json(DUMP)
    print(f'세팅 {len(tunes)}건', flush=True)
    # 곡별 첫 세팅 + 인기 점수(공식 인기 파일, 실패 시 세팅 수로 대체)
    by_tune = {}
    counts = {}
    for t in tunes:
        tid = str(t.get('tune_id') or t.get('tune') or '')
        if not tid:
            continue
        counts[tid] = counts.get(tid, 0) + 1
        if tid not in by_tune:
            by_tune[tid] = t
    pop = {}
    try:
        for p in fetch_json(POP):
            pop[str(p.get('tune_id') or '')] = int(p.get('tunebooks') or 0)
        print(f'인기 데이터 {len(pop)}건', flush=True)
    except Exception as e:
        print(f'인기 파일 없음({e}) — 세팅 수로 대체', flush=True)
        pop = counts
    order = sorted(by_tune, key=lambda k: pop.get(k, 0), reverse=True)

    os.makedirs(RAW, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    catalog = load_catalog()
    done = {e['source_url'] for e in catalog}
    added = failed = 0
    for tid in order:
        if added >= LIMIT:
            break
        src_url = f'https://thesession.org/tunes/{tid}'
        if src_url in done:
            continue
        t = by_tune[tid]
        name = (t.get('name') or f'Tune {tid}').strip()
        body = (t.get('abc') or '').replace('\\r\\n', '\n').replace('\r', '\n')
        if not body.strip():
            continue
        abc = (f"X:1\nT:{name}\nR:{t.get('type') or ''}\n"
               f"M:{t.get('meter') or '4/4'}\nL:1/8\n"
               f"K:{abc_key(t.get('mode'))}\n{body}\n")
        safe = re.sub(r'[^A-Za-z0-9._-]', '_', name)[:70] or 'tune'
        out_pdf = os.path.join(RAW, f'{safe}-{tid}.pdf')
        out_mid = os.path.join(MIDS, f's_{safe}-{tid}.mid')
        try:
            ok = convert(abc, out_pdf, out_mid)
        except Exception as e:
            print(f'  ! 예외: {tid} — {e}', flush=True)
            ok = False
        if not ok:
            failed += 1
            if failed <= 5:
                print(f'  ! 변환 실패: {tid} {name}', flush=True)
            continue
        entry = {
            'source': 'thesession',
            'source_url': src_url,
            'file': os.path.relpath(out_pdf, ROOT),
            'title': name,
            'composer': 'Traditional',
            'instrument': 'Folk',
            'license': 'Public Domain (traditional)',
        }
        if os.path.exists(out_mid):
            entry['midi'] = os.path.relpath(out_mid, ROOT)
        catalog.append(entry)
        done.add(src_url)
        added += 1
        if added % 100 == 0:
            print(f'  … {added}곡 완료', flush=True)
            save_catalog(catalog)
    save_catalog(catalog)
    print(f'민속곡 신규 {added}곡, 실패 {failed}곡, 카탈로그 총 {len(catalog)}곡',
          flush=True)


if __name__ == '__main__':
    main()
