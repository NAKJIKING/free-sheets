#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenScore String Quartets 수집 — CC0 현악사중주를 MuseScore CLI로
PDF+미디 렌더링. Lieder 수집기와 같은 구조 (QUARTETS_DIR 클론 전제).
"""
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw', 'openscore_quartets')
MIDS = os.path.join(ROOT, 'mids')
CATALOG = os.path.join(ROOT, 'catalog.json')
SRC = os.environ.get(
    'QUARTETS_DIR', os.path.abspath(os.path.join(ROOT, 'quartets_src')))
MSCORE = os.environ.get('MSCORE', 'mscore4')


def load_catalog():
    if os.path.exists(CATALOG):
        with open(CATALOG, encoding='utf-8') as f:
            return json.load(f)
    return []


def save_catalog(c):
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


def nice(name):
    return re.sub(r'[_]+', ' ', name).strip()


def pdf_title(path):
    try:
        data = open(path, 'rb').read(200000)
        m = re.search(rb'/Title \((.*?)\)\s*/', data, re.S) or \
            re.search(rb'/Title \((.*?)\)', data)
        if not m:
            return None
        raw = m.group(1)
        if raw.startswith(b'\xfe\xff'):
            t = raw[2:].decode('utf-16-be', 'replace').strip()
        else:
            t = raw.decode('latin-1', 'replace').strip()
        return t if len(t) > 2 else None
    except Exception:
        return None


def main():
    if not os.path.isdir(SRC):
        print(f'!! quartets 클론 없음: {SRC}', file=sys.stderr)
        sys.exit(1)
    sample = sorted(glob.glob(os.path.join(SRC, 'scores', '*')))[:5]
    print('scores/ 하위 샘플:', [os.path.basename(s) for s in sample], flush=True)

    all_files = sorted(
        glob.glob(os.path.join(SRC, 'scores', '**', '*.mscx'), recursive=True) +
        glob.glob(os.path.join(SRC, 'scores', '**', '*.mscz'), recursive=True))
    # 같은 곡의 mscx/mscz 짝만 합치고, 한 폴더에 악장이 여럿이어도 유지.
    by_key = {}
    for p in all_files:
        key = os.path.join(os.path.dirname(p), os.path.splitext(os.path.basename(p))[0])
        if key not in by_key or p.endswith('.mscz'):
            by_key[key] = p
    files = sorted(by_key.values())
    print(f'악장 파일 총 {len(files)}개 (원본 {len(all_files)}개)', flush=True)

    os.makedirs(RAW, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    catalog = load_catalog()
    done = {e['source_url'] for e in catalog}
    added = failed = 0
    for path in files:
        rel = os.path.relpath(path, SRC)
        src_url = f'https://github.com/OpenScore/StringQuartets/blob/main/{rel}'
        if src_url in done:
            continue
        parts = rel.split(os.sep)
        composer = nice(parts[1]) if len(parts) > 2 else ''
        stem = nice(os.path.splitext(parts[-1])[0])
        setname = nice(parts[-2]) if len(parts) > 3 else ''
        base_title = f'{setname} – {stem}' if setname and setname != composer else stem
        safe = re.sub(r'[^A-Za-z0-9._-]', '_', f'{composer}-{base_title}')[:80]
        out_pdf = os.path.join(RAW, safe + '.pdf')
        out_mid = os.path.join(MIDS, 'q_' + safe + '.mid')
        try:
            r = subprocess.run([MSCORE, '-o', out_pdf, path],
                               capture_output=True, text=True, timeout=180)
            if r.returncode != 0 or not os.path.exists(out_pdf):
                print(f'  ! PDF 실패: {rel} — {(r.stderr or "")[:150]}', flush=True)
                failed += 1
                continue
            r2 = subprocess.run([MSCORE, '-o', out_mid, path],
                                capture_output=True, text=True, timeout=180)
            midi_rel = ''
            if r2.returncode == 0 and os.path.exists(out_mid) \
                    and os.path.getsize(out_mid) > 100:
                midi_rel = os.path.relpath(out_mid, ROOT)
        except Exception as e:
            print(f'  ! 예외: {rel} — {e}', flush=True)
            failed += 1
            continue
        title = pdf_title(out_pdf) or base_title
        entry = {
            'source': 'openscore_quartets',
            'source_url': src_url,
            'file': os.path.relpath(out_pdf, ROOT),
            'title': title,
            'composer': composer,
            'instrument': 'StringQuartet',
            'license': 'CC0',
        }
        if midi_rel:
            entry['midi'] = midi_rel
        catalog.append(entry)
        done.add(src_url)
        added += 1
        if added % 20 == 0:
            print(f'  … {added}곡 완료', flush=True)
            save_catalog(catalog)
    save_catalog(catalog)
    print(f'사중주 신규 {added}곡, 실패 {failed}곡, 카탈로그 총 {len(catalog)}곡',
          flush=True)


if __name__ == '__main__':
    main()
