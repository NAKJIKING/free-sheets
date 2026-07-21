#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenScore Lieder 미디 추출 — 카탈로그의 Lieder 곡에 미리 듣기 미디를 채운다.

전제: 워크플로가 OpenScore/Lieder 저장소를 lieder_src 에 클론해 두고,
mscore(뮤즈스코어4 CLI)가 설치되어 있어야 한다. 실행마다 BATCH 곡씩
증분 처리하며, 실패한 곡은 lieder_midi_failed.txt 에 적어 재시도하지 않는다.
"""
import glob
import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')
MIDS = os.path.join(ROOT, 'mids')
FAILED = os.path.join(ROOT, 'lieder_midi_failed.txt')
LIEDER = os.environ.get(
    'LIEDER_DIR', os.path.abspath(os.path.join(ROOT, 'lieder_src')))
BATCH = int(os.environ.get('LIEDER_BATCH', '300'))
MSCORE = os.environ.get('MSCORE', 'mscore4')
PREFIX = 'https://github.com/OpenScore/Lieder/blob/main/'


def load_failed():
    if os.path.exists(FAILED):
        with open(FAILED, encoding='utf-8') as f:
            return {ln.strip() for ln in f if ln.strip()}
    return set()


def main():
    with open(CATALOG, encoding='utf-8') as f:
        catalog = json.load(f)
    os.makedirs(MIDS, exist_ok=True)
    skip = load_failed()
    todo = [e for e in catalog
            if e.get('source') == 'openscore_lieder' and not e.get('midi')
            and e['source_url'] not in skip]
    print(f'미디 없는 Lieder: {len(todo)}곡 (실패 제외 {len(skip)}곡)', flush=True)
    added = failed = 0
    new_failed = []
    for e in todo:
        if added >= BATCH:
            break
        rel = e['source_url'][len(PREFIX):]
        src = os.path.join(LIEDER, rel)
        if not os.path.exists(src):
            # 원본 저장소에서 파일명·확장자가 바뀌었으면 곡 디렉터리에서 찾는다
            d = os.path.dirname(src)
            cands = sorted(glob.glob(os.path.join(d, '*.mscz')) +
                           glob.glob(os.path.join(d, '*.mscx')))
            if not cands:
                print(f'  ! 원본 없음: {rel}', flush=True)
                new_failed.append(e['source_url'])
                failed += 1
                continue
            src = cands[0]
        base = os.path.splitext(os.path.basename(e['file']))[0]
        out = os.path.join(MIDS, base + '.mid')
        if os.path.exists(out):
            # 이름 충돌 — 원본 URL 해시로 구분
            h = hashlib.sha1(e['source_url'].encode()).hexdigest()[:8]
            out = os.path.join(MIDS, f'{base}-{h}.mid')
        try:
            r = subprocess.run([MSCORE, '-o', out, src],
                               capture_output=True, text=True, timeout=180)
            if r.returncode != 0 or not os.path.exists(out) \
                    or os.path.getsize(out) < 100:
                print(f'  ! 렌더 실패: {rel} — {(r.stderr or "")[:150]}',
                      flush=True)
                new_failed.append(e['source_url'])
                failed += 1
                continue
        except Exception as ex:
            print(f'  ! 예외: {rel} — {ex}', flush=True)
            new_failed.append(e['source_url'])
            failed += 1
            continue
        e['midi'] = os.path.relpath(out, ROOT)
        added += 1
        if added % 25 == 0:
            print(f'  … {added}곡 완료', flush=True)
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    if new_failed:
        with open(FAILED, 'a', encoding='utf-8') as f:
            for u in new_failed:
                f.write(u + '\n')
    print(f'미디 신규 {added}곡, 실패 {failed}곡, '
          f'남은 {len(todo) - added - failed}곡', flush=True)


if __name__ == '__main__':
    main()
