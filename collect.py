#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""무료 악보 라이브러리 수집기 — 재배포 허용 소스에서 악기별로 다운로드.

GitHub Actions에서 실행된다. 소스별 수집 결과를 free_library/raw/<source>/
아래에 저장하고, 곡마다 메타데이터(제목·작곡가·라이선스·출처 URL)를
free_library/catalog.json 에 누적한다.

v1 소스: Mutopia Project — 전 곡이 Public Domain / CC 라이선스로
재배포가 명시적으로 허용된 유일한 대형 소스라 1순위.
"""
import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw')
CATALOG = os.path.join(ROOT, 'catalog.json')

UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (public-domain collector)'}
PER_INSTRUMENT_CAP = 400         # v2: 사실상 전량 수집 (Mutopia 최대 악기가 ~400곡)
REQUEST_DELAY = 1.5              # 서버 예의용 딜레이(초)

# 대표 악기 (Mutopia 검색 파라미터명 기준)
INSTRUMENTS = [
    'Piano', 'Flute', 'Violin', 'Clarinet', 'Trumpet',
    'Saxophone', 'Cello', 'Guitar',
]

# 재배포 허용으로 취급하는 라이선스 (표기 그대로 보존해 출처 고지에 사용)
OK_LICENSE = re.compile(
    r'(public\s*domain|creative\s*commons)', re.I)


def fetch(url, binary=False, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else data.decode('utf-8', 'replace')
        except Exception as e:
            print(f'  ! fetch 실패({i+1}/{retries}) {url} — {e}', flush=True)
            time.sleep(3 * (i + 1))
    return None


class MutopiaTable(HTMLParser):
    """make-table.cgi 결과에서 곡 블록(제목/작곡가/라이선스/A4 PDF 링크)을 뽑는다."""

    def __init__(self):
        super().__init__()
        self.pieces = []
        self._cur = {}
        self._grab = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and 'href' in a:
            href = a['href']
            if href.endswith('-a4.pdf') or href.endswith('.pdf'):
                # 상대경로 → 절대경로
                if href.startswith('..'):
                    href = 'https://www.mutopiaproject.org/' + href.lstrip('./')
                if 'a4' in href or 'pdf' not in self._cur:
                    self._cur['pdf'] = href
        if tag == 'span' and a.get('class') == 'piece-title':
            self._grab = 'title'
        if tag == 'span' and a.get('class') == 'piece-composer':
            self._grab = 'composer'

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._grab:
            self._cur[self._grab] = self._cur.get(self._grab, '') + text
            self._grab = None
        if 'License' in text or 'license' in text:
            self._cur.setdefault('license_hint', text)
        m = re.search(r'(Public Domain|Creative Commons[^<.]*)', text)
        if m:
            self._cur['license'] = m.group(1).strip()
        # 곡 블록 경계: PDF 링크와 제목이 모이면 확정
        if 'pdf' in self._cur and ('title' in self._cur or len(text) > 0):
            pass

    def flush_piece(self):
        if 'pdf' in self._cur:
            self.pieces.append(dict(self._cur))
        self._cur = {}


def collect_mutopia():
    os.makedirs(os.path.join(RAW, 'mutopia'), exist_ok=True)
    catalog = load_catalog()
    seen_urls = {e['source_url'] for e in catalog}
    added = 0
    debug_dumped = False
    for inst in INSTRUMENTS:
        print(f'== Mutopia: {inst}', flush=True)
        entries = []
        for startat in range(0, 2000, 25):  # 페이지 순회 (전 페이지)
            url = ('https://www.mutopiaproject.org/cgibin/make-table.cgi'
                   f'?Instrument={inst}&startat={startat}')
            html = fetch(url)
            if html is None:
                break
            if not debug_dumped:
                # 파서 개선용 구조 샘플 — 첫 페이지 일부를 로그로
                snippet = re.sub(r'\s+', ' ', html)
                i = snippet.find('.pdf')
                print('--- HTML SAMPLE ---', flush=True)
                print(snippet[max(0, i-1500):i+500], flush=True)
                print('--- END SAMPLE ---', flush=True)
                debug_dumped = True
            page_entries = parse_mutopia_html(html)
            new = [e for e in page_entries
                   if e.get('pdf') not in {x.get('pdf') for x in entries}]
            if not new:
                break
            entries.extend(new)
            if len(entries) >= PER_INSTRUMENT_CAP * 2:
                break
            time.sleep(REQUEST_DELAY)
        print(f'   후보 {len(entries)}곡', flush=True)
        count = 0
        inst_dir = os.path.join(RAW, 'mutopia', inst.lower())
        os.makedirs(inst_dir, exist_ok=True)
        for e in entries:
            if count >= PER_INSTRUMENT_CAP:
                break
            pdf = e.get('pdf')
            lic = e.get('license', '')
            if not pdf or pdf in seen_urls:
                continue
            if lic and not OK_LICENSE.search(lic):
                continue
            fname = re.sub(r'[^A-Za-z0-9._-]', '_', pdf.rsplit('/', 1)[-1])
            dest = os.path.join(inst_dir, fname)
            if not os.path.exists(dest):
                data = fetch(pdf, binary=True)
                if not data or not data.startswith(b'%PDF'):
                    print(f'  ! PDF 아님/실패: {pdf}', flush=True)
                    continue
                with open(dest, 'wb') as f:
                    f.write(data)
                time.sleep(REQUEST_DELAY)
            title = e.get('title') or prettify_filename(fname)
            composer = e.get('composer') or composer_from_url(pdf)
            catalog.append({
                'source': 'mutopia',
                'source_url': pdf,
                'file': os.path.relpath(dest, ROOT),
                'title': title,
                'composer': composer,
                'instrument': inst,
                'license': lic or 'see source page',
            })
            seen_urls.add(pdf)
            count += 1
            added += 1
        print(f'   저장 {count}곡', flush=True)
    save_catalog(catalog)
    print(f'Mutopia 신규 {added}곡, 카탈로그 총 {len(catalog)}곡', flush=True)


def parse_mutopia_html(html):
    """곡 블록 파싱 — <a href=...pdf> 주변의 제목/작곡가/라이선스를 정규식으로."""
    entries = []
    # 결과 테이블은 곡마다 여러 링크(.ly/.mid/.pdf)를 가진 블록이 반복된다
    blocks = re.split(r'<hr\b|<tr\b', html)
    for b in blocks:
        pdfs = re.findall(r'href="([^"]+?\.pdf)"', b)
        if not pdfs:
            continue
        pdf = next((p for p in pdfs if 'a4' in p), pdfs[0])
        if pdf.startswith('..'):
            pdf = 'https://www.mutopiaproject.org/' + pdf.lstrip('./')
        elif pdf.startswith('/'):
            pdf = 'https://www.mutopiaproject.org' + pdf
        title = _first(r'<span[^>]*class="piece-title"[^>]*>([^<]+)', b) or \
            _first(r'<b>([^<]{3,80})</b>', b)
        composer = _first(r'<span[^>]*class="piece-composer"[^>]*>([^<]+)', b) or \
            _first(r'by\s+([A-Z][^<,]{2,50})', b)
        lic = _first(r'(Public Domain|Creative Commons[^<]*)', b)
        entries.append({'pdf': pdf, 'title': (title or '').strip(),
                        'composer': (composer or '').strip(),
                        'license': (lic or '').strip()})
    return entries


def prettify_filename(fname):
    """bwv1008-a4.pdf → Bwv1008 처럼 파일명을 임시 제목으로."""
    base = re.sub(r'(-a4|-let)?\.pdf$', '', fname)
    return re.sub(r'[_-]+', ' ', base).strip().title()


def composer_from_url(url):
    """ftp/<Composer>/... 경로에서 작곡가 디렉터리명 추출."""
    m = re.search(r'/ftp/([^/]+)/', url)
    if not m:
        return ''
    raw = m.group(1)
    # BachJS → Bach, J.S. / Traditional → Traditional
    m2 = re.match(r'([A-Z][a-z]+)([A-Z]{1,3})$', raw)
    if m2:
        initials = '.'.join(m2.group(2)) + '.'
        return f'{m2.group(1)}, {initials}'
    return raw


def _first(pattern, text):
    m = re.search(pattern, text)
    return m.group(1) if m else None


def load_catalog():
    if os.path.exists(CATALOG):
        with open(CATALOG, encoding='utf-8') as f:
            return json.load(f)
    return []


def save_catalog(catalog):
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    collect_mutopia()
    print('done')
