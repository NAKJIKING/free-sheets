"""PDMX(MuseScore 파생 퍼블릭 도메인 25만 곡) 수집기 — 3단계(본 수집).

관악·현악(플루트·클라리넷·트럼펫·색소폰·바이올린·첼로)의 독주 또는
피아노 반주 이중주 악보를 고른다.
 - 저작권: subset:no_license_conflict == True 만 사용 (222,856곡 서브셋)
 - 품질/중복: is_best_unique_arrangement == True (같은 곡의 대표 편곡만)
 - 인기순(평점·조회수)으로 악기당 CAP 곡 선별
 - pdf.tar.gz(9.6GB)를 스트리밍하며 선별된 PDF만 추출 (전체 저장 안 함)
"""
import csv
import io
import json
import os
import re
import sys
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw')
CATALOG = os.path.join(ROOT, 'catalog.json')
BASE = 'https://zenodo.org/api/records/15571083/files'
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (public-domain collector)'}

CAP = 150  # 악기당 1차 배치 상한 (저장소 용량 예고선 500MB 관리)

# 전수조사에서 제외 판정된 곡 (MuseScore ID) — 원곡 저작권 존속·검증 불능·
# 정서적 거부감 우려. 자동 수집이 다시 담지 않도록 영구 차단.
BLOCKED_IDS = {
    '5902556',  # Mary Did You Know (1991, Mark Lowry) - 저작권 존속
    '4159766',  # 2CELLOS 브랜드 편곡
    '5907396',  # The Laundromat theme - 현대 영상물 추정
    '873391',   # 러시아 국가 - 거부감 우려
    '5935685',  # Kevin Jiang 창작곡
    '5941614',  # Kevin Jiang 창작곡
    '5838089',  # 원곡 식별 불가
}

# 악기별 MIDI 프로그램 번호 (tracks 컬럼)
TARGETS = {
    'Flute': {73},
    'Violin': {40},
    'Cello': {42},
    'Clarinet': {71},
    'Trumpet': {56},
    'Saxophone': {64, 65, 66, 67},
}
KEYBOARD = {0, 1, 2, 3, 4, 5, 6, 7}  # 피아노 반주로 허용

# ── 저작권 안전 장치 ──────────────────────────────────────────
# MuseScore 이용자가 붙인 'publicdomain' 라벨은 오표기가 많다
# (현대 팝·애니 곡 편곡에도 붙어 있음). 원곡 자체가 확실히 퍼블릭
# 도메인인 작곡가(사후 70년+ 경과)의 곡, 또는 전통민요만 통과시킨다.
PD_COMPOSERS = [
    # 바로크·고전
    'Bach', 'Handel', 'Vivaldi', 'Telemann', 'Purcell', 'Scarlatti',
    'Corelli', 'Albinoni', 'Pachelbel', 'Rameau', 'Couperin', 'Buxtehude',
    'Monteverdi', 'Palestrina', 'Byrd', 'Tallis', 'Dowland', 'Frescobaldi',
    'Lully', 'Charpentier', 'Quantz', 'Stamitz', 'Danzi', 'Boccherini',
    'Haydn', 'Mozart', 'Beethoven', 'Clementi', 'Czerny', 'Diabelli',
    'Hummel', 'Gluck', 'Salieri', 'Kuhlau', 'Cimarosa',
    # 낭만
    'Schubert', 'Schumann', 'Chopin', 'Liszt', 'Mendelssohn', 'Brahms',
    'Wagner', 'Verdi', 'Rossini', 'Donizetti', 'Bellini', 'Puccini',
    'Tchaikovsky', 'Rimsky-Korsakov', 'Mussorgsky', 'Borodin', 'Glinka',
    'Rachmaninoff', 'Rachmaninov', 'Scriabin', 'Grieg', 'Dvorak',
    'Dvo\u0159\u00e1k', 'Smetana', 'Janacek', 'Mahler', 'Bruckner',
    'Strauss', 'Debussy', 'Ravel', 'Faure', 'Faur\u00e9', 'Saint-Saens',
    'Saint-Sa\u00ebns', 'Franck', 'Bizet', 'Gounod', 'Massenet',
    'Offenbach', 'Satie', 'Elgar', 'Holst', 'Albeniz', 'Alb\u00e9niz',
    'Granados', 'Paganini', 'Sarasate', 'Wieniawski', 'Weber', 'Spohr',
    'MacDowell', 'Burgm\u00fcller', 'Burgmuller', 'Sibelius',
    # 기타·류트
    'Tarrega', 'T\u00e1rrega', 'Sor', 'Giuliani', 'Carcassi', 'Carulli',
    'Aguado', 'Mertz', 'Milan', 'Sanz',
    # 관악 연습곡·명곡
    'Arban', 'Clarke', 'Klose', 'Klos\u00e9', 'Rose', 'Baermann',
    'Crusell', 'Boehm', 'B\u00f6hm', 'Andersen', 'Popp', 'K\u00f6hler',
    'Kohler', 'Drouet', 'Demersseman', 'Doppler', 'Briccialdi',
    # 미국 퍼블릭 도메인
    'Joplin', 'Sousa', 'Foster',
    # 종교·전통
    'Gregorian', 'Hymn',
]
_PD_RE = re.compile(
    r'\b(' + '|'.join(re.escape(n) for n in PD_COMPOSERS) + r')\b', re.I)
_TRAD_RE = re.compile(
    r'\b(traditional|trad\.|folk|anonymous|anon\.?)\b', re.I)


def is_pd_safe(composer, artist, title):
    """원곡이 확실히 퍼블릭 도메인인지 — 작곡가 화이트리스트 또는 전통곡."""
    for field in (composer, artist):
        if field and _PD_RE.search(field):
            return True
    blob = ' '.join(x for x in (composer, artist) if x)
    return bool(_TRAD_RE.search(blob))


def open_url(name):
    req = urllib.request.Request(f'{BASE}/{name}/content', headers=UA)
    return urllib.request.urlopen(req, timeout=600)


def parse_tracks(s):
    try:
        return [int(x) for x in s.split('-')] if s and s != 'NA' else []
    except ValueError:
        return None


def pick_candidates():
    """CSV 한 번 훑어 악기별 후보를 고른다."""
    cands = {k: [] for k in TARGETS}
    with open_url('PDMX.csv') as r:
        text = io.TextIOWrapper(r, encoding='utf-8', errors='replace')
        reader = csv.DictReader(text)
        for row in reader:
            if row.get('subset:no_license_conflict') != 'True':
                continue
            if row.get('is_best_unique_arrangement') != 'True':
                continue
            pdf = row.get('pdf', 'NA')
            if not pdf or pdf == 'NA':
                continue
            progs = parse_tracks(row.get('tracks', 'NA'))
            if not progs or len(progs) > 2:
                continue
            inst = None
            solo = None
            for name, targets in TARGETS.items():
                hits = [p for p in progs if p in targets]
                rest = [p for p in progs if p not in targets]
                if len(hits) >= 1 and all(p in KEYBOARD for p in rest):
                    inst = name
                    solo = not rest
                    break
            if inst is None:
                continue
            if not is_pd_safe(row.get('composer_name', ''),
                              row.get('artist_name', ''),
                              row.get('song_name', '')):
                continue
            try:
                rating = float(row.get('rating') or 0)
                n_ratings = int(row.get('n_ratings') or 0)
                views = int(row.get('n_views') or 0)
            except ValueError:
                rating, n_ratings, views = 0.0, 0, 0
            score = (rating if n_ratings > 0 else 0.0, views)
            meta = row.get('metadata', '')
            m = re.search(r'/(\d+)\.json$', meta)
            ms_id = m.group(1) if m else ''
            if ms_id in BLOCKED_IDS:
                continue
            def _clean(v):
                return '' if v in (None, '', 'NA') else v.strip()
            title = (_clean(row.get('song_name'))
                     or _clean(row.get('title')) or 'Untitled')
            composer = (_clean(row.get('composer_name'))
                        or _clean(row.get('artist_name')))
            cands[inst].append({
                'pdf': pdf.lstrip('./'),
                'score': score,
                'title': title,
                'composer': composer,
                'license': row.get('license') or 'publicdomain',
                'solo': solo,
                'ms_id': ms_id,
            })
    wanted = {}
    for inst, lst in cands.items():
        lst.sort(key=lambda c: c['score'], reverse=True)
        take = lst[:int(CAP * 1.3)]  # 아카이브에 PDF가 없을 때를 대비한 여유분
        print(f'  {inst}: 후보 {len(lst)}곡 → 선별 {len(take)}곡', flush=True)
        for c in take:
            c['inst'] = inst
            wanted[c['pdf']] = c
    return wanted


def main():
    print('== PDMX: CSV 선별', flush=True)
    wanted = pick_candidates()
    print(f'총 추출 대상 {len(wanted)}개, PDF 아카이브 스트리밍 시작', flush=True)

    catalog = json.load(open(CATALOG, encoding='utf-8'))
    # 이전 PDMX 수집분은 전부 버리고 새 기준으로 다시 담는다
    # (화이트리스트 도입 전에 섞여 든 현대곡 정리).
    catalog = [e for e in catalog if e.get('source') != 'pdmx']
    import shutil
    shutil.rmtree(os.path.join(RAW, 'pdmx'), ignore_errors=True)
    seen = {e['source_url'] for e in catalog}
    counts = {k: 0 for k in TARGETS}
    added = 0
    with open_url('pdf.tar.gz') as r:
        with tarfile.open(fileobj=r, mode='r|gz') as tf:
            remaining = len(wanted)
            for m in tf:
                if remaining <= 0:
                    break
                if not m.isfile():
                    continue
                key = m.name.lstrip('./')
                c = wanted.get(key)
                if c is None:
                    continue
                remaining -= 1
                inst = c['inst']
                if counts[inst] >= CAP:
                    continue
                src = (f"https://musescore.com/score/{c['ms_id']}"
                       if c['ms_id'] else f"pdmx:{key}")
                if src in seen:
                    continue
                data = tf.extractfile(m).read()
                if not data.startswith(b'%PDF'):
                    continue
                inst_dir = os.path.join(RAW, 'pdmx', inst.lower())
                os.makedirs(inst_dir, exist_ok=True)
                safe = re.sub(r'[^A-Za-z0-9._-]', '_', c['title'])[:60]
                fname = f"{safe}-{os.path.basename(key)[:12]}.pdf"
                with open(os.path.join(inst_dir, fname), 'wb') as f:
                    f.write(data)
                catalog.append({
                    'source': 'pdmx',
                    'source_url': src,
                    'file': os.path.relpath(
                        os.path.join(inst_dir, fname), ROOT),
                    'title': c['title'],
                    'composer': c['composer'],
                    'instrument': inst,
                    'license': c['license'],
                })
                seen.add(src)
                counts[inst] += 1
                added += 1
                if added % 100 == 0:
                    print(f'  ...{added}곡 추출', flush=True)

    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    print('== 악기별 신규:', counts, flush=True)
    print(f'PDMX 신규 {added}곡, 카탈로그 총 {len(catalog)}곡', flush=True)


if __name__ == '__main__':
    main()
