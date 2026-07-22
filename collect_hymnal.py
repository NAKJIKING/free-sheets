#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Open Hymnal 수집 v2 — 공식 배포 ABC zip을 받아 퍼블릭 도메인
찬송가를 PDF+미디로 변환한다.

1차 시도(색인의 .abc 직링크 크롤링)는 실패했다 — 색인에 직링크가
없고(HTTP 13KB, .abc 0건) HTTPS는 러너에서 접속 실패. 공식 배포는
모든 ABC 소스를 묶은 zip이다 (mobile-download.html).

흐름: 다운로드 페이지들에서 .zip 링크를 찾고 → abc가 든 zip을 받아
→ 안의 .abc를 곡별로 변환(abcm2ps→ps2pdf, abc2midi) → ABC 원문은
abc/openhymnal/ 에 저장(조옮김 배치가 재방문 없이 쓴다).

전제: abcm2ps, abc2midi(abcmidi), ps2pdf(ghostscript) 설치.
"""
import io
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw', 'openhymnal')
MIDS = os.path.join(ROOT, 'mids')
ABCDIR = os.path.join(ROOT, 'abc', 'openhymnal')
CATALOG = os.path.join(ROOT, 'catalog.json')
# HTTPS는 깃허브 러너에서 접속 실패 — 이 사이트는 http로 받는다.
PAGES = [
    'http://openhymnal.org/mobile-download.html',
    'http://openhymnal.org/download.html',
    'http://openhymnal.org/mobile-index.html',
    'http://openhymnal.org/index.html',
]
UA = {'User-Agent': 'free-sheets-collector (public domain hymnal mirror)'}


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
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


def find_zips():
    """다운로드 페이지들에서 zip 링크를 모은다 (abc 우선 정렬)."""
    found = []
    for page in PAGES:
        try:
            html = fetch(page)
        except Exception as e:
            print(f'페이지 실패 {page}: {e}', flush=True)
            continue
        for h in re.findall(r'href=["\']([^"\']+?\.zip)["\']', html, re.I):
            url = urllib.parse.urljoin(page, h)
            if url not in found:
                found.append(url)
        if found:
            print(f'{page} → zip {len(found)}개', flush=True)
    # abc가 이름에 든 zip을 앞으로 — 소스(ABC Plus) 배포본이 목표.
    found.sort(key=lambda u: ('abc' not in u.lower(), u))
    return found


def iter_tunes(zip_bytes):
    """zip 안 .abc 문서를 튜니트 단위(X: 블록)로 나눈다."""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for name in sorted(zf.namelist()):
        if not name.lower().endswith('.abc'):
            continue
        try:
            text = zf.read(name).decode('utf-8', 'replace')
        except Exception:
            continue
        # 파일 하나에 여러 튜니트가 들 수 있다 — X:로 분리,
        # 앞줘(설정 줄)는 모든 튜니트에 공통 적용한다.
        parts = re.split(r'(?=^X:)', text, flags=re.M)
        header = ''
        tunes = []
        for p in parts:
            if p.lstrip().startswith('X:'):
                tunes.append(p)
            elif not tunes:
                header = p
        idx = 0
        for t in tunes:
            idx += 1
            yield (f'{name}#{idx}' if len(tunes) > 1 else name,
                   header + t if header.strip() else t)


def main():
    zips = find_zips()
    if not zips:
        print('!! zip 링크를 찾지 못했다 — 페이지 구조 확인 필요', flush=True)
        return
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(MIDS, exist_ok=True)
    os.makedirs(ABCDIR, exist_ok=True)
    catalog = load_catalog()
    done = {e['source_url'] for e in catalog}
    added = failed = 0
    got_zip = None
    for zu in zips:
        if 'abc' not in zu.lower():
            continue
        try:
            print(f'zip 받는 중: {zu}', flush=True)
            got_zip = (zu, fetch(zu, binary=True))
            break
        except Exception as e:
            print(f'  ! zip 실패: {zu} — {e}', flush=True)
    if got_zip is None:
        # abc 이름이 없으면 모든 zip을 열어 .abc가 든 것을 찾는다.
        for zu in zips:
            try:
                print(f'zip 검사: {zu}', flush=True)
                data = fetch(zu, binary=True)
                zf = zipfile.ZipFile(io.BytesIO(data))
                if any(n.lower().endswith('.abc') for n in zf.namelist()):
                    got_zip = (zu, data)
                    break
            except Exception as e:
                print(f'  ! zip 실패: {zu} — {e}', flush=True)
    if got_zip is None:
        print('!! ABC가 든 zip을 찾지 못했다', flush=True)
        return
    zip_url, zip_bytes = got_zip
    print(f'ABC zip: {zip_url} ({len(zip_bytes)//1024}KB)', flush=True)

    for member, abc in iter_tunes(zip_bytes):
        src = f'{zip_url}#{member}'
        if src in done:
            continue
        title = abc_field(abc, 'T') or os.path.splitext(
            os.path.basename(member))[0].replace('_', ' ')
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
            print(f'  ! 변환 예외: {member} — {e}', flush=True)
            ok = False
        if not ok:
            print(f'  ! 변환 실패: {member}', flush=True)
            failed += 1
            continue
        # ABC 원문 저장 — 조옮김 배치(transpose_hymnal.py)가 바로 쓴다.
        stem = os.path.splitext(os.path.basename(out_pdf))[0]
        with open(os.path.join(ABCDIR, stem + '.abc'), 'w',
                  encoding='utf-8') as f:
            f.write(abc)
        entry = {
            'source': 'openhymnal',
            'source_url': src,
            'file': os.path.relpath(out_pdf, ROOT),
            'title': title,
            'composer': composer,
            'instrument': 'Hymn',
            'license': 'Public Domain',
        }
        if os.path.exists(out_mid):
            entry['midi'] = os.path.relpath(out_mid, ROOT)
        catalog.append(entry)
        done.add(src)
        added += 1
        if added % 50 == 0:
            print(f'  … {added}곡 완료', flush=True)
            save_catalog(catalog)
    save_catalog(catalog)
    print(f'찬송가 신규 {added}곡, 실패 {failed}곡, 카탈로그 총 {len(catalog)}곡',
          flush=True)


if __name__ == '__main__':
    main()
