#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""찬송가 조옮김 악보 생성 — Open Hymnal ABC 소스를 ±3반음까지 조옮김.

collect_hymnal.py가 수집한 곡의 source_url(.abc 직링크)에서 ABC를
다시 받아 abc2abc -t 로 조옮김한 뒤 PDF로 렌더한다. 결과는
keys/openhymnal/ 아래에 두고, 카탈로그 곡 항목에
'keys': [{'t': -3, 'file': ...}, ...] 필드를 심는다.

앱은 keys 필드가 있으면 내려받기 때 키 선택 시트를 보여준다.
ABC 원문도 abc/openhymnal/ 에 저장해 다음부터는 재방문 없이 쓴다.

전제: abcm2ps, abcmidi(abc2abc), ghostscript(ps2pdf) 설치.
"""
import json
import os
import re
import subprocess
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYS = os.path.join(ROOT, 'keys', 'openhymnal')
ABCDIR = os.path.join(ROOT, 'abc', 'openhymnal')
CATALOG = os.path.join(ROOT, 'catalog.json')
SHIFTS = [-3, -2, -1, 1, 2, 3]
UA = {'User-Agent': 'free-sheets-collector (public domain hymnal mirror)'}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def load_catalog():
    with open(CATALOG, encoding='utf-8') as f:
        return json.load(f)


def save_catalog(c):
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


def render_pdf(abc_text, out_pdf):
    """ABC → PDF. 성공 여부 반환."""
    tmp_abc = os.path.join(ROOT, '_tmp_t.abc')
    tmp_ps = os.path.join(ROOT, '_tmp_t.ps')
    with open(tmp_abc, 'w', encoding='utf-8') as f:
        f.write(abc_text)
    try:
        r = subprocess.run(['abcm2ps', tmp_abc, '-O', tmp_ps],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not os.path.exists(tmp_ps):
            return False
        r = subprocess.run(['ps2pdf', tmp_ps, out_pdf],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and os.path.exists(out_pdf)
    finally:
        for p in (tmp_abc, tmp_ps):
            if os.path.exists(p):
                os.remove(p)


def transpose(abc_text, t):
    """abc2abc -t 로 조옮김한 ABC를 돌려준다 (실패 시 None)."""
    tmp = os.path.join(ROOT, '_tmp_src.abc')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(abc_text)
    try:
        r = subprocess.run(['abc2abc', tmp, '-t', str(t)],
                           capture_output=True, text=True, timeout=60)
        out = r.stdout
        # abc2abc는 문제 지점을 %표시 줄로 남긴다 — X: 헤더가 있으면 유효.
        if not out or 'X:' not in out:
            return None
        return out
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    os.makedirs(KEYS, exist_ok=True)
    os.makedirs(ABCDIR, exist_ok=True)
    catalog = load_catalog()
    todo = [e for e in catalog
            if e.get('source') == 'openhymnal' and not e.get('keys')]
    print(f'대상 찬송가 {len(todo)}곡 (이미 keys 있는 곡 제외)', flush=True)
    done = failed = 0
    for e in todo:
        stem = os.path.splitext(os.path.basename(e['file']))[0]
        abc_path = os.path.join(ABCDIR, stem + '.abc')
        try:
            if os.path.exists(abc_path):
                with open(abc_path, encoding='utf-8') as f:
                    abc = f.read()
            else:
                abc = fetch(e['source_url'])
                time.sleep(0.7)  # 작은 사이트 예절
                with open(abc_path, 'w', encoding='utf-8') as f:
                    f.write(abc)
        except Exception as ex:
            print(f'  ! ABC 받기 실패: {e["source_url"]} — {ex}', flush=True)
            failed += 1
            continue
        keys = []
        for t in SHIFTS:
            tag = f'+{t}' if t > 0 else str(t)
            out_pdf = os.path.join(KEYS, f'{stem}_t{tag}.pdf')
            if not os.path.exists(out_pdf):
                ta = transpose(abc, t)
                if ta is None or not render_pdf(ta, out_pdf):
                    continue
            keys.append({'t': t, 'file': os.path.relpath(out_pdf, ROOT)})
        if keys:
            e['keys'] = keys
            done += 1
        else:
            failed += 1
        if done % 20 == 0 and done:
            save_catalog(catalog)
            print(f'  … {done}곡 완료', flush=True)
    save_catalog(catalog)
    total = sum(len(e.get('keys', [])) for e in catalog)
    print(f'조옮김 완료 {done}곡 / 실패 {failed}곡, 조옮김 악보 총 {total}벌',
          flush=True)


if __name__ == '__main__':
    main()
