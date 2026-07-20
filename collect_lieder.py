#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenScore Lieder Corpus 수집 — CC0 가곡을 MuseScore CLI로 PDF 렌더링.

전제: 워크플로가 저장소를 ../lieder 에 클론해 두고, mscore(뮤즈스코어 CLI)가
설치되어 있어야 한다. 실행마다 BATCH 곡씩 증분 수집한다.
"""
import json
import os
import re
import subprocess
import sys
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw', 'openscore_lieder')
CATALOG = os.path.join(ROOT, 'catalog.json')
LIEDER = os.environ.get(
    'LIEDER_DIR', os.path.abspath(os.path.join(ROOT, '..', 'lieder_src')))
BATCH = int(os.environ.get('LIEDER_BATCH', '150'))
MSCORE = os.environ.get('MSCORE', 'mscore3')


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
    """MuseScore가 PDF 메타데이터에 넣어주는 실제 곡명 추출."""
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
    if not os.path.isdir(LIEDER):
        print(f'!! lieder 클론 없음: {LIEDER}', file=sys.stderr)
        sys.exit(1)
    # 저장소 구조 샘플 로그 — 경로 규칙 확인용
    sample = sorted(glob.glob(os.path.join(LIEDER, 'scores', '*')))[:5]
    print('scores/ 하위 샘플:', [os.path.basename(s) for s in sample], flush=True)

    all_files = sorted(
        glob.glob(os.path.join(LIEDER, 'scores', '**', '*.mscx'), recursive=True) +
        glob.glob(os.path.join(LIEDER, 'scores', '**', '*.mscz'), recursive=True))
    # 곡 디렉터리당 파일 1개만 (mscz 우선 — MuseScore4는 둘 다 읽음)
    by_dir = {}
    for p in all_files:
        d = os.path.dirname(p)
        if d not in by_dir or p.endswith('.mscz'):
            by_dir[d] = p
    files = sorted(by_dir.values())
    print(f'곡 디렉터리 총 {len(files)}개 (파일 {len(all_files)}개)', flush=True)

    os.makedirs(RAW, exist_ok=True)
    catalog = load_catalog()
    done_srcs = {e['source_url'] for e in catalog}
    # 이미 수집된 곡의 디렉터리 (mscx/mscz 확장자 무관 중복 방지)
    done_dirs = {u.rsplit('/', 1)[0] for u in done_srcs
                 if 'OpenScore/Lieder' in u}
    added = failed = 0
    for path in files:
        if added >= BATCH:
            break
        rel = os.path.relpath(path, LIEDER)
        src_url = f'https://github.com/OpenScore/Lieder/blob/main/{rel}'
        if src_url in done_srcs or src_url.rsplit('/', 1)[0] in done_dirs:
            continue
        parts = rel.split(os.sep)
        # scores/<작곡가>/<작품집>/<곡>... 구조 가정 — 로그로 검증 후 조정
        composer = nice(parts[1]) if len(parts) > 2 else ''
        title = nice(os.path.splitext(parts[-1])[0])
        out = os.path.join(
            RAW, re.sub(r'[^A-Za-z0-9._-]', '_', f'{composer}-{title}')[:80] + '.pdf')
        try:
            r = subprocess.run(
                [MSCORE, '-o', out, path],
                capture_output=True, text=True, timeout=120)
            if r.returncode != 0 or not os.path.exists(out):
                print(f'  ! 렌더 실패: {rel} — {r.stderr[:200]}', flush=True)
                failed += 1
                continue
        except Exception as e:
            print(f'  ! 예외: {rel} — {e}', flush=True)
            failed += 1
            continue
        title = pdf_title(out) or title
        catalog.append({
            'source': 'openscore_lieder',
            'source_url': src_url,
            'file': os.path.relpath(out, ROOT),
            'title': title,
            'composer': composer,
            'instrument': 'Voice+Piano',
            'license': 'CC0',
        })
        done_srcs.add(src_url)
        added += 1
        if added % 10 == 0:
            print(f'  … {added}곡 완료', flush=True)
    save_catalog(catalog)
    print(f'Lieder 신규 {added}곡, 실패 {failed}곡, 카탈로그 총 {len(catalog)}곡',
          flush=True)


if __name__ == '__main__':
    main()
