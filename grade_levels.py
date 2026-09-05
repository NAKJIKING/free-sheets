#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""난이도 등급 자동 분류 — catalog.json 각 곡에 level 을 채운다.

level 값: 1 초급(초등 1~3학년) · 2 중급(초등 4~6학년) · 3 고급(중학 이상).
판단할 근거가 없는 곡은 level 을 두지 않는다(미분류 — 앱은 '전체'에서만
보여준다). 등급은 악기별로 따로 본다 — 같은 곡이라도 바이올린 단선율
편곡과 피아노 원곡은 다르게 나올 수 있다.

판정 순서 (앞쪽이 이긴다):
 ① 작곡가·작품번호·제목 규칙 (rule_level) — 교육 과정에서 자리가 정해진
    곡들. 바이엘·체르니 100번·안나 막달레나 → 초급, 부르크뮐러 25·
    소나티네·인벤션·슈만 유겐트 → 중급, 쇼팽·베토벤 소나타·에튀드·
    4중주 → 고급.
 ② 미디 특징값 점수 — 빠르기(초당 음 수)·리듬(16분음표 비율)·화음·
    음역·임시표 비율·길이·도약. 악기군마다 기준이 다르다.
    특징값은 level_features.json 에 캐시해 두어 미디 파일이 없는
    환경(CI, 2권 저장소 곡)에서도 같은 결과가 난다.
 ③ 미디가 없으면 작곡가 성향 기본값 — 비르투오소 작곡가 고급,
    교재 작곡가 중급, 전통곡 초급.

자체 조판(source=original) 곡에는 추가로 `entry`(입문) 표시를 붙인다.
level 은 그대로 1~3 을 유지한다 — 구버전 앱은 level 만 읽으므로(1~3 밖은
미분류 처리) 새 숫자를 만들면 구버전에서 곡이 사라진다. 새 앱만 entry 를
읽어 '입문' 분류로 보여주고, 구버전은 계속 초급으로 본다. 입문 판정은
ENTRY_IDS 명시 목록이다 — 특징값 게이트는 조표 샤프가 임시표로 잡히는 등
(스핀들러 acc 0.158) 오판이 있어 교재 수록곡을 놓친다.

매 실행마다 전부 새로 계산한다(멱등). 규칙만 고치고 다시 돌리면 된다.
build_all.py --write 가 original 항목을 다시 만들면 entry 가 지워지므로
그 뒤에는 이 스크립트를 꼭 다시 돌린다.

  python3 grade_levels.py                 # catalog.json 갱신
  python3 grade_levels.py --dry --sample 8   # 쓰지 않고 통계·표본만
  python3 grade_levels.py --mids /path/to/free-sheets-2   # 다른 저장소 미디도 읽기
"""
import argparse
import collections
import json
import os
import random
import re
import struct
import sys
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')
FEATURES = os.path.join(ROOT, 'level_features.json')

BEGINNER, INTER, ADV = 1, 2, 3
NAMES = {1: '초급', 2: '중급', 3: '고급', None: '미분류'}

# 입문(진짜 초보) — 자체 조판 단선율 중 첫 교본·동요 수준 곡. 멜로디 id 기준
# (mids/original/<악기>/<id>.mid 의 <id>)이라 9개 악기판에 똑같이 붙는다.
ENTRY_IDS = frozenset({
    # 2026 입문 교재 발굴분 24곡 (전부 입문)
    'cancan', 'lakeside', 'beethoven_rondo', 'nearer', 'rockofages',
    'joytoworld', 'amazing', 'suogan', 'waterwide', 'auldlang', 'firstnoel',
    'camptown', 'kentucky', 'gymno2', 'beyer101', 'gurlitt_sonatina',
    'reinagle', 'karussell', 'spindler', 'behr_may', 'czerny139_1',
    'czerny139_2', 'czerny100_2', 'bach_pol117a',
    # 기존 원본 중 동요·첫걸음급 16곡
    'au_clair', 'butterfly', 'entchen', 'frere', 'hot_cross', 'jingle',
    'kuckuck', 'london_bridge', 'mary_lamb', 'old_macdonald', 'row_boat',
    'twinkle', 'happy_birthday', 'we_wish', 'yankee', 'ode',
})


def is_entry(e):
    """입문 여부 — 자체 조판 곡만 대상, 멜로디 id 로 판정."""
    if e.get('source') != 'original':
        return False
    m = re.search(r'/([^/]+)\.mid$', e.get('midi') or '')
    return bool(m and m.group(1) in ENTRY_IDS)


KEYBOARD = {'Piano', 'Harpsichord', 'Organ', 'Accordion', 'Harp'}
GUITAR = {'Guitar', 'Lute', 'Mandolin'}
MELODIC = {'Violin', 'Viola', 'Cello', 'Flute', 'Clarinet', 'Oboe',
           'Bassoon', 'Trumpet', 'Horn', 'Trombone', 'Saxophone',
           'Recorder', 'Voice'}
LIEDER = {'Voice+Piano'}
FOLK = {'Folk'}
HYMN = {'Hymn'}
ENSEMBLE = {'StringQuartet', 'Orchestra'}
CHOIR = {'Choir'}

# 고음역 문턱 (MIDI 음높이) — 첫째를 넘으면 포지션 이동, 둘째를 넘으면 고포지션.
HIGH_POS = {
    'Violin': (81, 88), 'Viola': (76, 83), 'Cello': (62, 72),
    'Flute': (86, 93), 'Clarinet': (79, 86), 'Oboe': (84, 89),
    'Bassoon': (62, 70), 'Trumpet': (79, 84), 'Horn': (74, 79),
    'Trombone': (65, 70), 'Saxophone': (80, 86), 'Recorder': (86, 93),
    'Voice': (999, 999),
}


# ───────────────────────── 미디 파싱 → 특징값 ─────────────────────────

def _vlq(b, i):
    v = 0
    while True:
        c = b[i]
        i += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, i


def parse_midi(path):
    """(분해능, [(tick, us/beat)], [(on, off, pitch, vel, track)])"""
    b = open(path, 'rb').read()
    if b[:4] != b'MThd':
        raise ValueError('not midi')
    ln, fmt, ntr, div = struct.unpack('>IHHH', b[4:14])
    if div & 0x8000:
        raise ValueError('smpte')
    i = 8 + ln
    tracks = []
    for _ in range(ntr):
        if b[i:i + 4] != b'MTrk':
            break
        tl = struct.unpack('>I', b[i + 4:i + 8])[0]
        tracks.append(b[i + 8:i + 8 + tl])
        i += 8 + tl
    tempos, notes = [], []
    for ti, t in enumerate(tracks):
        i = tick = st = 0
        on = {}
        while i < len(t):
            d, i = _vlq(t, i)
            tick += d
            s = t[i]
            if s == 0xFF:
                typ = t[i + 1]
                l, j = _vlq(t, i + 2)
                if typ == 0x51:
                    tempos.append((tick, int.from_bytes(t[j:j + 3], 'big')))
                i = j + l
                continue
            if s in (0xF0, 0xF7):
                l, j = _vlq(t, i + 1)
                i = j + l
                continue
            if s & 0x80:
                st = s
                i += 1
            hi, ch = st & 0xF0, st & 0x0F
            if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                a, c = t[i], t[i + 1]
                i += 2
                if hi == 0x90 and c > 0:
                    on.setdefault((ch, a), []).append((tick, c))
                elif hi in (0x80, 0x90):
                    lst = on.get((ch, a))
                    if lst:
                        t0, v = lst.pop(0)
                        if ch != 9:
                            notes.append((t0, tick, a, v, ti))
            elif hi in (0xC0, 0xD0):
                i += 1
            else:
                i += 1
        for (ch, a), lst in on.items():
            for t0, v in lst:
                if ch != 9:
                    notes.append((t0, tick, a, v, ti))
    notes.sort()
    return div, tempos, notes


def _stats(notes, div, secs):
    """음표 목록 하나의 특징값."""
    n = len(notes)
    pitches = [x[2] for x in notes]
    groups, onsets = [], []
    for x in notes:
        if onsets and x[0] - onsets[-1] <= div // 8:
            groups[-1].append(x)
        else:
            onsets.append(x[0])
            groups.append([x])
    nons = len(onsets)
    chord = [len(g) for g in groups]
    dur = secs(max(x[1] for x in notes)) - secs(notes[0][0])
    iois = [(onsets[k + 1] - onsets[k]) / div for k in range(nons - 1)]
    pos = sorted(i for i in iois if i > 0)
    pc = collections.Counter(p % 12 for p in pitches)
    maj = (1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1)
    best = max(sum(pc[(k + j) % 12] for j in range(12) if maj[j])
               for k in range(12))
    tops = [max(g, key=lambda x: x[2])[2] for g in groups]
    leaps = sum(1 for k in range(len(tops) - 1)
                if abs(tops[k + 1] - tops[k]) > 12)
    lo = sum(1 for p in pitches if p < 60)
    return {
        'n': n,
        'nps': round(nons / max(dur, 1e-6), 2),          # 초당 타건(화음=1)
        'fast': round(sum(1 for i in iois if 0 < i <= 0.26)
                      / max(1, len(iois)), 2),             # 16분음표 비율
        'med_ioi': round(pos[len(pos) // 2], 3) if pos else 1.0,
        'poly': round(sum(1 for c in chord if c >= 3) / max(1, nons), 2),
        'maxchord': max(chord),
        'big5': round(sum(1 for c in chord if c >= 5) / max(1, nons), 3),  # 5음 이상 화음 비율
        'rng': max(pitches) - min(pitches),
        'lo': min(pitches), 'hi': max(pitches),
        'mean': round(sum(pitches) / n, 1),
        'acc': round(1 - best / n, 3),                     # 조 밖 음 비율
        'dur': round(dur, 1),
        'leaps': round(leaps / max(1, len(tops) - 1), 3),  # 옥타브 넘는 도약
        'both': round(min(lo, n - lo) / n, 2),             # 양손(고저) 균형
    }


def midi_features(path):
    div, tempos, notes = parse_midi(path)
    if not notes:
        return None
    tempos.sort()
    if not tempos or tempos[0][0] > 0:
        tempos.insert(0, (0, 500000))
    segs, t_prev, sec = [], 0, 0.0
    for tk, us in tempos:
        sec += (tk - t_prev) / div * segs[-1][2] / 1e6 if segs else 0
        segs.append((tk, sec, us))
        t_prev = tk

    def secs(tk):
        lo, hi = 0, len(segs) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if segs[mid][0] <= tk:
                lo = mid
            else:
                hi = mid - 1
        tk0, s0, us = segs[lo]
        return s0 + (tk - tk0) / div * us / 1e6

    f = _stats(notes, div, secs)
    by = collections.defaultdict(list)
    for x in notes:
        by[x[4]].append(x)
    tr = [_stats(v, div, secs) for v in by.values() if len(v) >= 8]
    tr.sort(key=lambda t: -t['n'])
    f['tracks'] = [{k: t[k] for k in ('n', 'nps', 'fast', 'med_ioi', 'poly',
                                      'rng', 'lo', 'hi', 'mean', 'acc',
                                      'leaps')} for t in tr[:4]]
    return f


def load_features(cat, extra_dirs):
    """캐시를 읽고, 로컬에 있는 미디는 (크기가 바뀌었으면) 다시 계산한다."""
    cache = {}
    if os.path.exists(FEATURES):
        cache = json.load(open(FEATURES, encoding='utf-8'))
    dirs = [ROOT] + list(extra_dirs)
    new = err = 0
    for e in cat:
        m = e.get('midi')
        if not m:
            continue
        p = next((os.path.join(d, m) for d in dirs
                  if os.path.exists(os.path.join(d, m))), None)
        if p is None:
            continue
        sz = os.path.getsize(p)
        c = cache.get(m)
        if c and c.get('sz') == sz:
            continue
        try:
            f = midi_features(p)
        except Exception:
            f = None
        if f is None:
            err += 1
            cache[m] = {'sz': sz, 'f': None}
        else:
            cache[m] = {'sz': sz, 'f': f}
            new += 1
    # 카탈로그에서 빠진 미디는 캐시에서도 뺀다.
    live = {e.get('midi') for e in cat if e.get('midi')}
    cache = {k: v for k, v in cache.items() if k in live}
    return cache, new, err


# ───────────────────────── 문자열 정리 ─────────────────────────

_SPECIAL = str.maketrans({'ø': 'o', 'ß': 'ss', 'ł': 'l', 'đ': 'd',
                          'æ': 'ae', 'œ': 'oe', '’': "'", '‘': "'",
                          '–': '-', '—': '-'})


def fold(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.translate(_SPECIAL).lower().strip()


def opus_of(tf):
    m = re.search(r'\bop(?:us)?\.?\s*(\d+)', tf)
    if not m:
        return None, None
    op = int(m.group(1))
    rest = tf[m.end():m.end() + 14]
    m2 = re.match(r'\s*[,./:-]?\s*(?:no\.?|nr\.?|n\.?|#)\s*(\d+)', rest)
    return op, (int(m2.group(1)) if m2 else None)


def bwv_of(tf):
    m = re.search(r'\bbwv\s*[-.]?\s*(anh\.?\s*)?(\d+)', tf)
    return (bool(m.group(1)), int(m.group(2))) if m else (None, None)


# 작곡가 식별 — 정규화된 이름·변형 철자·'composer 성 이름' 표기까지.
COMPOSER_KEYS = [
    ('cpebach', r'c\.?\s?p\.?\s?e\.?\s?bach|carl philipp emanuel|philipp emanuel'),
    ('wfbach', r'w\.?\s?f\.?\s?bach|wilhelm friedemann'),
    ('jcbach', r'j\.?\s?c\.?\s?bach|johann christian bach|johann christoph friedrich'),
    ('bach', r'\bbach\b'),
    ('czerny', r'czerny'),
    ('burgmuller', r'burgm'),
    ('clementi', r'clementi'),
    ('kuhlau', r'kuhlau'),
    ('schumann_c', r'clara (wieck|schumann)'),
    ('schumann', r'schumann'),
    ('gurlitt', r'gurlitt'),
    ('diabelli', r'diabelli'),
    ('duvernoy', r'duvernoy'),
    ('lemoine', r'lemoine'),
    ('kohler', r'k[oö]hler'),
    ('streabbog', r'streabbog|gobbaerts'),
    ('beyer', r'\bbeyer\b'),
    ('hanon', r'hanon'),
    ('loeschhorn', r'lo(e)?sch(h)?orn'),
    ('turk', r'\bt[uü]rk\b'),
    ('tartini', r'tartini'),
    ('sousa', r'\bsousa\b'),
    ('bertini', r'bertini'),
    ('heller', r'\bheller\b'),
    ('lichner', r'lichner'),
    ('spindler', r'spindler'),
    ('oesten', r'oesten'),
    ('reinecke', r'reinecke'),
    ('kullak', r'kullak'),
    ('lecouppey', r'couppey'),
    ('concone', r'concone'),
    ('schmitt', r'aloys schmitt|\bschmitt\b'),
    ('lynes', r'\blynes\b'),
    ('biehl', r'\bbiehl\b'),
    ('kirchner', r'kirchner'),
    ('schytte', r'schytte'),
    ('behr', r'\bbehr\b'),
    ('gade', r'\bgade\b'),
    ('sartorio', r'sartorio'),
    ('krogmann', r'krogmann'),
    ('rohde', r'\brohde\b'),
    ('bohm', r'\bb[oö]hm\b'),
    ('lange', r'gustav lange|\blange\b'),
    ('ellmenreich', r'ellmenreich'),
    ('maykapar', r'maykapar|maikapar'),
    ('rebikov', r'rebiko'),
    ('gretchaninov', r'gre(t)?chanino'),
    ('mozart', r'mozart'),
    ('beethoven', r'beethoven'),
    ('haydn', r'\bhaydn\b'),
    ('schubert', r'schubert'),
    ('chopin', r'chopin'),
    ('liszt', r'liszt'),
    ('brahms', r'brahms'),
    ('mendelssohn', r'mendelssohn'),
    ('hensel', r'\bhensel\b|fanny'),
    ('grieg', r'grieg'),
    ('tchaikovsky', r'tchaikov|tschaikow|chaikov'),
    ('rachmaninoff', r'rachmanin'),
    ('scriabin', r'scriabin|skrjabin|skryabin'),
    ('debussy', r'debussy'),
    ('ravel', r'\bravel\b'),
    ('satie', r'\bsatie\b'),
    ('faure', r'\bfaure\b'),
    ('saintsaens', r'saint-?\s?saens'),
    ('bizet', r'\bbizet\b'),
    ('massenet', r'massenet'),
    ('gounod', r'gounod'),
    ('offenbach', r'offenbach'),
    ('albeniz', r'albeniz'),
    ('granados', r'granados'),
    ('alkan', r'\balkan\b'),
    ('thalberg', r'thalberg'),
    ('moscheles', r'moscheles'),
    ('moszkowski', r'moszkowski'),
    ('joplin', r'joplin'),
    ('scarlatti', r'scarlatti'),
    ('handel', r'handel|haendel'),
    ('couperin', r'couperin'),
    ('rameau', r'rameau'),
    ('purcell', r'purcell'),
    ('telemann', r'telemann'),
    ('vivaldi', r'vivaldi'),
    ('corelli', r'corelli'),
    ('pachelbel', r'pachelbel'),
    ('dowland', r'dowland'),
    ('dvorak', r'dvorak'),
    ('smetana', r'smetana'),
    ('mussorgsky', r'mus(s)?orgsk'),
    ('rimsky', r'rimsk'),
    ('borodin', r'borodin'),
    ('glinka', r'glinka'),
    ('balakirev', r'balakirev'),
    ('lyadov', r'l[iy]adov'),
    ('arensky', r'arensky'),
    ('sibelius', r'sibelius'),
    ('elgar', r'\belgar\b'),
    ('holst', r'\bholst\b'),
    ('verdi', r'\bverdi\b'),
    ('puccini', r'puccini'),
    ('rossini', r'rossini'),
    ('wagner', r'wagner'),
    ('weber', r'\bweber\b'),
    ('strauss', r'strauss'),
    ('field', r'john field'),
    ('hummel', r'hummel'),
    ('dussek', r'dussek|dusik'),
    ('cramer', r'\bcramer\b'),
    ('kalkbrenner', r'kalkbrenner'),
    ('herz', r'henri herz|\bherz\b'),
    ('henselt', r'henselt'),
    ('rubinstein', r'rubinstein'),
    ('paderewski', r'paderewski'),
    ('sinding', r'sinding'),
    ('godard', r'godard'),
    ('chaminade', r'chaminade'),
    ('macdowell', r'macdowell'),
    ('gottschalk', r'gottschalk'),
    ('nevin', r'\bnevin\b'),
    ('durand', r'\bdurand\b'),
    ('poldini', r'poldini'),
    ('godowsky', r'godowsky'),
    ('busoni', r'busoni'),
    ('tausig', r'tausig'),
    ('medtner', r'medtner'),
    ('bortkiewicz', r'bortkiewicz'),
    ('gershwin', r'gershwin'),
    ('paganini', r'paganini'),
    ('wieniawski', r'wieniawski'),
    ('sarasate', r'sarasate'),
    ('vieuxtemps', r'vieuxtemps'),
    ('bazzini', r'bazzini'),
    ('sauret', r'\bsauret\b'),
    ('ernst', r'\bernst\b'),
    ('beriot', r'beriot'),
    ('kreutzer', r'kreutzer'),
    ('rode', r'\brode\b'),
    ('fiorillo', r'fiorillo'),
    ('dont', r'\bdont\b'),
    ('gavinies', r'gavinies'),
    ('dancla', r'dancla'),
    ('alard', r'\balard\b'),
    ('mazas', r'\bmazas\b'),
    ('wohlfahrt', r'wohlfahrt'),
    ('kayser', r'\bkayser\b'),
    ('sitt', r'\bsitt\b'),
    ('seitz', r'\bseitz\b'),
    ('rieding', r'rieding'),
    ('kuchler', r'k[uü]chler'),
    ('sevcik', r'sevcik'),
    ('hrimaly', r'hrimaly'),
    ('schradieck', r'schradieck'),
    ('bruch', r'\bbruch\b'),
    ('monti', r'\bmonti\b'),
    ('drdla', r'drdla'),
    ('glazunov', r'glazunov|glazounov'),
    ('bohm_c', r'carl bohm|\bbohm\b'),
    ('gossec', r'gossec'),
    ('boccherini', r'boccherini'),
    ('lully', r'\blully\b'),
    ('popper', r'\bpopper\b'),
    ('servais', r'servais'),
    ('davidov', r'davido[vf]|davydov'),
    ('grutzmacher', r'gr[uü]tzmacher'),
    ('dotzauer', r'dotzauer'),
    ('kummer', r'\bkummer\b'),
    ('klengel', r'klengel'),
    ('romberg', r'romberg'),
    ('goltermann', r'goltermann'),
    ('duport', r'duport'),
    ('franchomme', r'franchomme'),
    ('piatti', r'piatti'),
    ('squire', r'\bsquire\b'),
    ('lee', r'sebastian lee'),
    ('breval', r'breval'),
    ('marcello', r'marcello'),
    ('andersen', r'andersen'),
    ('berbiguier', r'berbiguier'),
    ('furstenau', r'f[uü]rstenau'),
    ('boehm', r'boehm'),
    ('tulou', r'\btulou\b'),
    ('gariboldi', r'gariboldi'),
    ('drouet', r'drouet'),
    ('popp', r'\bpopp\b'),
    ('demersseman', r'demersseman'),
    ('doppler', r'doppler'),
    ('gaubert', r'gaubert|taffanel'),
    ('quantz', r'quantz'),
    ('hotteterre', r'hotteterre'),
    ('loeillet', r'loeillet'),
    ('cavallini', r'cavallini'),
    ('baermann', r'baermann|b[aä]rmann'),
    ('klose', r'klos[eé]'),
    ('rose', r'cyrille rose|\bc\.\s?rose\b'),
    ('lefevre', r'lef[eè]vre'),
    ('stamitz', r'stamitz'),
    ('arban', r'\barban\b'),
    ('clarke_h', r'herbert l(incoln)? clarke|h\.\s?l\.\s?clarke'),
    ('clarke_j', r'jeremiah clarke'),
    ('ferling', r'ferling'),
    ('sor', r'\bsor\b'),
    ('carulli', r'carulli'),
    ('carcassi', r'carcassi'),
    ('giuliani', r'giuliani'),
    ('aguado', r'aguado'),
    ('tarrega', r'tarrega'),
    ('mertz', r'\bmertz\b'),
    ('coste', r'\bcoste\b'),
    ('regondi', r'regondi'),
    ('legnani', r'legnani'),
    ('kuffner', r'k[uü]ffner'),
    ('horetzky', r'horetzky'),
    ('sanz', r'\bsanz\b'),
    ('foster', r'\bfoster\b'),
    ('monteverdi', r'monteverdi|monte pd'),
    ('traditional', r'^traditional$|^anonymous$|^trad\.?$|^anon\.?$|^$'),
]
_CK = [(k, re.compile(p)) for k, p in COMPOSER_KEYS]


def ckey(cf):
    for k, rx in _CK:
        if rx.search(cf):
            return k
    return ''


# 미디가 없어도 성향으로 기본값을 줄 작곡가.
VIRTUOSO = {
    'chopin', 'liszt', 'rachmaninoff', 'scriabin', 'alkan', 'thalberg',
    'moscheles', 'moszkowski', 'albeniz', 'granados', 'debussy', 'ravel',
    'brahms', 'mendelssohn', 'saintsaens', 'balakirev', 'godowsky', 'busoni',
    'tausig', 'henselt', 'medtner', 'joplin', 'gershwin', 'paganini',
    'wieniawski', 'sarasate', 'vieuxtemps', 'bazzini', 'sauret', 'ernst',
    'beriot', 'kreutzer', 'rode', 'fiorillo', 'gavinies', 'popper',
    'servais', 'davidov', 'grutzmacher', 'franchomme', 'piatti', 'duport',
    'mertz', 'coste', 'regondi', 'legnani', 'andersen', 'cavallini',
    'baermann', 'ferling', 'furstenau', 'boehm', 'drouet', 'doppler',
    'demersseman', 'gaubert', 'bruch', 'glazunov', 'sibelius', 'elgar',
    'mussorgsky', 'rimsky', 'borodin', 'glinka', 'smetana', 'dvorak',
    'lyadov', 'arensky', 'hummel', 'cramer', 'kalkbrenner', 'herz',
    'rubinstein', 'paderewski', 'sinding', 'gottschalk', 'chaminade',
    'macdowell', 'field', 'weber', 'bortkiewicz', 'tarrega', 'tartini', 'sousa',
}
PEDAGOGY = {
    'czerny', 'burgmuller', 'clementi', 'kuhlau', 'gurlitt', 'diabelli',
    'duvernoy', 'lemoine', 'kohler', 'streabbog', 'beyer', 'hanon',
    'loeschhorn', 'bertini', 'heller', 'lichner', 'spindler', 'oesten',
    'reinecke', 'kullak', 'lecouppey', 'concone', 'schmitt', 'lynes',
    'biehl', 'kirchner', 'schytte', 'behr', 'gade', 'sartorio', 'krogmann',
    'rohde', 'bohm', 'lange', 'ellmenreich', 'maykapar', 'rebikov', 'turk',
    'wohlfahrt', 'kayser', 'sitt', 'seitz', 'rieding', 'kuchler', 'sevcik',
    'hrimaly', 'schradieck', 'dancla', 'alard', 'mazas', 'dont', 'dotzauer',
    'kummer', 'klengel', 'lee', 'squire', 'goltermann', 'romberg',
    'gariboldi', 'berbiguier', 'tulou', 'popp', 'klose', 'lefevre', 'arban',
    'clarke_h', 'carulli', 'carcassi', 'giuliani', 'sor', 'aguado',
    'kuffner', 'horetzky', 'sanz', 'bohm_c', 'breval', 'marcello',
    'hotteterre', 'loeillet',
}


# ───────────────────────── ① 규칙 ─────────────────────────

def rule_level(e, tf, cf, ck, grp):
    """작곡가·작품번호·제목 규칙. 해당 없으면 None."""
    op, opno = opus_of(tf)
    anh, bwv = bwv_of(tf)
    inst = e.get('instrument') or ''

    def has(p):
        return re.search(p, tf) is not None

    # ── 악기 무관 제목 규칙 ──
    if grp in (ENSEMBLE,):
        return ADV
    # 제목이 스스로 '초보용'이라고 밝히는 교재 — 미디가 없어 작곡가 성향
    # 기본값으로 떨어지면 소르·카이저 같은 대가의 입문 교본이 중급·고급으로
    # 잘못 매겨진다. 실측: 이 규칙에 걸리는 17곡 중 12곡은 이미 초급이라
    # 기존 판정과 일치하고, 5곡(소르 Op.31·Op.35, 디아벨리 기타, 카이저
    # Op.20)만 바로잡힌다.
    if has(r'for beginners?|fur anfanger|vom ersten anfang|ersten unterricht'
           r'|very easy|tres facile|sehr leicht|elementary and progressive'
           r'|elementary studies|vorschule|petite ecole'
           r'|exercices tres faciles|pieces tres faciles'):
        return BEGINNER
    if has(r'concert(o|ino)\b|konzert|concierto') and not has(r'concertino'):
        return ADV
    if has(r'\bconcertino'):
        return INTER
    if has(r'symphon|sinfonie|sinfonia|ouvert|overture|obertura|rhapsod'
           r'|paraphrase|transcri|reminiscence|grande? (fantais|valse|polon|sonat|etude)'
           r'|de concert|brillante|de bravoure|toccata|scherzo|ballade|polonaise'
           r'|(?<!petit)(?<!little) (?:prelude|pr[ae]ludium) and fugue|fugue|fuga\b'
           r'|passacaglia|chaconne|carnival of venice|carnaval de venise'
           r'|moto perpetuo|perpetuum mobile|tarant(elle|ella)|csardas'
           r'|hungarian rhapsod|zigeunerweisen|caprice|capriccio'
           r'|tragedie lyrique|opera\b|oper\b|drame lyrique|vocal score'
           r'|\bdivisions?\b'):
        if not has(r'\b(easy|facile|leicht|petit)'):
            return ADV
    if has(r'sonatin'):
        if ck == 'beethoven' and has(r'\bg\b|g major|g-dur|sol'):
            return BEGINNER
        return INTER
    if has(r'f[uü]r elise|fur elise|for elise|pour elise|para elisa'):
        return INTER
    if has(r'ode to joy|ode an die freude|himno de la alegr|freude sch[oö]ner'
           r'|hymne a la joie|inno alla gioia'):
        return BEGINNER
    if has(r'twinkle|ah,? vous dirai|petite etoile'):
        return ADV if has(r'variation') else BEGINNER
    # ── 작곡가별 ──
    if ck == 'bach':
        if anh and 113 <= bwv <= 132:
            return BEGINNER
        if bwv:
            if 772 <= bwv <= 786 or 924 <= bwv <= 943 or 599 <= bwv <= 644 \
                    or 690 <= bwv <= 771 or 250 <= bwv <= 507:
                return INTER
            if bwv == 846 and not has(r'fug'):
                return INTER
            if bwv >= 525 or 1 <= bwv <= 249:
                return ADV
        if has(r'jesu,? joy|jesus bleibet|wachet auf|sleepers|sheep may|schafe'
               r'|air on|arioso|siciliano|bist du bei mir|ave maria|badinerie'):
            return INTER
        if has(r'\b(minuet|menuet|musette|march|marche|polonaise|gavotte|bourr[eé]e)\b') \
                and not has(r'suite|partita'):
            return BEGINNER if grp is KEYBOARD or grp is MELODIC else INTER
        if has(r'invention'):
            return INTER
        if has(r'sinfonia|wtk|wtc|well.?tempered|wohltemperi|clavier|fug|partita'
               r'|suite|goldberg|chromatic|italian|toccata|sonat|variation'):
            return ADV
        if has(r'chorale|choral'):
            return INTER
        if has(r'pr[ae]elud|prelude|pr[aä]ludium'):
            return INTER
        return None
    if ck == 'czerny':
        if op in (599, 139, 821, 777, 261, 453, 823, 481, 792):
            return BEGINNER
        if op in (849, 636, 335, 553, 718, 802, 840, 748, 261, 337):
            return INTER
        if op in (299, 740, 365, 834, 409, 245, 692, 755, 756):
            return ADV
        if has(r'veloci|gel[aä]ufigkeit|virtuos|brillant|bravour'):
            return ADV
        if has(r'exercise|etude|etuden|studies|stud'):
            return INTER
        return None
    if ck == 'burgmuller':
        if op == 100:
            return INTER
        if op in (105, 109):
            return ADV
        return None
    if ck == 'clementi':
        if op in (36, 37, 38):
            return INTER
        if op == 44 or has(r'gradus'):
            return ADV
        if has(r'sonata|sonate'):
            return ADV
        return None
    if ck == 'kuhlau':
        if op in (20, 55, 59, 60, 88) or has(r'sonatin'):
            return INTER
        if inst == 'Flute' or has(r'sonata|sonate|variation|rondo|fantas'):
            return ADV
        return None
    if ck == 'schumann':
        if op == 68:
            if (opno and opno <= 4) or has(r'melodie|soldatenmarsch|soldier'
                                            r'|tr[aä]llerliedchen|humming|\bchoral'):
                return BEGINNER
            return INTER
        if op in (15, 118, 124):
            return INTER
        if has(r'tr[aä]umerei|reverie|kinderszenen|scenes from childhood'
               r'|album for the young|jugendalbum|album f[uü]r die jugend'):
            return INTER
        if grp is KEYBOARD:
            return ADV
        return None
    if ck == 'gurlitt':
        if op in (101, 117, 130, 140, 82, 187, 190, 205, 210, 211, 228, 166, 155):
            return BEGINNER
        return None
    if ck == 'diabelli':
        return BEGINNER if op == 149 else INTER
    if ck in ('duvernoy',):
        return BEGINNER if op == 176 else INTER
    if ck == 'lemoine':
        return BEGINNER if op == 37 else INTER
    if ck == 'kohler':
        if inst == 'Flute':
            return BEGINNER if op == 93 else (INTER if op in (33, 66, 30) else None)
        return BEGINNER
    if ck in ('streabbog', 'beyer', 'hanon', 'lichner', 'spindler', 'schmitt',
              'lynes', 'biehl', 'schytte', 'behr', 'gade', 'sartorio',
              'krogmann', 'rohde', 'lecouppey', 'ellmenreich', 'maykapar', 'turk'):
        return BEGINNER
    if ck == 'loeschhorn':
        return BEGINNER if op == 65 else INTER
    if ck in ('bertini', 'heller', 'kullak', 'concone', 'kirchner',
              'reinecke', 'lange', 'bohm', 'rebikov', 'gretchaninov'):
        return INTER
    if ck == 'mozart':
        m = re.search(r'\bk\.?\s?v?\.?\s*(\d+)', tf)
        k = int(m.group(1)) if m else None
        if k and k <= 6 and not has(r'sonat'):
            return BEGINNER
        if k == 545 or has(r'facile'):
            return INTER
        if has(r'alla turca|turkish|turc|k\.?\s?331|k\.?\s?265|variation'
               r'|sonat|fantas|rondo|requiem|tuba mirum|lacrimosa'):
            return ADV
        if has(r'\b(minuet|menuet|menuetto|allegro in|andante in|german dance|deutsche)\b') \
                and grp is not LIEDER:
            return BEGINNER
        if has(r'nachtmusik|night music|voi che sapete|non piu andrai|ave verum'):
            return INTER
        return None
    if ck == 'beethoven':
        if has(r'ecossais|german dance|deutscher? t[aä]nz|l[aä]ndler|contredanse'
               r'|country dance|minuet in g|menuett? in g|menuetto in g'):
            return BEGINNER
        if op in (49, 79):
            return INTER
        if op == 119 or has(r'bagatelle') and op not in (33, 126):
            return INTER
        if has(r'sonat|moonlight|mondschein|pathetique|appassionata|waldstein'
               r'|tempest|variation|rondo|andante favori|fantasi'):
            return ADV
        if has(r'romance') and grp is MELODIC:
            return ADV
        return None
    if ck == 'haydn':
        m = re.search(r'hob\.?\s*xvi[:./]\s*(\d+)', tf)
        h = int(m.group(1)) if m else None
        if has(r'sonat'):
            return INTER if (h and h <= 15 and h != 6) else ADV
        if has(r'\b(minuet|menuet|german dance|deutsche|tedesca|allemande)\b'):
            return BEGINNER
        if has(r'variation|fantas|capric'):
            return ADV
        return None
    if ck == 'schubert':
        if has(r'impromptu|sonat|wanderer|fantas|klavierst[uü]ck') and grp is KEYBOARD:
            if has(r'op\.?\s?94|d\.?\s?780') and has(r'no\.?\s?3|nr\.?\s?3'):
                return INTER
            return ADV
        if has(r'moments? musica'):
            return INTER if has(r'no\.?\s?3|nr\.?\s?3|f minor|f-moll') else ADV
        if has(r'ave maria|st[aä]ndchen|serenade|wiegenlied|lullaby|heidenr[oö]slein'
               r'|forelle|trout|an die musik|marche militaire|military march'):
            return INTER
        if has(r'ecossais|german dance|deutsche|l[aä]ndler|waltz|walzer|valse|minuet|menuet'):
            return None  # 특징값으로
        if grp is KEYBOARD and has(r'variation|fantas'):
            return ADV
        return None
    if ck == 'chopin':
        if has(r'(op\.?\s?28|chop 28|prelude|pr[eé]lude)\D{0,12}\b(4|6|7|20)\b'
               r'|prelude.*(e minor|a major|b minor|c minor|op\.?\s?28,? no\.?\s?(4|6|7|20)\b)'):
            return INTER
        if has(r'(waltz|valse|walzer).*(op\.?\s?69,? no\.?\s?2|b minor|a minor|posth|b\.?\s?150|kk)'):
            return INTER
        if has(r'cantabile|largo in e|album leaf|feuille d|polonaise in g minor|b\.?\s?1\b'):
            return INTER
        return ADV
    if ck in ('liszt', 'rachmaninoff', 'scriabin', 'alkan', 'thalberg',
              'moscheles', 'godowsky', 'busoni', 'tausig', 'henselt',
              'medtner', 'balakirev', 'joplin', 'gershwin'):
        if ck == 'liszt' and has(r'consolation|liebestr[aä]um'):
            return ADV
        if ck == 'rachmaninoff' and has(r'vocalise') and grp is not KEYBOARD:
            return INTER
        return ADV
    if ck == 'moszkowski':
        return INTER if op in (91, 77, 18, 92) else ADV
    if ck == 'albeniz':
        return ADV
    if ck == 'granados':
        return INTER if op == 1 or has(r'cuentos|juventud') else ADV
    if ck == 'debussy':
        if has(r'reverie|r[eê]verie|little shepherd|petit berger|petit n[eè]gre'
               r'|little nigar|page d.album|doctor gradus|la fille aux cheveux'
               r'|girl with the flaxen'):
            return INTER
        return ADV
    if ck == 'ravel':
        return ADV
    if ck == 'satie':
        if has(r'gymnop|gnossien'):
            return INTER
        return None
    if ck == 'faure':
        if has(r'berceuse|apr[eè]s un r[eê]ve|sicilienne|pavane') and grp is not KEYBOARD:
            return INTER
        return ADV
    if ck == 'saintsaens':
        if has(r'\bswan\b|cygne|schwan'):
            return INTER
        return ADV
    if ck == 'brahms':
        if has(r'wiegenlied|lullaby|berceuse|cradle'):
            return BEGINNER if grp is not LIEDER else INTER
        if has(r'(waltz|walzer|valse).*(op\.?\s?39)') and has(r'no\.?\s?15|nr\.?\s?15|a flat|as-dur'):
            return INTER
        if has(r'hungarian dance|ungarischer? t[aä]nz') and grp is not KEYBOARD:
            return INTER
        return ADV
    if ck == 'mendelssohn':
        if has(r'(op\.?\s?19|op\.?\s?30|op\.?\s?102).*(no\.?\s?6|nr\.?\s?6)|venetian|venezian|gondol'
               r'|op\.?\s?30.*(no\.?\s?3|nr\.?\s?3)|op\.?\s?53.*(no\.?\s?4|nr\.?\s?4)'):
            return INTER
        if has(r'wedding march|hochzeitsmarsch|marche nuptiale') and grp is not KEYBOARD:
            return INTER
        return ADV
    if ck == 'grieg':
        if op in (12, 38, 43, 47, 54, 57, 62, 65, 68, 71) or has(r'lyri(c|sche)'):
            return INTER
        if has(r'morning|morgenstimmung|solveig|anitra|hall of the mountain|peer gynt'):
            return None
        return ADV
    if ck == 'tchaikovsky':
        if op == 39 or has(r'album for the young|children.?s album|jugendalbum'
                           r'|chanson triste|old french|neapolitan|sweet dream|douce r[eê]verie'):
            return BEGINNER if grp is MELODIC else INTER
        return ADV
    if ck == 'scarlatti':
        m = re.search(r'\b(k|kk|l|longo)\.?\s*(\d+)', tf)
        k = int(m.group(2)) if m and m.group(1).startswith('k') else None
        if k in (32, 34, 40, 63, 73, 95, 322, 391, 431, 440, 453, 83, 42):
            return INTER
        return ADV
    if ck == 'handel':
        if has(r'sarabande|\bair\b|aria|hallelujah|messiah|largo|ombra mai|lascia'
               r'|bourr[eé]e|judas maccab|see the conqu|minuet|menuet|gavotte|hornpipe'
               r'|water music|fireworks|passepied'):
            return INTER if grp is KEYBOARD or grp is LIEDER else BEGINNER
        if has(r'suite|sonat|fug|chaconne|variation|harmonious'):
            return ADV if grp is KEYBOARD else INTER
        return None
    if ck in ('couperin', 'rameau', 'cpebach', 'wfbach'):
        return ADV if grp is KEYBOARD else None
    if ck == 'purcell':
        if has(r'rondeau|abdelazer|trumpet (tune|voluntary)|minuet|menuet|air|hornpipe|march'):
            return BEGINNER if grp is MELODIC else INTER
        return None
    if ck == 'telemann':
        if has(r'fantas'):
            return ADV
        return INTER
    if ck == 'vivaldi':
        if has(r'a minor|a-moll|rv\s?356|op\.?\s?3,? no\.?\s?6'):
            return INTER
        if has(r'four seasons|quattro stagioni|spring|primavera|winter|inverno'
               r'|summer|estate|autumn|autunno|concert'):
            return ADV
        return None
    if ck == 'corelli':
        return ADV if has(r'folia|follia') else INTER
    if ck == 'pachelbel':
        return INTER if has(r'canon|kanon') else None
    if ck == 'dowland':
        return INTER
    if ck == 'dvorak':
        if has(r'humoresque|humoreske|sonatin|op\.?\s?100|largo|new world|going home|songs my mother'):
            return INTER
        return ADV
    if ck in ('smetana', 'mussorgsky', 'rimsky', 'borodin', 'glinka',
              'lyadov', 'arensky', 'sibelius', 'glazunov', 'bruch'):
        if ck == 'rimsky' and has(r'bumble|hummel'):
            return ADV
        return ADV
    if ck == 'elgar':
        if op == 22 or has(r'very easy'):
            return BEGINNER
        if has(r'salut d.amour|love.?s greeting|chanson de (matin|nuit)|nimrod|pomp'):
            return INTER
        return ADV
    if ck == 'holst':
        return INTER if has(r'jupiter|thaxted') else ADV
    if ck in ('verdi', 'puccini', 'rossini', 'wagner', 'gounod', 'massenet',
              'bizet', 'offenbach', 'strauss'):
        if has(r'bridal|wedding|hochzeit|la donna|libiamo|brindisi|habanera|toreador'
               r'|can.?can|blue danube|donau|radetzky|pilgrim|barcarolle|ave maria'
               r'|o mio babbino|nessun|va pensiero|anvil|triumphal|march'):
            return INTER
        if has(r'meditation') and ck == 'massenet':
            return ADV
        if grp is LIEDER or grp is MELODIC or inst == 'Voice':
            return None
        return ADV
    if ck in ('weber', 'field', 'hummel', 'dussek', 'cramer', 'kalkbrenner',
              'herz', 'rubinstein', 'paderewski', 'sinding', 'godard',
              'chaminade', 'macdowell', 'gottschalk', 'nevin', 'durand',
              'poldini', 'bortkiewicz'):
        if ck == 'dussek' and (op == 20 or has(r'sonatin')):
            return INTER
        if ck == 'rubinstein' and has(r'melody in f|melodie'):
            return INTER
        if ck == 'macdowell' and has(r'wild rose|to a water'):
            return INTER
        if ck == 'godard' and has(r'berceuse|jocelyn'):
            return INTER
        if ck == 'nevin' and has(r'narcissus'):
            return INTER
        if ck == 'weber' and has(r'country|dance|waltz|walzer|sonatin'):
            return BEGINNER
        if ck == 'chaminade' and grp is LIEDER:
            return None
        return ADV
    # ── 현악·관악 교재 ──
    if ck in ('paganini', 'wieniawski', 'sarasate', 'vieuxtemps', 'bazzini',
              'sauret', 'ernst', 'beriot', 'kreutzer', 'rode', 'fiorillo',
              'gavinies'):
        if ck == 'beriot' and (op == 102 or has(r'methode|method')):
            return INTER
        return ADV
    if ck == 'dont':
        return INTER if op in (37, 38) else ADV
    if ck == 'dancla':
        if op in (123, 84, 126) or has(r'petite ecole|petits? (airs|morceaux)|faciles?'):
            return BEGINNER
        if op in (73, 74):
            return ADV
        return INTER
    if ck == 'alard':
        return ADV if has(r'fantais|brillant') else INTER
    if ck == 'mazas':
        return INTER
    if ck == 'wohlfahrt':
        return BEGINNER
    if ck in ('kayser', 'sitt', 'seitz', 'sevcik', 'hrimaly', 'schradieck'):
        if ck == 'sevcik' and op == 6:
            return BEGINNER
        return INTER
    if ck in ('rieding', 'kuchler'):
        return BEGINNER
    if ck in ('monti', 'tartini'):
        return ADV
    if ck == 'drdla':
        return INTER
    if ck == 'bohm_c':
        return INTER
    if ck in ('gossec', 'lully'):
        return BEGINNER if has(r'gavotte') else INTER
    if ck == 'boccherini':
        return INTER if has(r'minuet|menuet') else ADV
    if ck == 'popper':
        if op in (54, 55, 64, 76) and not has(r'etude|stud'):
            return INTER
        return ADV
    if ck == 'dotzauer':
        return INTER
    if ck == 'kummer':
        return BEGINNER if op == 60 else INTER
    if ck == 'klengel':
        return BEGINNER if op == 17 else INTER
    if ck == 'romberg':
        return INTER if has(r'sonat') else ADV
    if ck == 'goltermann':
        return INTER if op in (65, 76) else ADV
    if ck == 'lee':
        return BEGINNER if op == 101 else INTER
    if ck == 'squire':
        return INTER
    if ck == 'breval':
        return BEGINNER
    if ck == 'marcello':
        return INTER
    if ck == 'berbiguier':
        return INTER
    if ck == 'tulou':
        return INTER
    if ck == 'gariboldi':
        return BEGINNER if op == 132 else INTER
    if ck == 'popp':
        return INTER
    if ck in ('quantz', 'hotteterre', 'loeillet'):
        return INTER
    if ck == 'klose':
        return ADV if has(r'etude|stud') else INTER
    if ck == 'rose':
        return ADV
    if ck == 'lefevre':
        return INTER
    if ck == 'stamitz':
        return ADV
    if ck == 'arban':
        return ADV if has(r'fantais|variation|carnival|carnaval') else INTER
    if ck == 'clarke_h':
        return ADV if has(r'carnival|bride|debutante|maid') else INTER
    if ck == 'clarke_j':
        return BEGINNER
    # ── 기타 ──
    if ck == 'sor':
        if op == 60 or op == 44 or op == 35 and opno and opno <= 12 or op == 31 and opno and opno <= 6:
            return BEGINNER
        if op in (35, 31) or has(r'lesson|lecon|exercise|etude|estud|stud'):
            return INTER
        if op in (6, 29, 9, 14, 7, 30):
            return ADV
        return None
    if ck == 'carulli':
        if op in (241, 246, 27, 333) or has(r'methode|method|lesson|exercise|etude|stud'):
            return BEGINNER
        return None
    if ck == 'carcassi':
        if op == 60:
            return INTER
        if op == 59 or has(r'methode|method|lesson'):
            return BEGINNER
        return None
    if ck == 'giuliani':
        if op in (50, 139, 51) or has(r'papillon|lesson|lezion'):
            return BEGINNER
        if op in (100, 48, 1, 111) or has(r'exercise|etude|stud'):
            return INTER
        return None
    if ck == 'aguado':
        return INTER
    if ck == 'tarrega':
        if has(r'lagrima|l[aá]grima|adelita|pavana|marieta|estudio|preludio|prelude|tango|mazurka'):
            return INTER
        return ADV
    if ck in ('kuffner', 'horetzky', 'sanz'):
        return INTER
    if ck == 'foster':
        return BEGINNER if grp is MELODIC or grp is FOLK else INTER

    # ── 작곡가 규칙에 안 걸린 곡의 일반 제목 규칙 ──
    if has(r'\b(easy|facile|facili|leicht|leichte|elementary|elementaire'
           r'|beginner|anf[aä]nger|first (steps|lessons|book)|erste|premiere?s? lecons'
           r'|kinderleicht|for (the )?young|jugend|for children|children.?s|kinder'
           r'|petits? (morceaux|pieces)|progressive)\b'):
        if has(r'\b(very easy|tres facile|sehr leicht|elementary|beginner|anf[aä]nger'
               r'|first (steps|lessons)|erste|premiere?s? lecons|kinderleicht'
               r'|five.?finger|cinq doigts|f[uü]nf finger)\b'):
            return BEGINNER
        if ck in PEDAGOGY or has(r'etude|etuden|studies|stud(y|i)|exercise|lessons'):
            return INTER
    if has(r'\b(scales?|gammes?|tonleiter|arpegg|five.?finger|cinq doigts|f[uü]nf finger)\b'):
        return BEGINNER
    if has(r'\b(methode?|method|school|escuela|metodo|instruction|tutor)\b|schule\b'):
        return INTER

    return None


# ───────────────────────── ② 특징값 점수 ─────────────────────────

def _speed(f, fast_hi, fast_mid, fast_lo, nps_hi, nps_mid):
    rhythm = (3 if f['fast'] >= fast_hi else 2 if f['fast'] >= fast_mid
              else 1 if (f['fast'] >= fast_lo or f['med_ioi'] <= 0.5) else 0)
    speed = 2 if f['nps'] >= nps_hi else 1 if f['nps'] >= nps_mid else 0
    return max(rhythm, speed)


def score_keyboard(f):
    pts = _speed(f, 0.9, 0.5, 0.2, 6.0, 4.0)
    if f['poly'] >= 0.6 and f['maxchord'] >= 4:
        pts += 2 if f['both'] >= 0.3 else 1   # 양손 4성부 화음
    if f['big5'] >= 0.05:
        pts += 1          # 두꺼운 화음이 드문드문
    if f['big5'] >= 0.25:
        pts += 1          # 두꺼운 화음이 계속
    if f['rng'] >= 55:
        pts += 1
    if f['rng'] >= 70:
        pts += 1
    if f['acc'] >= 0.10:
        pts += 1
    if f['acc'] >= 0.20:
        pts += 1
    if f['dur'] >= 150:
        pts += 1
    if f['dur'] >= 300:
        pts += 1
    if f['leaps'] >= 0.2:
        pts += 1
    if f['both'] < 0.08:
        pts -= 1
    return BEGINNER if pts <= 1 else INTER if pts <= 4 else ADV


def score_guitar(f):
    pts = _speed(f, 0.8, 0.4, 0.15, 5.0, 3.5)
    if f['poly'] >= 0.3:
        pts += 1
    if f['maxchord'] >= 5:
        pts += 1
    if f['rng'] >= 34:
        pts += 1
    if f['rng'] >= 40:
        pts += 1
    if f['acc'] >= 0.08:
        pts += 1
    if f['acc'] >= 0.15:
        pts += 1
    if f['dur'] >= 150:
        pts += 1
    if f['dur'] >= 300:
        pts += 1
    if f['leaps'] >= 0.15:
        pts += 1
    if f['hi'] >= 81:
        pts += 1
    return BEGINNER if pts <= 1 else INTER if pts <= 4 else ADV


def solo_track(f):
    """반주가 딸린 미디에서 독주 트랙 — 화음이 가장 적은 트랙."""
    tr = f.get('tracks') or []
    if not tr:
        return None
    return sorted(tr, key=lambda t: (t['poly'], -t['n']))[0]


def score_melodic(f, inst):
    t = solo_track(f) or f
    pts = _speed(t, 0.8, 0.4, 0.15, 5.0, 3.5)
    if t['rng'] >= 24:
        pts += 1
    if t['rng'] >= 34:
        pts += 1
    if t['acc'] >= 0.08:
        pts += 1
    if t['acc'] >= 0.18:
        pts += 1
    if t['leaps'] >= 0.1:
        pts += 1
    if t['poly'] >= 0.1:
        pts += 1          # 중음·화음
    if f['dur'] >= 180:
        pts += 1
    if f['dur'] >= 360:
        pts += 1
    h1, h2 = HIGH_POS.get(inst, (999, 999))
    if t['hi'] >= h1:
        pts += 1
    if t['hi'] >= h2:
        pts += 1
    return BEGINNER if pts <= 1 else INTER if pts <= 4 else ADV


def score_lieder(f):
    v = solo_track(f) or f
    pts = 0
    if v['rng'] >= 15:
        pts += 1
    if v['rng'] >= 19:
        pts += 1
    if v['acc'] >= 0.08:
        pts += 1
    if v['acc'] >= 0.18:
        pts += 1
    if v['leaps'] >= 0.08:
        pts += 1
    if v['fast'] >= 0.3:
        pts += 1
    if f['fast'] >= 0.6:
        pts += 1          # 반주 16분음표
    if f['nps'] >= 5:
        pts += 1
    if f['big5'] >= 0.1:
        pts += 1
    if f['acc'] >= 0.1:
        pts += 1          # 반주 임시표
    if f['leaps'] >= 0.2:
        pts += 1
    if f['dur'] >= 120:
        pts += 1
    if f['dur'] >= 240:
        pts += 1
    return BEGINNER if pts <= 1 else INTER if pts <= 5 else ADV


def score_hymn(f):
    pts = 0
    if f['acc'] >= 0.02:
        pts += 1
    if f['acc'] >= 0.06:
        pts += 1
    if f['fast'] >= 0.05:
        pts += 1
    if f['nps'] >= 1.9:
        pts += 1
    if f['leaps'] >= 0.06:
        pts += 1
    if f['rng'] >= 34:
        pts += 1
    return BEGINNER if pts == 0 else INTER if pts <= 2 else ADV


def score_folk(f):
    pts = 0
    if f['rng'] >= 15:
        pts += 1
    if f['rng'] >= 19:
        pts += 1
    if f['acc'] >= 0.03:
        pts += 1
    if f['fast'] >= 0.1:
        pts += 1
    if f['nps'] >= 3.6:
        pts += 1
    if f['leaps'] >= 0.03:
        pts += 1
    if f['poly'] >= 0.1:
        pts += 1
    return BEGINNER if pts <= 1 else INTER if pts <= 3 else ADV


def feature_level(f, grp, inst):
    if grp is KEYBOARD:
        return score_keyboard(f)
    if grp is GUITAR:
        return score_guitar(f)
    if grp is MELODIC:
        return score_melodic(f, inst)
    if grp is LIEDER:
        return score_lieder(f)
    if grp is HYMN:
        return score_hymn(f)
    if grp is FOLK:
        return score_folk(f)
    if grp is ENSEMBLE:
        return ADV
    return None


# ───────────────────────── ③ 기본값 ─────────────────────────

def default_level(ck, grp, inst):
    if grp is ENSEMBLE:
        return ADV
    if ck in VIRTUOSO:
        return ADV
    if ck in PEDAGOGY:
        return INTER
    if ck == 'traditional':
        return BEGINNER if grp in (MELODIC, FOLK, CHOIR) or inst == 'Recorder' else None
    if ck == 'foster':
        return BEGINNER
    if grp is HYMN:
        return INTER
    if grp is LIEDER:
        return INTER
    if grp is CHOIR:
        return INTER if ck in ('bach', 'schubert', 'mendelssohn') else (
            ADV if ck in ('handel', 'mozart', 'haydn', 'monteverdi') else None)
    if inst == 'Voice':
        if ck in ('schubert', 'schumann', 'faure', 'mendelssohn', 'brahms', 'foster'):
            return INTER
        if ck in ('handel', 'bach', 'monteverdi', 'vivaldi', 'rameau', 'mozart',
                  'haydn', 'purcell'):
            return ADV
    if inst in ('Organ', 'Harpsichord'):
        return INTER if ck == 'traditional' else ADV
    if inst == 'Lute':
        return ADV if ck == 'bach' else INTER
    return None


def group_of(inst):
    for g in (KEYBOARD, GUITAR, MELODIC, LIEDER, FOLK, HYMN, ENSEMBLE, CHOIR):
        if inst in g:
            return g
    return None


def grade(e, feats):
    """(level|None, 판정 경로)"""
    inst = e.get('instrument') or ''
    if e.get('source') == 'original' and e.get('level') in (1, 2, 3):
        return e['level'], 'fixed'   # 직접 조판한 초급판 — 만들 때 정한 등급 유지
    grp = group_of(inst)
    tf = fold(e.get('title'))
    cf = fold(e.get('composer'))
    ck = ckey(cf)
    lv = rule_level(e, tf, cf, ck, grp)
    if lv:
        return lv, 'rule'
    c = feats.get(e.get('midi') or '')
    f = c.get('f') if c else None
    if f and grp is not None:
        lv = feature_level(f, grp, inst)
        if lv:
            if ck in VIRTUOSO and lv < INTER:
                lv = INTER   # 비르투오소 작곡가 곡은 초급으로 두지 않는다
            return lv, 'midi'
    lv = default_level(ck, grp, inst)
    return (lv, 'default') if lv else (None, 'none')


# ───────────────────────── 실행 ─────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mids', action='append', default=[],
                    help='미디 파일을 추가로 찾을 저장소 폴더 (예: free-sheets-2 클론)')
    ap.add_argument('--dry', action='store_true', help='catalog.json 을 쓰지 않는다')
    ap.add_argument('--sample', type=int, default=0, help='악기·등급별 표본을 n곡씩 출력')
    ap.add_argument('--tsv', help='전체 판정 결과를 TSV 로 저장')
    ap.add_argument('--only', help='표본을 이 판정 경로(rule/midi/default)로 한정')
    a = ap.parse_args()

    cat = json.load(open(CATALOG, encoding='utf-8'))
    feats, new, err = load_features(cat, a.mids)
    print(f'미디 특징값: 캐시 {len(feats)}곡 (새로 계산 {new}, 실패 {err})')

    stat = collections.defaultdict(collections.Counter)
    how = collections.Counter()
    changed = 0
    rows = []
    for e in cat:
        lv, path = grade(e, feats)
        old = (e.get('level'), e.get('entry'))
        if lv:
            e['level'] = lv
        else:
            e.pop('level', None)
        if is_entry(e):
            e['entry'] = True
        else:
            e.pop('entry', None)
        if old != (e.get('level'), e.get('entry')):
            changed += 1
        stat[e.get('instrument') or '?']['entry' if e.get('entry') else lv] += 1
        how[path] += 1
        rows.append((e, lv, path))

    if not a.dry:
        json.dump(cat, open(CATALOG, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        json.dump(feats, open(FEATURES, 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
    print(f'등급: {len(cat)}곡 중 변경 {changed}곡  판정 경로 {dict(how)}')
    tot = collections.Counter()
    for inst, c in sorted(stat.items(), key=lambda x: -sum(x[1].values())):
        tot.update(c)
        n = sum(c.values())
        print(f'  {inst:14} {n:5}  입문 {c["entry"]:4}  초급 {c[1]:5}  중급 {c[2]:5}  고급 {c[3]:5}  미분류 {c[None]:5}')
    n = sum(tot.values())
    print(f'  {"합계":14} {n:5}  입문 {tot["entry"]:4}  초급 {tot[1]:5}  중급 {tot[2]:5}  고급 {tot[3]:5}  미분류 {tot[None]:5}')

    if a.tsv:
        with open(a.tsv, 'w', encoding='utf-8') as fp:
            fp.write('level\tpath\tinstrument\tcomposer\ttitle\tsource\tmidi\n')
            for e, lv, path in rows:
                fp.write(f"{lv or 0}\t{path}\t{e.get('instrument')}\t{e.get('composer')}"
                         f"\t{e.get('title')}\t{e.get('source')}\t{e.get('midi', '')}\n")
    if a.sample:
        random.seed(7)
        for inst in ('Piano', 'Guitar', 'Violin', 'Flute', 'Cello', 'Voice+Piano',
                     'Hymn', 'Folk'):
            for lv in (1, 2, 3, None):
                pool = [r for r in rows if r[0].get('instrument') == inst and r[1] == lv
                        and (not a.only or r[2] == a.only)]
                if not pool:
                    continue
                print(f'\n== {inst} {NAMES[lv]} ({len(pool)})')
                for e, _, path in random.sample(pool, min(a.sample, len(pool))):
                    c = feats.get(e.get('midi') or '')
                    f = (c or {}).get('f') or {}
                    fs = (f"nps{f['nps']} fast{f['fast']} poly{f['poly']} ch{f['maxchord']} "
                          f"rng{f['rng']} acc{f['acc']} dur{f['dur']} lp{f['leaps']}") if f else ''
                    print(f"  [{path:7}] {e.get('title', '')[:46]:46} | "
                          f"{e.get('composer', '')[:22]:22} | {fs}")


if __name__ == '__main__':
    main()
