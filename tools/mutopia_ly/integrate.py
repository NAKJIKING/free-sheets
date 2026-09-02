"""bulk_compile 결과 → free-sheets 파일 배치 + 카탈로그 항목 (dry-run 지원)."""
import json, os, re, shutil, sys, unicodedata
sys.path.insert(0, '/home/user/free-sheets')
import sanitize_catalog as S
FS = '/home/user/free-sheets'
OUT = os.path.dirname(os.path.abspath(__file__))

INST_MAP = [
    (r'string quartet', 'StringQuartet'), (r'voice and piano|voice, piano|voice & piano|voice with piano|song', 'Voice+Piano'),
    (r'satb|ttbb|ssaa|ssa\b|choir|chorus|voices', 'Choir'), (r'\bvoice\b|vocal|soprano|tenor|alto|bass voice', 'Voice'),
    (r'piano duet|4 hands|four hands', 'Piano'), (r'harpsichord|clavier|clavichord|virginal', 'Harpsichord'), (r'organ', 'Organ'),
    (r'piano|pianoforte|fortepiano|keyboard', 'Piano'), (r'guitar|guitarre|vihuela', 'Guitar'), (r'\blute\b', 'Lute'), (r'mandolin', 'Mandolin'),
    (r'violin|violine|violon\b', 'Violin'), (r'viola\b', 'Viola'), (r'cello|violoncello', 'Cello'), (r'double bass|contrabass', 'Cello'),
    (r'flute|fl[oö]te|flauto', 'Flute'), (r'recorder|blockfl', 'Recorder'), (r'clarinet', 'Clarinet'), (r'oboe', 'Oboe'), (r'bassoon', 'Bassoon'),
    (r'trumpet|cornet', 'Trumpet'), (r'\bhorn\b', 'Horn'), (r'trombone', 'Trombone'), (r'saxophone', 'Saxophone'), (r'harp\b', 'Harp'),
    (r'accordion', 'Accordion'), (r'orchestra|ensemble|band|chamber|quintet|trio|quartet|sextet', 'Orchestra'), (r'percussion|drum', 'Percussion'),
]
SKIP = re.compile(r'koto|shamisen|banjo|ukulele|bagpipe|shakuhachi', re.I)

def inst_of(text):
    t = (text or '').lower()
    if not t or SKIP.search(t): return None
    for pat, name in INST_MAP:
        if re.search(pat, t): return name
    return None

def slug(s):
    s = unicodedata.normalize('NFKD', s); s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s).strip('_')
    return s[:90]

def title_of(r, o):
    h = r.get('header', {})
    t = (o.get('title') or h.get('title') or h.get('mutopiatitle') or '').strip()
    t = re.sub(r'\\[a-zA-Z]+|[{}#]|\s+', ' ', t).strip() if '\\' in t else t
    op = (h.get('opus') or h.get('mutopiaopus') or '').strip()
    if op and op.lower() not in t.lower():
        t = f'{t} {op}' if t else op
    m = re.search(r'[Nn]o[._ ]*0*(\d+)', os.path.basename(r['rel']))
    if m and not re.search(r'\bno\.?\s*\d', t, re.I):
        t = f'{t} No.{int(m.group(1))}'
    if len(r['outputs']) > 1 and o.get('main'):
        base = os.path.splitext(o['main'])[0]
        if base.lower() not in t.lower(): t = f'{t} — {base}'
    return t.strip(' -—')

def main(dry=True):
    res = json.load(open(os.path.join(OUT, 'results.json'), encoding='utf-8'))
    cat = json.load(open(os.path.join(FS, 'catalog.json'), encoding='utf-8'))
    existing = {(S.norm(e.get('title')), S.norm(e.get('composer')), e.get('instrument')) for e in cat}
    import fitz
    from PIL import Image
    new = []; stat = {'ok': 0, 'noinst': 0, 'dup': 0, 'skip': 0, 'fail': 0}
    for r in res:
        if not r['ok']:
            stat['fail'] += 1; continue
        h = r.get('header', {})
        inst = inst_of(h.get('mutopiainstrument') or h.get('instrument'))
        if not inst:
            stat['noinst'] += 1; continue
        comp = (h.get('composer') or h.get('mutopiacomposer') or '').strip()
        comp = re.sub(r'\s*\(.*?\)\s*', ' ', comp).strip()
        lic = h.get('license') or ('Public Domain' if 'public' in (h.get('copyright') or '').lower() else '')
        if not lic:
            stat['skip'] += 1; continue
        url = (f"https://www.mutopiaproject.org/cgibin/piece-info.cgi?id={h['id']}" if h.get('id')
               else f"https://www.mutopiaproject.org/ftp/{r['rel']}/")
        for o in r['outputs']:
            title = title_of(r, o)
            if not title: continue
            key = (S.norm(title), S.norm(comp), inst)
            if key in existing:
                stat['dup'] += 1; continue
            existing.add(key)
            name = slug(r['rel'].replace('/', '__') + ('' if len(r['outputs']) == 1 else '__' + os.path.splitext(o['main'])[0]))
            sub = inst.lower().replace('+', '_')
            pdf = f'raw/mutopia/{sub}/{name}.pdf'; mid = f'mids/mutopia/{sub}/{name}.mid'; th = f'thumbs/mutopia/{sub}/{name}.webp'
            e = {'source': 'mutopia', 'source_url': url, 'file': pdf, 'title': title, 'composer': comp, 'instrument': inst,
                 'license': lic + ' (Mutopia)' if 'Mutopia' not in lic else lic, 'thumb': th}
            if o.get('midi'): e['midi'] = mid
            if not dry:
                os.makedirs(os.path.join(FS, os.path.dirname(pdf)), exist_ok=True)
                os.makedirs(os.path.join(FS, os.path.dirname(mid)), exist_ok=True)
                os.makedirs(os.path.join(FS, os.path.dirname(th)), exist_ok=True)
                shutil.copy(o['pdf'], os.path.join(FS, pdf))
                if o.get('midi'): shutil.copy(o['midi'], os.path.join(FS, mid))
                d = fitz.open(o['pdf']); pix = d[0].get_pixmap(dpi=60)
                im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); im.thumbnail((340, 480)); im.save(os.path.join(FS, th), quality=80)
            new.append(e); stat['ok'] += 1
    print(stat)
    import collections
    print(collections.Counter(e['instrument'] for e in new).most_common())
    if not dry:
        cat.extend(new)
        json.dump(cat, open(os.path.join(FS, 'catalog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(new, open(os.path.join(OUT, 'new_entries.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return new

if __name__ == '__main__':
    main(dry='--write' not in sys.argv)
