#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""free-sheets-3(3권·교본) 카탈로그 병합 — 공개 raw로 catalog3.json을
받아 1권 catalog.json에 합친다. 3권 곡은 base(릴리스 URL) 필드로
앱이 그쪽에서 내려받는다. 재실행 안전: 기존 archive 항목 교체.
"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')
VOL3 = ('https://raw.githubusercontent.com/NAKJIKING/'
        'free-sheets-3/main/catalog3.json')
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (catalog merge)'}


def main():
    req = urllib.request.Request(VOL3, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        vol3 = json.loads(r.read().decode('utf-8'))
    ok = [e for e in vol3
          if e.get('base') and e.get('file') and e.get('title')]
    catalog = json.load(open(CATALOG, encoding='utf-8'))
    before = len(catalog)
    catalog = [e for e in catalog if e.get('source') != 'archive']
    catalog.extend(ok)
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    print(f'병합: 1권 {before}곡 → archive {len(ok)}곡 반영, 총 {len(catalog)}곡',
          flush=True)


if __name__ == '__main__':
    main()
