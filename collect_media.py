"""라이브러리 부가 미디어 수집 — 썸네일(전곡) + 미디(가능한 곡).

- 썸네일: 각 PDF 1쪽을 480px WebP로 렌더 → thumbs/<경로>.webp
- 미디:
  * mutopia: 악보 URL의 -a4.pdf → .mid 로 치환해 내려받기
  * pdmx: PDMX.csv 로 (pdf 해시 앞 12자 → mid 경로) 맵을 만들고
          mid.tar.gz 를 스트리밍하며 해당 곡만 추출
  * openscore_lieder: 1단계에서는 제외 (MuseScore 재렌더 필요)
- catalog.json 에 thumb / midi 필드 추가
"""
import csv
import io
import json
import os
import subprocess
import tarfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (public-domain collector)'}
ZEN = 'https://zenodo.org/api/records/15571083/files'


def fetch(url, binary=True, retries=3, timeout=120):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print(f'  ! fetch 실패({i+1}/{retries}) {url} — {e}', flush=True)
            time.sleep(2 * (i + 1))
    return None


def make_thumb(pdf_path, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + '.tmp'
    try:
        subprocess.run(
            ['pdftoppm', '-f', '1', '-l', '1', '-scale-to', '480',
             '-singlefile', '-png', pdf_path, tmp],
            check=True, capture_output=True, timeout=60)
        subprocess.run(
            ['cwebp', '-quiet', '-q', '55', tmp + '.png', '-o', out_path],
            check=True, capture_output=True, timeout=60)
        return True
    except Exception as e:
        print(f'  ! 썸네일 실패 {pdf_path} — {e}', flush=True)
        return False
    finally:
        if os.path.exists(tmp + '.png'):
            os.remove(tmp + '.png')


def main():
    catalog = json.load(open(CATALOG, encoding='utf-8'))

    # ── 1) 썸네일 (전곡) ──
    made = have = fail = 0
    for e in catalog:
        pdf = os.path.join(ROOT, e['file'])
        if not os.path.exists(pdf):
            continue
        rel = e['file']
        if rel.startswith('raw/'):
            rel = rel[4:]
        thumb_rel = 'thumbs/' + os.path.splitext(rel)[0] + '.webp'
        out = os.path.join(ROOT, thumb_rel)
        if os.path.exists(out):
            e['thumb'] = thumb_rel
            have += 1
            continue
        if make_thumb(pdf, out):
            e['thumb'] = thumb_rel
            made += 1
        else:
            fail += 1
        if (made + fail) % 200 == 0 and made + fail:
            print(f'  썸네일 진행 {made+fail}…', flush=True)
    print(f'썸네일: 신규 {made}, 기존 {have}, 실패 {fail}', flush=True)

    # ── 2) Mutopia 미디 ──
    got = 0
    for e in catalog:
        if e['source'] != 'mutopia' or e.get('midi'):
            continue
        src = e['source_url']
        if not src.endswith('-a4.pdf'):
            continue
        mid_url = src[:-len('-a4.pdf')] + '.mid'
        rel = e['file']
        if rel.startswith('raw/'):
            rel = rel[4:]
        mid_rel = 'mids/' + os.path.splitext(rel)[0] + '.mid'
        out = os.path.join(ROOT, mid_rel)
        if os.path.exists(out):
            e['midi'] = mid_rel
            continue
        data = fetch(mid_url)
        if data and data[:4] == b'MThd':
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'wb') as f:
                f.write(data)
            e['midi'] = mid_rel
            got += 1
            time.sleep(1.0)
    print(f'Mutopia 미디: 신규 {got}', flush=True)

    # ── 3) PDMX 미디 ──
    pdmx = [e for e in catalog
            if e['source'] == 'pdmx' and not e.get('midi')]
    if pdmx:
        # 파일명 속 해시 앞 12자로 곡을 되찾는다
        want_prefix = {}
        for e in pdmx:
            base = os.path.basename(e['file'])          # 제목-Qm12자.pdf
            prefix = os.path.splitext(base)[0].rsplit('-', 1)[-1]
            want_prefix[prefix] = e
        # CSV에서 (해시 12자 → mid 경로) 맵
        mid_of = {}
        req = urllib.request.Request(f'{ZEN}/PDMX.csv/content', headers=UA)
        with urllib.request.urlopen(req, timeout=600) as r:
            text = io.TextIOWrapper(r, encoding='utf-8', errors='replace')
            for row in csv.DictReader(text):
                pdfp = row.get('pdf', 'NA')
                midp = row.get('mid', 'NA')
                if pdfp == 'NA' or midp == 'NA':
                    continue
                h = os.path.splitext(os.path.basename(pdfp))[0][:12]
                if h in want_prefix:
                    mid_of[midp.lstrip('./')] = want_prefix[h]
        print(f'PDMX 미디 대상 {len(mid_of)}곡, mid.tar.gz 스트리밍', flush=True)
        got = 0
        req = urllib.request.Request(f'{ZEN}/mid.tar.gz/content', headers=UA)
        with urllib.request.urlopen(req, timeout=600) as r:
            with tarfile.open(fileobj=r, mode='r|gz') as tf:
                remaining = len(mid_of)
                for m in tf:
                    if remaining <= 0:
                        break
                    if not m.isfile():
                        continue
                    e = mid_of.get(m.name.lstrip('./'))
                    if e is None:
                        continue
                    remaining -= 1
                    data = tf.extractfile(m).read()
                    if data[:4] != b'MThd':
                        continue
                    rel = e['file']
                    if rel.startswith('raw/'):
                        rel = rel[4:]
                    mid_rel = 'mids/' + os.path.splitext(rel)[0] + '.mid'
                    out = os.path.join(ROOT, mid_rel)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with open(out, 'wb') as f:
                        f.write(data)
                    e['midi'] = mid_rel
                    got += 1
        print(f'PDMX 미디: 신규 {got}', flush=True)

    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    n_thumb = sum(1 for e in catalog if e.get('thumb'))
    n_midi = sum(1 for e in catalog if e.get('midi'))
    print(f'카탈로그 갱신 — 썸네일 {n_thumb}, 미디 {n_midi} / {len(catalog)}',
          flush=True)


if __name__ == '__main__':
    main()
