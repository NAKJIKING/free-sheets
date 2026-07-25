#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카탈로그 정리 — 앱에 보이는 품질 문제를 일괄 교정한다.

병합(merge2·merge3) 뒤에 항상 실행한다. 재실행 안전(멱등).

① 제목 없는 항목: 파일명에서 제목 복구 (mutopia 51곡이 앱에서 아예
   안 보이던 문제. 앱은 제목 없는 항목을 건너뛴다)
② 인코딩 깨진 글자: UTF-8을 latin-1로 잘못 읽어 바이트가 유실된 항목.
   되돌릴 수 없으므로 — 제목이 통째로 깨졌으면 제외, 작곡가만 깨졌으면
   작곡가를 비운다.
③ 같은 곡 중복: 같은 작품이 여러 번 올라온 것(예: 파가니니 24 카프리스
   17줄)을 하나로. 단 민속곡(thesession)은 같은 이름의 서로 다른 곡이
   많으므로(예: Paddy Fahey's 29곡) 중복으로 보지 않는다.
④ 정렬: 첫 화면에 알려진 곡이 오도록 소스 우선순위로 재배열.
   민속곡은 뒤로 보낸다.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')

# 깨진 인코딩 판별.
# 주의: Ä·Å·Ö는 스웨덴어·독일어에서 정상으로 쓰인다('Äppelbo Gånglåt',
# 'An eine Äolsharfe'). 정상 표기를 지우지 않도록 손상 고유의 흔적만 잡는다.
#  - 'Ã', 'â€'는 정상 표기에 나오지 않는다 → 손상 확정
#  - 낱말 중간에 오는 대문자 악센트(TraviÄka, SkaÄe, krustÄ)는 손상.
#    정상 표기는 낱말 첫 글자에만 온다(Äppelbo, Är, Ästhetik)
#  - 키릴 오독(Ð·Ñ 연속)은 손상
ACCENT_UPPER = 'ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ'
_MIDWORD = re.compile('[a-zà-öø-ÿ][' + ACCENT_UPPER + ']')
_CYR = re.compile('[ÐÑ][-¿†-›]|[ÐÑ].[ÐÑ]')


def is_broken(s):
    """되돌릴 수 없이 손상된 문자열인지."""
    s = s or ''
    if not s:
        return False
    if 'Ã' in s or 'â€' in s:
        return True
    if _MIDWORD.search(s):
        return True
    # 키릴 오독: Ð/Ñ가 여러 번 반복되면 손상
    if sum(s.count(c) for c in 'ÐÑ') >= 3:
        return True
    return False

# 같은 이름의 다른 곡이 흔한 소스 — 제목 기준 중복 제거에서 제외.
DUP_EXEMPT = {'thesession'}

# 첫 화면 노출 우선순위 (작을수록 앞). 알려진 클래식·교재를 앞에,
# 무명 민속곡을 뒤로.
SOURCE_ORDER = {
    'mutopia': 0,             # 정전 클래식 (큐레이션)
    'openscore_lieder': 1,    # 가곡 정전
    'openscore_quartets': 2,  # 실내악 정전
    'archive': 3,             # 교재·교본
    'pdmx': 4,                # 인기 편곡
    'pdmx2': 5,
    'openhymnal': 6,          # 찬송가
    'thesession': 9,          # 민속곡 — 맨 뒤
}


def title_from_file(path):
    """파일명에서 사람이 읽을 제목을 만든다.

    'raw/mutopia/piano/Rumores_de_la-caleta-a4.pdf' → 'Rumores de la Caleta'
    """
    stem = os.path.splitext(os.path.basename(path or ''))[0]
    # 판형·편집 접미사 제거 (-a4, -let, -a4-2 등)
    stem = re.sub(r'-(a4|let|letter)(-\d+)?$', '', stem, flags=re.I)
    stem = re.sub(r'[_-]+', ' ', stem).strip()
    if not stem:
        return ''
    # 전부 소문자면 단어 첫 글자만 대문자로 (이미 대소문자가 섞였으면 존중)
    if stem == stem.lower():
        stem = ' '.join(w[:1].upper() + w[1:] for w in stem.split())
    return stem


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


def main():
    data = json.load(open(CATALOG, encoding='utf-8'))
    before = len(data)
    stat = {'제목복구': 0, '깨짐제외': 0, '작곡가비움': 0, '중복제거': 0}

    out = []
    for e in data:
        title = (e.get('title') or '').strip()

        # ① 제목 복구
        if not title:
            title = title_from_file(e.get('file'))
            if title:
                e['title'] = title
                stat['제목복구'] += 1
            else:
                continue  # 제목을 못 만들면 목록에 못 쓴다

        # ② 깨진 인코딩
        if is_broken(title):
            stat['깨짐제외'] += 1
            continue
        if is_broken(e.get('composer')):
            e['composer'] = ''
            stat['작곡가비움'] += 1

        out.append(e)

    # ③ 같은 작품 중복 제거 (민속곡 제외).
    #    미디·썸네일이 있는 쪽을 남겨 미리듣기 품질을 지킨다.
    def richness(e):
        return (1 if e.get('midi') else 0) + (1 if e.get('thumb') else 0)

    best = {}
    order = []
    passthru = []
    for e in out:
        if (e.get('source') or '') in DUP_EXEMPT:
            passthru.append(e)
            continue
        key = (norm(e.get('title')), norm(e.get('composer')),
               e.get('instrument') or '')
        if key not in best:
            best[key] = e
            order.append(key)
        else:
            stat['중복제거'] += 1
            if richness(e) > richness(best[key]):
                best[key] = e
    deduped = [best[k] for k in order] + passthru

    # ④ 재배열 (안정 정렬 — 같은 순위 안에서는 기존 순서 유지).
    #    소스 우선순위 → 작곡가가 적힌 곡 먼저.
    #    파일명에서 복구한 제목('Bluemtns' 같은 축약형)은 작곡가가 없어
    #    자연히 뒤로 밀린다. 첫 화면에 알아볼 수 있는 곡이 오게 하는 목적.
    deduped.sort(key=lambda e: (SOURCE_ORDER.get(e.get('source'), 7),
                                0 if (e.get('composer') or '').strip() else 1))

    json.dump(deduped, open(CATALOG, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'정리: {before} → {len(deduped)}곡', flush=True)
    for k, v in stat.items():
        print(f'  {k}: {v}', flush=True)


if __name__ == '__main__':
    main()
