#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""free-sheets-2(2권) 카탈로그 병합 — 공개 raw URL로 catalog2.json을
받아 1권 catalog.json에 합친다. 2권 곡(pdmx2·imslp 등)은 base
필드(저장소/릴리스 URL)를 달고 있어 앱이 그쪽에서 내려받는다.
재실행해도 안전: base를 가진 항목(=2권 유래) 전부를 걸어내고
새 catalog2로 교체한다.
"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')
VOL2 = ('https://raw.githubusercontent.com/NAKJIKING/'
        'free-sheets-2/main/catalog2.json')
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (catalog merge)'}


def main():
    req = urllib.request.Request(VOL2, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        vol2 = json.loads(r.read().decode('utf-8'))
    ok = [e for e in vol2
          if e.get('base') and e.get('file') and e.get('title')]
    catalog = json.load(open(CATALOG, encoding='utf-8'))
    before = len(catalog)
    catalog = [e for e in catalog if not e.get('base')]
    catalog.extend(ok)
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    print(f'병합: 1권 고유 {before - (before - len(catalog) + len(ok))}곡에 '
          f'2권 {len(ok)}곡 반영, 총 {len(catalog)}곡', flush=True)


if __name__ == '__main__':
    main()
