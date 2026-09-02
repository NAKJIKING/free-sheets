"""선율 목록 × 악기 → free-sheets 에 파일 배치 + 카탈로그 항목."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inst_sheet as I
FS = '/home/user/free-sheets'
CAT_INST = {'piano':'Piano','recorder':'Recorder','violin':'Violin','flute':'Flute','clarinet':'Clarinet','trumpet':'Trumpet','altosax':'Saxophone','cello':'Cello','guitar':'Guitar'}
TAGS = '초등 초급 단선율 쉬운 악보 easy melody beginner kids 儿童 简易 einfach fácil facile'

def run(cfg_path, meta_path, insts, out_tmp, write=False, only=None):
    cfgs = {c['id']: c for c in json.load(open(cfg_path, encoding='utf-8'))}
    meta = json.load(open(meta_path, encoding='utf-8'))   # list of dicts: id,title,alias,composer,level,license,source_url,tags
    cat = json.load(open(os.path.join(FS, 'catalog.json'), encoding='utf-8'))
    byfile = {e['file']: i for i, e in enumerate(cat)}
    made = []
    for m in meta:
        if only and m['id'] not in only: continue
        cfg = cfgs[m['id']]
        for inst in insts:
            info = I.build_variant(cfg, inst, out_tmp)
            base = os.path.join(out_tmp, f"{m['id']}__{inst}")
            pdf = f"raw/original/{inst}/{m['id']}.pdf"; mid = f"mids/original/{inst}/{m['id']}.mid"; th = f"thumbs/original/{inst}/{m['id']}.webp"
            e = {'source': 'original', 'source_url': m['source_url'], 'file': pdf, 'title': m['title'], 'composer': m['composer'],
                 'instrument': CAT_INST[inst], 'license': m['license'], 'thumb': th, 'midi': mid,
                 'alias': f"{m['alias']} ({I.INSTR[inst]['ko']})", 'tags': (m.get('tags', '') + ' ' + I.INSTR[inst]['ko'] + ' ' + TAGS).strip(), 'level': m['level']}
            if write:
                for sub in (f'raw/original/{inst}', f'mids/original/{inst}', f'thumbs/original/{inst}'):
                    os.makedirs(os.path.join(FS, sub), exist_ok=True)
                shutil.copy(base + '.pdf', os.path.join(FS, pdf)); shutil.copy(base + '.midi', os.path.join(FS, mid)); shutil.copy(base + '.webp', os.path.join(FS, th))
                if pdf in byfile: cat[byfile[pdf]] = e
                else: byfile[pdf] = len(cat); cat.append(e)
            made.append((m['id'], inst, info['written_key'], info['shift'], info['viol']))
    if write:
        json.dump(cat, open(os.path.join(FS, 'catalog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return made

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('cfg'); ap.add_argument('meta'); ap.add_argument('--out', default='set_out'); ap.add_argument('--write', action='store_true'); ap.add_argument('--only', nargs='*'); ap.add_argument('--insts', nargs='*', default=list(I.INSTR))
    a = ap.parse_args()
    made = run(a.cfg, a.meta, a.insts, a.out, a.write, a.only)
    for m in made: print(m)
    print(len(made), 'sheets', 'written' if a.write else 'dry')
