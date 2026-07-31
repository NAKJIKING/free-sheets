#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카탈로그 검사 — 차단된 곡이 다시 실려 있으면 실패한다.

`sanitize_catalog.py` 는 걸러내는 쪽이고, 이 스크립트는 걸러졌는지
확인하는 쪽이다. 병합 워크플로에서 sanitize 다음에 돌려, 규칙이
망가졌거나 sanitize 를 빠뜨린 채 커밋되는 일을 막는다.

2026-07 점검에서 이미 차단 목록에 있던 52건 중 13건이 카탈로그에
그대로 남아 있었다 — 목록만 있고 검증이 없으면 이렇게 샌다.

실패하면 종료 코드 1.
"""
import json
import os
import sys

import sanitize_catalog as S
from pd_match import is_pd_composer

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')


def violations(cat):
    """(사유, 항목) 목록."""
    bad = []
    for e in cat:
        url = e.get('source_url') or ''
        title = (e.get('title') or '').strip()
        comp = (e.get('composer') or '').strip()
        src = e.get('source') or ''
        why = None
        if url in S.BLOCKED_URLS:
            why = '차단목록'
        elif S.BLOCKED_TITLE.match(title):
            why = '차단제목'
        elif url in S.SESSION_BLOCKED:
            why = 'session작곡가'
        elif S.NON_SCORE_ID.search(url):
            why = '비악보'
        elif S.ARRANGER.search(f'{title} {comp}'):
            why = '편곡자권리'
        elif S.BAD_COMPOSER.match(comp):
            why = '작곡가불명'
        elif comp.lower() in S.BLOCKED_COMPOSERS:
            why = '보호기간중'
        elif src in S.STRICT_PD_SOURCES and not is_pd_composer(comp, ''):
            why = 'PD판정실패'
        elif url in S.ARCHIVE_BLOCKED:
            why = '교본표기미확인'
        elif not title:
            why = '제목없음'
        if why:
            bad.append((why, e))
    return bad


def main():
    cat = json.load(open(CATALOG, encoding='utf-8'))
    bad = violations(cat)
    print(f'검사 대상 {len(cat)}곡')
    if not bad:
        print('통과 — 차단 목록 누수 0건')
        return 0
    seen = {}
    for why, e in bad:
        seen[why] = seen.get(why, 0) + 1
    print(f'실패 — 누수 {len(bad)}건')
    for why, n in sorted(seen.items(), key=lambda x: -x[1]):
        print(f'  {why}: {n}건')
    for why, e in bad[:20]:
        print(f'  · [{why}] {e.get("title", "")[:50]} / '
              f'{e.get("composer", "")[:30]} / {e.get("source_url", "")}')
    print('\n`python3 sanitize_catalog.py` 를 돌려 정리한 뒤 다시 커밋하세요.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
