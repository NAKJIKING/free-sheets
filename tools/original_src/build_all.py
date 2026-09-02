"""전 언어·전 악기 빌드 — 곡 설정 + 번역을 합쳐 free-sheets 에 배치한다."""
import json, os, re, shutil, sys, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inst_sheet as I

HERE = os.path.dirname(os.path.abspath(__file__))
FS = '/home/user/free-sheets'
CAT_INST = {'piano':'Piano','recorder':'Recorder','violin':'Violin','flute':'Flute','clarinet':'Clarinet',
            'trumpet':'Trumpet','altosax':'Saxophone','cello':'Cello','guitar':'Guitar'}
TAGS = '초등 초급 단선율 쉬운 악보 easy melody beginner kids 儿童 简易 einfach fácil facile'


def load():
    cfgs = {}
    for f in ('cfg2.json', 'cfg_auto_final.json', 'cfg_hand.json'):
        for c in json.load(open(os.path.join(HERE, f), encoding='utf-8')):
            cfgs[c['id']] = c
    metas = {}
    for f in ('originals_meta_export.json', 'meta_auto.json', 'meta_hand.json'):
        p = os.path.join(HERE, f)
        if not os.path.exists(p): continue
        for m in json.load(open(p, encoding='utf-8')):
            metas[m['id']] = m
    i18n = json.load(open(os.path.join(HERE, 'i18n.json'), encoding='utf-8'))
    return cfgs, metas, i18n


def clean_title(t):
    return re.sub(r'\s*\((easy melody|melody)\)\s*$', '', t).strip()


def ko_sub(cfg, title_en):
    """한국어 작은 줄 — 원제가 앞에 붙어 있으면 떼어 낸다."""
    s = (cfg.get('subtitle') or '').strip()
    for sep in (' — ', ' - ', ' · '):
        if s.startswith(title_en + sep):
            return s[len(title_en) + len(sep):]
    return s


def prepare(cfgs, metas, i18n):
    out = []
    for pid, m in metas.items():
        c = dict(cfgs[pid])
        te = clean_title(m['title'])
        c['title_en'] = te
        c['sub_en'] = ko_sub(c, te) if not re.search(r'[가-힣]', ko_sub(c, te)) else (i18n.get(pid, {}).get('en', {}) or {}).get('sub', '')
        tr = i18n.get(pid, {})
        c['i18n'] = {'ko': dict(title=m['alias'], sub=ko_sub(c, te)),
                     'en': dict(title=te, sub=c['sub_en'])}
        for lg in ('de', 'fr', 'es', 'pt', 'ind', 'zh'):
            if lg in tr: c['i18n'][lg] = tr[lg]
        # 한국어 표기 안의 원어 이름을 뽑아 다른 언어판에 쓴다
        # (독일어판에 '루트비히 판 베토벤'이 찍히던 것)
        mm = re.search(r'\(([^()]*[A-Za-z][^()]*)\)', c.get('composer', ''))
        c['composer_latin'] = mm.group(1).strip() if mm else m['composer']
        c['_meta'] = m
        out.append(c)
    return out


def job(a):
    cfg, inst, lang, outdir = a
    try:
        I.build_variant(cfg, inst, outdir, lang=lang)
        return (cfg['id'], inst, lang, None)
    except BaseException as e:
        return (cfg['id'], inst, lang, repr(e)[:120])


def main(write=False, only=None, langs=None, insts=None, workers=4, catalog_only=False):
    cfgs, metas, i18n = load()
    pieces = prepare(cfgs, metas, i18n)
    if only: pieces = [p for p in pieces if p['id'] in only]
    langs = langs or I.LANGS
    insts = insts or list(I.INSTR)
    outdir = os.path.join(HERE, 'all_out')
    jobs = [(p, i, lg, outdir) for p in pieces for i in insts for lg in langs]
    print(f'{len(pieces)}곡 × {len(insts)}악기 × {len(langs)}언어 = {len(jobs)}장', flush=True)
    bad = []
    if catalog_only:
        jobs = []
    with mp.Pool(workers) as pool:
        for n, r in enumerate(pool.imap_unordered(job, jobs, chunksize=4), 1):
            if r[3]: bad.append(r)
            if n % 200 == 0: print(f'  {n}/{len(jobs)} 실패 {len(bad)}', flush=True)
    print('완료, 실패', len(bad), flush=True)
    for b in bad[:10]: print('  !', b, flush=True)
    if not write:
        return
    cat = json.load(open(os.path.join(FS, 'catalog.json'), encoding='utf-8'))
    cat = [e for e in cat if e.get('source') != 'original']
    for p in pieces:
        m = p['_meta']
        for inst in insts:
            sub = inst
            pdf = f'raw/original/{sub}/{p["id"]}.pdf'
            mid = f'mids/original/{sub}/{p["id"]}.mid'
            th = f'thumbs/original/{sub}/{p["id"]}.webp'
            langmap = {}
            for lg in langs:
                src = os.path.join(outdir, f'{p["id"]}__{inst}' + ('' if lg == 'ko' else f'__{lg}') + '.pdf')
                if not os.path.exists(src): continue
                rel = pdf if lg == 'ko' else f'raw/original/{sub}/{lg}/{p["id"]}.pdf'
                os.makedirs(os.path.join(FS, os.path.dirname(rel)), exist_ok=True)
                shutil.copy(src, os.path.join(FS, rel))
                if lg != 'ko': langmap[lg] = rel
            base = os.path.join(outdir, f'{p["id"]}__{inst}')
            for src, rel in ((base + '.midi', mid), (base + '.webp', th)):
                os.makedirs(os.path.join(FS, os.path.dirname(rel)), exist_ok=True)
                if os.path.exists(src): shutil.copy(src, os.path.join(FS, rel))
            e = {'source': 'original', 'source_url': m['source_url'], 'file': pdf,
                 'title': clean_title(m['title']), 'composer': m['composer'], 'instrument': CAT_INST[inst],
                 'license': m['license'], 'thumb': th, 'midi': mid,
                 'alias': f"{m['alias']} ({I.INST_NAMES[inst]['ko']})",
                 'tags': (m.get('tags', '') + ' ' + I.INST_NAMES[inst]['ko'] + ' ' + TAGS).strip(),
                 'level': m['level']}
            if langmap: e['langs'] = langmap
            cat.append(e)
    json.dump(cat, open(os.path.join(FS, 'catalog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('카탈로그 갱신 — original', sum(1 for e in cat if e['source'] == 'original'), flush=True)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true'); ap.add_argument('--only', nargs='*')
    ap.add_argument('--langs', nargs='*'); ap.add_argument('--insts', nargs='*'); ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--catalog-only', action='store_true')
    a = ap.parse_args()
    main(a.write, a.only, a.langs, a.insts, a.workers, a.catalog_only)
