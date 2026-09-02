"""악기별 초급 단선율 — 한 선율을 악기 음역·조·음자리표·이조 기보에 맞춰 조판한다."""
import os, re, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melody_sheet as M

# 기보 음역(초급, MIDI 번호)·이조(기보 = 실음 + transp)·선호 기보 조(pc)
INSTR = {
 'piano':    dict(ko='피아노 (오른손)', en='Piano', clef='treble',   transp=0,  lo=60, hi=81, keys=[0,7,5,2,9], transposition=''),
 'recorder': dict(ko='리코더',          en='Recorder', clef='treble', transp=0,  lo=60, hi=79, keys=[0,5,7,2], transposition="\\transposition c''"),
 'violin':   dict(ko='바이올린',        en='Violin', clef='treble',   transp=0,  lo=55, hi=83, keys=[2,7,9,0], transposition=''),
 'flute':    dict(ko='플루트',          en='Flute', clef='treble',    transp=0,  lo=62, hi=84, keys=[5,7,0,2,10], transposition=''),
 'clarinet': dict(ko='클라리넷 (B♭)',   en='Clarinet in B♭', clef='treble', transp=2, lo=55, hi=79, keys=[0,5,7,2], transposition='\\transposition bes'),
 'trumpet':  dict(ko='트럼펫 (B♭)',     en='Trumpet in B♭', clef='treble', transp=2, lo=55, hi=76, keys=[0,5,7,10], transposition='\\transposition bes'),
 'altosax':  dict(ko='알토색소폰 (E♭)', en='Alto Saxophone', clef='treble', transp=9, lo=60, hi=79, keys=[0,7,5,2], transposition='\\transposition ees'),
 'cello':    dict(ko='첼로',            en='Cello', clef='bass',      transp=0,  lo=36, hi=62, keys=[0,7,2,5], transposition=''),
 'guitar':   dict(ko='기타',            en='Guitar', clef='"treble_8"', transp=12, lo=52, hi=79, keys=[0,7,2,9,4], transposition='\\transposition c'),
}
MAJ_NAME = {0:'c',1:'des',2:'d',3:'ees',4:'e',5:'f',6:'fis',7:'g',8:'aes',9:'a',10:'bes',11:'b'}
MIN_NAME = {0:'c',1:'cis',2:'d',3:'ees',4:'e',5:'f',6:'fis',7:'g',8:'gis',9:'a',10:'bes',11:'b'}
MAJ_ACC = {0:0,7:1,2:2,9:3,4:4,11:5,6:6,5:1,10:2,3:3,8:4,1:5}
DUR = {'1':1536,'2':768,'4':384,'8':192,'16':96,'32':48}

def parse_key(key):
    m = re.match(r"\s*([a-g])(is|es)?\s*\\(major|minor)", key)
    return (M.PC[m.group(1)] + {'is':1,'es':-1,None:0}[m.group(2)]) % 12, m.group(3) == 'minor'

def key_name(pc, minor):
    return (MIN_NAME[pc] + ' \\minor') if minor else (MAJ_NAME[pc] + ' \\major')

def n_acc(pc, minor):
    return MAJ_ACC[(pc + 3) % 12 if minor else pc]

def events_from_lily(mel):
    """제한된 LilyPond 문자열 → (on, off, pitch|None) 실음 이벤트."""
    ev = []; t = 0; tie = False
    for tok in mel.split():
        m = re.match(r"^([a-gr])(isis|eses|is|es|s)?([',]*)(\d+)(\.*)(~)?$", tok)
        if not m: continue
        d = DUR[m.group(4)]; d = int(d * (2 - 0.5 ** len(m.group(5)))) if m.group(5) else d
        if m.group(1) == 'r':
            ev.append((t, t + d, None)); t += d; tie = False; continue
        p = M.PC[m.group(1)] + {'is':1,'es':-1,'s':-1,'isis':2,'eses':-2,None:0}[m.group(2)] + 48   # c = 48, c' = 60
        p += 12 * (m.group(3).count("'") - m.group(3).count(','))
        if tie and ev and ev[-1][2] == p: ev[-1] = (ev[-1][0], t + d, p)
        else: ev.append((t, t + d, p))
        t += d; tie = bool(m.group(6))
    return [e for e in ev if e[2] is not None]

def choose_shift(events, tonic, minor, inst):
    """실음 이벤트를 악기 기보 음역·쉬운 조에 맞추는 반음 이동량."""
    ps = [e[2] for e in events if e[2] is not None]
    best = None
    for s in range(-30, 31):
        w = [p + s + inst['transp'] for p in ps]
        viol = sum(1 for p in w if p < inst['lo'] or p > inst['hi'])
        wt = (tonic + s + inst['transp']) % 12
        acc = n_acc(wt, minor)
        center = (sum(w) / len(w)) - (inst['lo'] + inst['hi']) / 2
        score = viol * 10 + max(0, acc - 2) * 3 + acc * 1.0 + abs(center) / 8 + (0 if wt in inst['keys'] else 1.5) + (0 if s % 12 == 0 else 0.5)
        if best is None or score < best[0]: best = (score, s, wt, acc, viol)
    return best

def build_variant(cfg, inst_id, outdir, tag=None):
    inst = INSTR[inst_id]
    tonic, minor = parse_key(cfg['key'])
    if 'lily' in cfg:
        ev = events_from_lily(cfg['lily'])
        ev_all = ev
    else:
        ev = M.notes_from_midi(cfg['midi'], cfg['track'], cfg['start'], cfg['end'], top=cfg.get('top', True), pmin=cfg.get('pmin'), legato_max=cfg.get('legato_max', 384))
        ev_all = ev
    score, s, wt, acc, viol = choose_shift(ev_all, tonic, minor, inst)
    wkey = key_name(wt, minor)
    if 'lily' in cfg:
        # 문자열 선율은 이벤트로 바꿔 같은 경로로 재생성 (이동·철자 일관)
        mel, sol = M.to_lily(ev_all, cfg['time'], transpose=s + inst['transp'], partial=cfg.get('partial_ticks', 0), collapse=False, pad=False, key=wkey)
    else:
        mel, sol = M.to_lily(ev_all, cfg['time'], transpose=s + inst['transp'], partial=cfg.get('partial_ticks', 0), collapse=cfg.get('collapse', True), pad=cfg.get('pad', True), key=wkey)
    ly = M.TEMPLATE % dict(
        staff=cfg.get('staff', 24), footer=cfg.get('footer', ''), title_ko=cfg['title_ko'],
        subtitle=cfg.get('subtitle', ''),
        composer=cfg.get('composer', ''), arranger="초급 단선율 · Easy melody — 내 악보함 · My Sheet Music",
        key=wkey, time=cfg['time'], tempo=cfg.get('tempo', 96),
        partial=('\\partial ' + cfg['partial']) if cfg.get('partial') else '', melody=mel, lyrics=' '.join(sol))
    ly = ly.replace('\\key ' + wkey, f"\\clef {inst['clef']} {inst['transposition']} \\key " + wkey)
    ly = ly.replace('  tagline = ##f', f'  subsubtitle = \\markup {{ \\fontsize #0.5 \\bold "{inst["ko"]} · {inst["en"]}" }}\n  tagline = ##f')
    if not cfg.get('solfege', False):
        ly = re.sub(r'\n\s*\\addlyrics \{[^}]*\}\n', '\n', ly)
    base = os.path.join(outdir, (tag or cfg['id']) + '__' + inst_id)
    os.makedirs(outdir, exist_ok=True)
    open(base + '.ly', 'w', encoding='utf-8').write(ly)
    r = subprocess.run([M.LP, '-dno-point-and-click', '-o', base, base + '.ly'], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stderr[-800:]); raise SystemExit('lilypond failed ' + base)
    import fitz
    from PIL import Image
    d = fitz.open(base + '.pdf'); pg = d[0]
    pg.get_pixmap(dpi=80).save(base + '.png')
    pix = pg.get_pixmap(dpi=60); im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); im.thumbnail((340, 480)); im.save(base + '.webp', quality=80)
    return dict(inst=inst_id, shift=s, written_key=wkey, acc=acc, viol=viol, bars=mel.count('|'))

if __name__ == '__main__':
    cfgs = {c['id']: c for c in json.load(open(sys.argv[1], encoding='utf-8'))}
    plan = json.load(open(sys.argv[2], encoding='utf-8'))   # [[piece_id, inst_id], ...]
    out = sys.argv[3]
    for pid, inst in plan:
        info = build_variant(cfgs[pid], inst, out)
        print(pid, info)
