"""카탈로그 MIDI → 주제 선율 자동 후보: 박자·조표 읽기, 선율 트랙 고르기, 앞 N마디 자르기."""
import os, re, struct, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melody_sheet as M
FS = M.REPO
# 보조 검색 경로(선택) — 예전엔 세션 스크래치패드가 박혀 있었다.
FS2 = os.environ.get('FREE_SHEETS_ALT', '')
KEYS_MAJ = {-7:'ces',-6:'ges',-5:'des',-4:'aes',-3:'ees',-2:'bes',-1:'f',0:'c',1:'g',2:'d',3:'a',4:'e',5:'b',6:'fis',7:'cis'}
KEYS_MIN = {-7:'aes',-6:'ees',-5:'bes',-4:'f',-3:'c',-2:'g',-1:'d',0:'a',1:'e',2:'b',3:'fis',4:'cis',5:'gis',6:'dis',7:'ais'}

def midi_path(e):
    m = e.get('midi') or ''
    for d in (FS, FS2):
        p = os.path.join(d, m)
        if m and os.path.exists(p): return p
    return None

def meta(path):
    """(div, time '4/4', key 'g \\major', tempo bpm) — 첫 이벤트 기준."""
    b = open(path, 'rb').read(); ln, fmt, ntr, div = struct.unpack('>IHHH', b[4:14]); i = 8 + ln
    ts = None; ks = None; tempo = None
    for _ in range(ntr):
        if b[i:i+4] != b'MTrk': break
        tl = struct.unpack('>I', b[i+4:i+8])[0]; t = b[i+8:i+8+tl]; i += 8 + tl
        j = 0
        while j < len(t) - 3:
            if t[j] == 0xFF and t[j+1] == 0x58 and ts is None: ts = f'{t[j+3]}/{2**t[j+4]}'
            if t[j] == 0xFF and t[j+1] == 0x59 and ks is None:
                sf = t[j+3] - 256 if t[j+3] > 127 else t[j+3]; mi = t[j+4]
                ks = (KEYS_MIN[sf] + ' \\minor') if mi else (KEYS_MAJ[sf] + ' \\major')
            if t[j] == 0xFF and t[j+1] == 0x51 and tempo is None: tempo = round(60e6 / int.from_bytes(t[j+3:j+6], 'big'))
            j += 1
    return div, ts or '4/4', ks or 'c \\major', tempo or 100

def track_stats(path):
    div, tempos, notes = M.G.parse_midi(path)
    by = collections.defaultdict(list)
    for n in notes: by[n[4]].append(n)
    out = []
    for ti, ns in by.items():
        ns.sort(); ons = collections.Counter(n[0] for n in ns)
        poly = sum(1 for c in ons.values() if c >= 2) / len(ons)
        ps = [n[2] for n in ns]
        out.append(dict(track=ti, n=len(ns), mean=sum(ps)/len(ps), lo=min(ps), hi=max(ps), poly=round(poly, 2), first=ns[0][0] / div))
    return out

def pick_track(stats):
    """선율 트랙 = 음 수가 충분한 트랙 중 평균 음높이가 가장 높은 것.

    예전엔 화성 비율이 높은 트랙을 뒤로 밀었는데(poly > 0.5), 선율 추출이
    이미 화음의 맨 윗음만 가져가므로(notes_from_midi top=True) 그럴 이유가
    없다. 오히려 반주가 화음이면 선율 트랙이 밀려나 베이스가 뽑혔다 —
    짐노페디 2번이 평균 음고 40(왼손)으로, 체르니 Op.139-1 이 왼손으로
    잡히던 실제 사례가 있었다.
    """
    cands = [s for s in stats if s['n'] >= 12]
    if not cands: return None
    return max(cands, key=lambda s: s['mean'])

def make_cfg(e, bars=16, **over):
    p = midi_path(e)
    if not p: return None
    div, ts, key, tempo = meta(p)
    st = track_stats(p); tr = pick_track(st)
    if not tr: return None
    scale = 384 / div
    BAR = M.bar_ticks(ts)
    first_bar = int(tr['first'] * 384 // BAR)   # 선율 시작 마디 (전주 건너뛰기)
    start = first_bar * BAR
    cfg = dict(id=over.get('id') or re.sub(r'[^a-z0-9]+', '_', e['title'].lower())[:30], title_ko=over.get('title_ko', e.get('alias') or e['title']),
               subtitle=over.get('subtitle', e['title']), composer=over.get('composer', e['composer']), key=key, time=ts, tempo=min(tempo, 132),
               midi=p, track=tr['track'], start=start, end=start + bars * BAR, top=True, _stats=st)
    cfg.update({k: v for k, v in over.items() if k not in ('id',)})
    return cfg

if __name__ == '__main__':
    cat = json.load(open(os.path.join(FS, 'catalog.json'), encoding='utf-8'))
    for q in sys.argv[1:]:
        hits = [e for e in cat if re.search(q, e['title'], re.I) and midi_path(e)]
        for e in hits[:4]:
            c = make_cfg(e)
            if not c: continue
            print(e['title'][:40], '|', e['composer'][:16], '|', e['instrument'], '|', c['key'], c['time'], c['tempo'], '| track', c['track'], 'start bar', c['start'] // M.bar_ticks(c['time']), '|', [(s['track'], s['n'], round(s['mean']), s['poly']) for s in c['_stats']][:5])
