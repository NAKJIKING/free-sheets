#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Open Hymnal 수집 — 퍼블릭 도메인 찬송가(ABC)를 PDF+미디로 변환.

전제: abcm2ps, abc2midi(abcmidi), ps2pdf(ghostscript) 설치.
openhymnal.org 색인에서 .abc 링크를 모아 내려받는다 (예절 0.7초 간격).
"""
import json
import os
import re
import subprocess
import time
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw', 'openhymnal')
MIDS = os.path.join(ROOT, 'mids')
CATALOG = os.path.join(ROOT, 'catalog.json')
BASE = 'https://openhymnal.org/'
INDEXES = [
    'https://openhymnal.org/mobile-index.html',
    'https://openhymnal.org/index.html',
    'https://openhymnal.org/',
    'http://openhymnal.org/mobile-index.html',
]
UA = {'User-Agent': 'free-sheets-collector (public domain hymnal mirror)'}


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else data.decode('utf-8', 'replace')


def load_catalog():
    if os.path.exists(CATALOG):
        with open(CATALOG, encoding='utf-8') as f:
            return json.load(f)
    return []


def save_catalog(c):
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


def abc_field(abc, tag):
    m = re.search(rf'^{tag}:\s*(.+)$', abc, re.M)
    return m.group(1).strip() if m else ''


def convert(abc_text, out_pdf, out_mid):
    """ABC → PDF(abcm2ps+ps2pdf) / MIDI(abc2midi). 성공 여부 반환."""
    tmp_abc = os.path.join(ROOT, '_tmp.abc')
    tmp_ps = os.path.join(ROOT, '_tmp.ps')
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
            # 미디 실패해도 PDF는 살린다
            if os.path.exists(out_mid):
                os.remove(out_mid)
            return True
        return True
    finally:
        for p in (tmp_abc, tmp_ps):
            if os.path.exists(p):
                os.remove(p)


def main():
    links = []
    for idx in INDEXES:
        try:
            html = fetch(idx)
        except Exception as e:
            print(f'색인 실패 {idx}: {e}', flush=True)
            continue
        found = re.findall(r'href=["\']([^"\']+?\.abc)["\']', html, re.I)
        if found:
            links = [urllib.parse.urljoin(idx, h) for h in found]
            print(f'색인 {idx} → .abc 링크 {len(links)}개', flush=True)
            break
        print(f'색인 {idx}: .abc 링크 없음 (길이 {len(html)})', flush=True)
    links = sorted(set(links))
    if not links:
        print('!! .abc 링크를 찾지 못했다 — 색인 구조 확인 필요', flush=True)
        return

    os.makedirs(RAW, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    catalog = load_catalog()
    done = {e['source_url'] for e in catalog}
    added = failed = 0
    for url in links:
        if url in done:
            continue
        try:
            abc = fetch(url)
        except Exception as e:
            print(f'  ! 받기 실패: {url} — {e}', flush=True)
            failed += 1
            continue
        time.sleep(0.7)  # 작은 사이트 예절
        title = abc_field(abc, 'T') or os.path.splitext(
            os.path.basename(url))[0].replace('_', ' ')
        composer = abc_field(abc, 'C') or 'Traditional'
        safe = re.sub(r'[^A-Za-z0-9._-]', '_', title)[:80] or 'hymn'
        out_pdf = os.path.join(RAW, safe + '.pdf')
        out_mid = os.path.join(MIDS, 'h_' + safe + '.mid')
        n = 2
        while os.path.exists(out_pdf):
            out_pdf = os.path.join(RAW, f'{safe}-{n}.pdf')
            out_mid = os.path.join(MIDS, f'h_{safe}-{n}.mid')
            n += 1
        try:
            ok = convert(abc, out_pdf, out_mid)
        except Exception as e:
            print(f'  ! 변환 예외: {url} — {e}', flush=True)
            ok = False
        if not ok:
            print(f'  ! 변환 실패: {url}', flush=True)
            failed += 1
            continue
        entry = {
            'source': 'openhymnal',
            'source_url': url,
            'file': os.path.relpath(out_pdf, ROOT),
            'title': title,
            'composer': composer,
            'instrument': 'Hymn',
            'license': 'Public Domain',
        }
        if os.path.exists(out_mid):
            entry['midi'] = os.path.relpath(out_mid, ROOT)
        catalog.append(entry)
        done.add(url)
        added += 1
        if added % 25 == 0:
            print(f'  … {added}곡 완료', flush=True)
            save_catalog(catalog)
    save_catalog(catalog)
    print(f'찬송가 신규 {added}곡, 실패 {failed}곡, 카탈로그 총 {len(catalog)}곡',
          flush=True)


if __name__ == '__main__':
    main()
