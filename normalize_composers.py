#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""작곡가 표기 정규화 — 앱 표지 오버라인에 그대로 실리는 값이라
지저분한 표기(BeethovenLv, 생몰연도, 편곡자 뒤섞임, 전부대문자,
성-이름 뒤집힘, Traditional 변형 7종…)를 일괄 교정한다.

sanitize_catalog.py가 병합 뒤마다 함께 실행한다. 재실행 안전(멱등).
원본 표기를 복원할 일은 없다 — 소스 URL이 카탈로그에 남아 있다.
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')

# ── 정식 표기 사전: 별칭(소문자·구두점 제거) → 정식 이름 ──
# 자주 나오는 정전 작곡가 위주. 키는 _key()로 정규화해 비교한다.
_CANON_ALIASES = {
    'Johann Sebastian Bach': [
        'bach', 'js bach', 'j s bach', 'bach js', 'bach johann sebastian',
        'johann sebastian bach', 'j sebastian bach', 'jsbach',
    ],
    'Ludwig van Beethoven': [
        'beethoven', 'l v beethoven', 'lv beethoven', 'beethoven lv',
        'ludwig van beethoven', 'beethoven ludwig van', 'l van beethoven',
    ],
    'Frédéric Chopin': [
        'chopin', 'f chopin', 'f f chopin', 'frederic chopin',
        'fryderyk chopin',
        'chopin frederic', 'frederic francois chopin',
    ],
    'Wolfgang Amadeus Mozart': [
        'mozart', 'w a mozart', 'wa mozart', 'wolfgang amadeus mozart',
        'mozart wolfgang amadeus', 'w amadeus mozart',
    ],
    'Franz Schubert': ['schubert', 'f schubert', 'franz schubert',
                       'schubert franz'],
    'Johannes Brahms': ['brahms', 'j brahms', 'johannes brahms',
                        'brahms johannes'],
    'Franz Liszt': ['liszt', 'f liszt', 'franz liszt', 'liszt franz'],
    'Claude Debussy': ['debussy', 'c debussy', 'claude debussy',
                       'cl a debussy', 'craude debussy', 'debussy claude'],
    'Pyotr Ilyich Tchaikovsky': [
        'tchaikovsky', 'p tchaikovsky', 'pyotr ilyich tchaikovsky',
        'peter tschaikowsky', 'tschaikowsky', 'p i tchaikovsky',
        'piotr tchaikovsky', 'tchaikovsky pyotr ilyich',
    ],
    'Niccolò Paganini': ['paganini', 'n paganini', 'niccolo paganini',
                         'nicolo paganini', 'paganini niccolo'],
    'Erik Satie': ['satie', 'e satie', 'erik satie', 'satie erik'],
    'Henry Purcell': ['purcell', 'h purcell', 'henry purcell'],
    'Antonio Vivaldi': ['vivaldi', 'a vivaldi', 'antonio vivaldi'],
    'Tomaso Albinoni': ['albinoni', 't albinoni', 'tomaso albinoni'],
    'George Frideric Handel': [
        'handel', 'haendel', 'g f handel', 'gf handel',
        'george frideric handel', 'georg friedrich handel',
    ],
    'Joseph Haydn': ['haydn', 'j haydn', 'joseph haydn', 'franz joseph haydn'],
    'Felix Mendelssohn': [
        'mendelssohn', 'f mendelssohn', 'felix mendelssohn',
        'felix mendelssohn bartholdy', 'mendelssohn bartholdy',
    ],
    'Robert Schumann': ['schumann', 'r schumann', 'robert schumann'],
    'Edvard Grieg': ['grieg', 'e grieg', 'edvard grieg'],
    'Antonín Dvořák': ['dvorak', 'a dvorak', 'antonin dvorak'],
    'Camille Saint-Saëns': ['saint saens', 'c saint saens',
                            'camille saint saens'],
    'Carl Czerny': ['czerny', 'c czerny', 'carl czerny'],
    'Maurice Ravel': ['ravel', 'm ravel', 'maurice ravel'],
    'Gabriel Fauré': ['faure', 'g faure', 'gabriel faure'],
    'Georg Philipp Telemann': ['telemann', 'g p telemann',
                               'georg philipp telemann'],
    'Johann Pachelbel': ['pachelbel', 'j pachelbel', 'johann pachelbel'],
    'Arcangelo Corelli': ['corelli', 'a corelli', 'arcangelo corelli'],
    'Domenico Scarlatti': ['scarlatti', 'd scarlatti', 'domenico scarlatti'],
    'Muzio Clementi': ['clementi', 'm clementi', 'muzio clementi'],
    'Friedrich Burgmüller': ['burgmuller', 'f burgmuller',
                             'friedrich burgmuller', 'burgmueller'],
    'Jean-Baptiste Arban': ['arban', 'j b arban', 'jean baptiste arban'],
    'Matteo Carcassi': ['carcassi', 'm carcassi', 'matteo carcassi'],
    'Ferdinando Carulli': ['carulli', 'f carulli', 'ferdinando carulli'],
    'Fernando Sor': ['sor', 'f sor', 'fernando sor'],
    'Mauro Giuliani': ['giuliani', 'm giuliani', 'mauro giuliani'],
    'Dionisio Aguado': ['aguado', 'd aguado', 'dionisio aguado'],
    'Sergei Lyapunov': ['s liapunow', 'liapunow', 'lyapunov',
                        'sergei lyapunov'],
    'Georges Bizet': ['bizet', 'g bizet', 'georges bizet'],
    'Edward MacDowell': ['macdowell', 'edward macdowell', 'e macdowell'],
    'Edward Elgar': ['elgar', 'e elgar', 'edward elgar', 'elgar edward',
                     'eward elgar'],
    'William B. Bradbury': ['wm b bradbury', 'w b bradbury',
                            'william b bradbury'],
}
CANON = {}
for canonical, aliases in _CANON_ALIASES.items():
    for a in aliases:
        CANON[a] = canonical

# 무명·전통곡 표기 — 전부 아래 두 가지로 수렴.
_TRAD = re.compile(
    r'^(misc\s+)?(trad(itional|itionell|icional|itionnel)?\.?|volkslied|'
    r'folk( song)?)\b', re.I)
_ANON = re.compile(
    r'^(anon(ymous|ymus|yme)?\.?|unknown|unbekannt|urheber unbekannt|'
    r'autor:? desconocido|desconocido|composer unknown)\b', re.I)

_URL = re.compile(r'https?://\S+')
_PAREN = re.compile(r'\([^)]*\)')
# 편곡·채보 표기의 시작점 — 그 앞까지가 작곡가.
_ARR = re.compile(
    r'(?i)[\s,;/·—-]*\b(arr(anged|angement|angiert)?\s*(by)?[.:]?|'
    r'arreglo[.:]?|arranger[.:]?|trans(cribed|cription)?\s*(by)?[.:]?|'
    r'annotated\s*by|edited\s*by|composed\s*by|expanded\s*by)\b')
# 이름에 붙어 버린 작품번호·연도 꼬리.
_OPUS_TAIL = re.compile(r'(?i)[\s,._-]*\b(op|opus|no|nr|bwv|k|kv|woO)\b'
                        r'[\s.]*\d.*$')
_YEARS_TAIL = re.compile(r'[\s,.]*\d{4}\s*[–-]?\s*(\d{2,4})?[\s,.]*$')


def _key(s):
    """별칭 비교용 키 — 소문자, 발음구별기호·구두점 제거."""
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'[^a-zA-Z ]+', ' ', s.lower())
    return re.sub(r'\s+', ' ', s).strip()


def _decamel(s):
    """공백 없는 낙타붙임(FelixMendelssohn)을 띄운다. Mc/Mac은 보존."""
    if ' ' in s:
        return s
    s = re.sub(r'([a-zà-öø-ÿ])([A-ZÀ-Þ])', r'\1 \2', s)
    s = re.sub(r'\bMc ([A-Z])', r'Mc\1', s)
    s = re.sub(r'\bMac ([A-Z])', r'Mac\1', s)
    return s


def _titlecase_upper(s):
    """전부 대문자인 낱말(4자+)만 첫 글자 대문자로 — 이니셜(J.S.)은 보존."""
    def fix(w):
        if len(w) > 3 and w.isupper():
            return w.capitalize()
        return w
    return ' '.join(fix(w) for w in s.split())


def normalize(raw):
    """작곡가 한 명 표기를 정리해 돌려준다."""
    s = (raw or '').strip()
    if not s:
        return ''
    if _TRAD.match(s):
        return 'Traditional'
    if _ANON.match(s):
        return 'Anonymous'
    # 찬송가류 통짜 표기 — "Words: 작사자… Music: '곡조' 작곡자, 연도…"
    # 에서 곡조 작곡가를 뽑는다. Music이 없으면 작사자라도 남긴다.
    if re.match(r'(?i)\s*(words|lyrics|text|music|composers?)\b', s):
        m = re.search(
            r"(?i)\bmusic(\s+and\s+setting|\s*&\s*lyrics)?\s*:?\s*"
            r"(?:'[^']*'|\"[^\"]*\")?\s*(.+)$", s)
        cand = ''
        if m:
            cand = m.group(2)
        else:
            m = re.match(r"(?i)\s*(?:words|lyrics|text)\s*:?\s*(.+)$", s)
            if m:
                cand = m.group(1)
        if cand:
            # 연도·역자·부가 설명 앞에서 자른다.
            cand = re.split(
                r'(?i),|\s+\d{4}|\bcirca\b|\btranslat|\bparaphras|'
                r'\badapt|\bsetting\b|\baltered\b|\bwords\b|\blyrics\b',
                cand)[0]
            # 곡조명 따옴표·괄호·절 표기(verses 1-2 …)·or 접두를 걷어낸다.
            cand = re.sub(r"'[^']*'|\"[^\"]*\"", ' ', cand)
            cand = re.sub(r'\([^)]*\)?', ' ', cand)
            cand = re.sub(r'(?i)^\s*or\s+', '', cand)
            cand = re.sub(
                r'(?i)^\s*((verses?|stanzas?|vs|st|v)\.?\s*'
                r'[\d,&\- ]*(by\s+)?)+', '', cand)
            cand = re.sub(r'(?i)^by\s+', '', cand)
            cand = re.sub(r'\s+', ' ', cand).strip(' .:-,')
            if re.search(r'[A-Za-z]', cand):
                s = cand
            else:
                # 절 번호만 남고 이름이 없으면 — 작자 미상으로.
                return 'Anonymous'
    s = _URL.sub('', s)
    s = _PAREN.sub(' ', s)
    # 이름에 붙어 버린 'arr.'를 떼어 놓는다 (Mozartarr. → Mozart arr.)
    s = re.sub(r'(?i)(?<=[a-zà-öø-ÿ])(arr[.:])', r' \1', s)
    # 선행어 제거 — 'composed by X', 'attributed to X' → X
    s = re.sub(r'(?i)^\s*(composed\s+by|music\s+by|att?ributed\s+to|attibuted\s+to|'
               r'composers?\s*:|words\s+and\s+music\s*(by)?\s*:?)\s*',
               '', s)
    # 'composed by X arranged by Y' → X. 앞부분이 비면 원문 유지
    # (작곡가 없이 편곡자만 있는 경우 정보를 지우지 않는다).
    m = _ARR.search(s)
    if m and s[:m.start()].strip(' ,;-'):
        s = s[:m.start()]
    s = _OPUS_TAIL.sub('', s)
    s = _YEARS_TAIL.sub('', s)
    s = _decamel(s.strip(' ,;:-·'))
    # 낙타붙임을 뗀 뒤에도 작품번호 꼬리가 남을 수 있다 (ChopinOp.55)
    s = _OPUS_TAIL.sub('', s)
    s = re.sub(r'\s+', ' ', s).strip(' ,;:-·')
    if not s:
        return (raw or '').strip()
    # '성, 이름' → '이름 성'
    m = re.match(r'^([^,]+),\s*(.+)$', s)
    if m and len(m.group(2).split()) <= 3:
        s = f'{m.group(2).strip()} {m.group(1).strip()}'
    canon = CANON.get(_key(s))
    if canon:
        return canon
    if _TRAD.match(s):
        return 'Traditional'
    if _ANON.match(s):
        return 'Anonymous'
    # 붙어 버린 무명 표기 (unbekanntDatum…) — 키 접두로 잡는다.
    k = _key(s)
    for pre in ('anon', 'unknown', 'urheber unbekannt', 'autor desconocido',
                'desconocido', 'composer unknown'):
        if k.startswith(pre):
            return 'Anonymous'
    if k in ('composer', 'composers'):
        return 'Anonymous'
    return _titlecase_upper(s)


def main():
    catalog = json.load(open(CATALOG, encoding='utf-8'))
    changed = 0
    for e in catalog:
        old = e.get('composer', '')
        new = normalize(old)
        if new != old:
            e['composer'] = new
            changed += 1
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    uniq = len({e.get('composer', '') for e in catalog})
    print(f'작곡가 정규화: {changed}곡 표기 수정, 고유 표기 {uniq}종', flush=True)


if __name__ == '__main__':
    main()
