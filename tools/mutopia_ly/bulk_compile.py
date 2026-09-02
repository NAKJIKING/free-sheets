"""Mutopia 소스(.ly) 일괄 컴파일 — 카탈로그에 없는 곡을 PDF+MIDI 로 만든다."""
import json, os, re, shutil, subprocess, sys, time
from multiprocessing import Pool
ROOT = '/home/user/mutopiaproject/mutopiaproject/ftp'
LP = '/tmp/claude-0/-home-user-project-all/37b62809-cd4d-5ffe-9718-71b635990054/scratchpad/lily/lilypond-2.24.4/bin'
OUT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(OUT, 'w')

def header(dirpath):
    """디렉터리의 .ly/.ily 전부에서 헤더 값을 모은다."""
    h = {}
    for dp, dn, fn in os.walk(dirpath):
        for f in fn:
            if not f.endswith(('.ly', '.ily', '.lyi')): continue
            try: s = open(os.path.join(dp, f), encoding='utf-8', errors='replace').read(20000)
            except Exception: continue
            for k in ('title', 'composer', 'opus', 'mutopiatitle', 'mutopiacomposer', 'mutopiaopus', 'mutopiainstrument', 'instrument', 'copyright', 'footer', 'style', 'source', 'date', 'maintainer', 'poet', 'piece'):
                if k in h: continue
                m = re.search(r'(?m)^\s*' + k + r'\s*=\s*"([^"\n]*)"', s)
                if m: h[k] = m.group(1).strip()
            if 'license' not in h:
                m = re.search(r'creativecommons\.org/licenses/([a-z-]+)/([0-9.]+)', s)
                if m:
                    kind, ver = m.group(1), m.group(2)
                    name = {'by': 'Creative Commons Attribution', 'by-sa': 'Creative Commons Attribution-ShareAlike'}.get(kind, 'Creative Commons ' + kind)
                    h['license'] = f'{name} {ver}'
                elif re.search(r'creativecommons\.org/licenses/publicdomain|creativecommons\.org/publicdomain', s) or re.search(r'(?i)copyright\s*=\s*"public domain', s):
                    h['license'] = 'Public Domain'
            if 'id' not in h:
                m = re.search(r'Mutopia-\d{4}/\d{2}/\d{2}-(\d+)', s)
                if m: h['id'] = m.group(1)
    if 'license' not in h and h.get('copyright', '').lower().startswith('public'):
        h['license'] = 'Public Domain'
    return h

def mains(dirpath):
    lys = sorted(f for f in os.listdir(dirpath) if f.endswith('.ly'))
    texts = {}
    for f in lys:
        try: texts[f] = open(os.path.join(dirpath, f), encoding='utf-8', errors='replace').read()
        except Exception: texts[f] = ''
    scored = [f for f in lys if re.search(r'\\score|\\book', texts[f])]
    if not scored: return lys[:1]
    included = set()
    for f in lys:
        for m in re.finditer(r'\\include\s*"([^"]+)"', texts[f]):
            included.add(os.path.basename(m.group(1)))
    tops = [f for f in scored if f not in included]
    if not tops: tops = scored
    base = os.path.basename(dirpath).replace('-lys', '')
    tops.sort(key=lambda f: (0 if f[:-3] == base else 1, len(f)))
    return tops

def compile_one(rel):
    src = os.path.join(ROOT, rel)
    work = os.path.join(WORK, rel.replace('/', '__'))
    res = {'rel': rel, 'ok': False, 'outputs': []}
    try:
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(src, work, ignore=shutil.ignore_patterns('*.pdf', '*.midi', '*.mid', '*.ps', '*.png', '.git*'))
        files = []
        for dp, dn, fn in os.walk(work):
            files += [os.path.join(dp, f) for f in fn if f.endswith(('.ly', '.ily', '.lyi'))]
        subprocess.run([f'{LP}/convert-ly', '-e', '-d'] + files, capture_output=True, text=True, timeout=300)
        res['header'] = header(work)
        ms = mains(work)
        res['mains'] = ms
        # 각 main 후보를 컴파일 — 별개 악보(parts)면 모두, 아니면 PDF 가 나온 첫 것.
        multi = len(ms) > 1 and all(not re.search(r'\\include', open(os.path.join(work, m), encoding='utf-8', errors='replace').read()) for m in ms)
        for i, m in enumerate(ms[: (len(ms) if multi else 3)]):
            tag = f'out{i}'
            t0 = time.time()
            try:
                r = subprocess.run([f'{LP}/lilypond', '-dno-point-and-click', '-dbackend=ps', '-o', os.path.join(work, tag), os.path.join(work, m)],
                                   capture_output=True, text=True, timeout=420, cwd=work)
                err = r.stderr[-600:]
            except subprocess.TimeoutExpired:
                err = 'TIMEOUT'
            pdfs = sorted(f for f in os.listdir(work) if f.startswith(tag) and f.endswith('.pdf'))
            mids = sorted(f for f in os.listdir(work) if f.startswith(tag) and f.endswith('.midi'))
            if pdfs:
                hh = header(os.path.join(work, m)) if multi else {}
                res['outputs'].append({'main': m, 'pdf': os.path.join(work, pdfs[0]), 'midi': os.path.join(work, mids[0]) if mids else '', 'sec': round(time.time() - t0, 1), 'title': hh.get('title') or hh.get('piece') or ''})
                res['ok'] = True
                if not multi: break
            else:
                res['err'] = err
    except Exception as e:
        res['err'] = repr(e)
    return res

if __name__ == '__main__':
    missing = json.load(open(sys.argv[1]))
    rels = [m[0] for m in missing]
    os.makedirs(WORK, exist_ok=True)
    done = []
    t0 = time.time()
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 3) as pool:
        for i, r in enumerate(pool.imap_unordered(compile_one, rels)):
            done.append(r)
            if i % 25 == 0:
                print(f'{i+1}/{len(rels)} ok={sum(1 for d in done if d["ok"])} {round(time.time()-t0)}s', flush=True)
                json.dump(done, open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False)
    json.dump(done, open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False)
    print('DONE', len(done), 'ok', sum(1 for d in done if d['ok']), round(time.time() - t0), 's', flush=True)
