"""단선율 초급판 조판기 — MIDI 트랙(또는 LilyPond 선율 문자열)에서 선율을 뽑아
한글 제목·계이름이 붙은 한 줄 악보(LilyPond)를 만들고 PDF·MIDI·PNG·WebP 를 낸다."""
import os, re, shutil, subprocess, sys, json
# 저장소 루트 = 이 파일의 두 단계 위 (tools/original_src/ → 루트).
# 예전엔 '/home/user/free-sheets' 로 박혀 있어 다른 PC 에서 못 돌았다.
REPO = os.environ.get('FREE_SHEETS_ROOT') or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO); import grade_levels as G
# LilyPond: 환경변수 → PATH → 예전 고정 경로 순. 2.24 계열이면 된다.
LP = (os.environ.get('LILYPOND') or shutil.which('lilypond')
      or '/usr/bin/lilypond')
DIV = 384  # LilyPond MIDI ticks per quarter
SHARP_NAMES = ['c','cis','d','dis','e','f','fis','g','gis','a','ais','b']
FLAT_NAMES  = ['c','des','d','ees','e','f','ges','g','aes','a','bes','b']
SOL_SHARP = ['도','도♯','레','레♯','미','파','파♯','솔','솔♯','라','라♯','시']
SOL_FLAT  = ['도','레♭','레','미♭','미','파','솔♭','솔','라♭','라','시♭','시']
FLAT_KEYS = {'f','bes','ees','aes','des','ges','d \\minor','g \\minor','c \\minor','f \\minor'}
VALUES = [(1536,'1'),(1152,'2.'),(768,'2'),(576,'4.'),(384,'4'),(288,'8.'),(192,'8'),(144,'16.'),(96,'16'),(48,'32')]

PC = {'c':0,'d':2,'e':4,'f':5,'g':7,'a':9,'b':11}
def key_pref(key):
    """조성 문자열('g \\major', 'a \\minor') → 반음 pc 별 철자 선호('is'/'es')."""
    m = re.match(r"\s*([a-g])(is|es)?\s*\\(major|minor)", key)
    tonic = PC[m.group(1)] + {'is':1,'es':-1,None:0}[m.group(2)]; minor = m.group(3) == 'minor'
    rel = {1:'is',3:'es',6:'is',8:'es',10:'es'} if not minor else {1:'es',4:'is',6:'is',9:'is',11:'is'}
    return {(tonic + r) % 12: v for r, v in rel.items()}, (tonic % 12), minor

LETTERS = ['c','d','e','f','g','a','b']
SOL_LET = {'c':'도','d':'레','e':'미','f':'파','g':'솔','a':'라','b':'시'}
def scale_names(key):
    """조성의 온음계 7음 → {pc: (lily 이름, 계이름)} — 조표 철자 그대로."""
    m = re.match(r"\s*([a-g])(is|es)?\s*\\(major|minor)", key)
    letter = m.group(1); tonic = PC[letter] + {'is':1,'es':-1,None:0}[m.group(2)]
    steps = [0,2,4,5,7,9,11] if m.group(3) == 'major' else [0,2,3,5,7,8,10]
    out = {}
    li = LETTERS.index(letter)
    for k, st in enumerate(steps):
        L = LETTERS[(li + k) % 7]; pc = (tonic + st) % 12
        acc = (pc - PC[L]) % 12
        if acc == 1: nm, so = L + 'is', SOL_LET[L] + '♯'
        elif acc == 11: nm, so = L + 'es', SOL_LET[L] + '♭'
        else: nm, so = L, SOL_LET[L]
        out[pc] = (nm, so)
    return out

def spell(p, pref, scale=None):
    """온음계 음은 조표 철자, 반음은 pref('is'/'es')."""
    pc = p % 12
    if scale and pc in scale: return scale[pc]
    if pref.get(pc) == 'es': return FLAT_NAMES[pc], SOL_FLAT[pc]
    return SHARP_NAMES[pc], SOL_SHARP[pc]

def pitch_name(p, flats):
    if isinstance(flats, str) and flats == 'x': flats = True
    names = FLAT_NAMES if flats else SHARP_NAMES
    octv = p // 12 - 4  # c' = 60 → 0 marks → "'" * 1? LilyPond: c' = 60
    n = names[p % 12]
    o = p // 12 - 5     # 60//12=5 → 0 → c' needs one '
    marks = "'" * (o + 1) if o >= -1 else "," * (-(o + 1))
    return n + marks

def bar_ticks(time_sig):
    num, den = map(int, time_sig.split('/'))
    return num * (4 * DIV // den)

def split_value(L):
    """틱 길이를 표준 음가 목록으로 (긴 것부터)."""
    out = []
    for v, s in VALUES:
        while L >= v:
            out.append(s); L -= v
    return out, L

def _midi_path(midi):
    """설정의 미디 경로 — 상대경로면 저장소 루트 기준으로 푼다.
    (설정 파일에 절대경로를 박으면 다른 PC 에서 못 돌아간다)"""
    if os.path.isabs(midi) or os.path.exists(midi):
        return midi
    cand = os.path.join(REPO, midi)
    return cand if os.path.exists(cand) else midi


def notes_from_midi(midi, track, start_tick, end_tick, top=True, min_len=48, pmin=None, legato_max=384, pad_last=True, collapse_rests=True, tscale=1.0):
    div, tempos, notes = G.parse_midi(_midi_path(midi))
    scale = DIV / div * tscale
    ns = [(round(n[0]*scale), round(n[1]*scale), n[2]) for n in notes if n[4] == track and (pmin is None or n[2] >= pmin)]
    ns = [n for n in ns if start_tick <= n[0] < end_tick and n[1] - n[0] >= 60]  # 꾸밈음(짧은 음) 제외
    # 단선율화: 같은 시작(±1/32) 은 최고음만, 다음 시작에서 끊는다
    ns.sort()
    mono = []
    for on, off, p in ns:
        if mono and abs(on - mono[-1][0]) <= 48:
            if p > mono[-1][2] and top: mono[-1] = (mono[-1][0], max(off, mono[-1][1]), p)
            elif p < mono[-1][2] and not top: mono[-1] = (mono[-1][0], max(off, mono[-1][1]), p)
            continue
        mono.append((on, off, p))
    out = []
    for i, (on, off, p) in enumerate(mono):
        nxt = mono[i+1][0] if i+1 < len(mono) else end_tick
        off = min(off, nxt, end_tick)
        # 1/16 격자로 양자화
        q = lambda t: int(round(t / 96.0)) * 96
        on_q, off_q = q(on - start_tick), q(off - start_tick)
        if off_q <= on_q: off_q = on_q + 96
        if off_q - on_q < min_len: continue
        out.append((on_q, off_q, p))
    # 겹침 정리
    fixed = []
    for on, off, p in out:
        if fixed and on < fixed[-1][1]: fixed[-1] = (fixed[-1][0], on, fixed[-1][2])
        fixed.append((on, off, p))
    fixed = [f for f in fixed if f[1] > f[0]]
    # 레가토: 짧은 쉼(legato_max 이하)은 앞 음을 늘여 메운다
    out2 = []
    for i, (on, off, p) in enumerate(fixed):
        nxt = fixed[i+1][0] if i+1 < len(fixed) else None
        if nxt is not None and 0 < nxt - off <= legato_max: off = nxt
        out2.append((on, off, p))
    fixed = out2
    return fixed

def footer_lines(footer):
    """푸터 마크업. 긴 저작자표시(CC BY-SA)는 ' Licensed ' 앞에서 두 줄로
    나눈다 — 한 줄이면 A4 폭(595pt)을 넘어 양끝이 인쇄에서 잘린다."""
    if ' Licensed ' in footer and len(footer) > 105:
        a, b = footer.split(' Licensed ', 1)
        return ('\\center-column { \\line { "%s" } \\line { "Licensed %s" } }'
                % (a, b))
    return '\\line { "%s" }' % footer


def to_lily(events, time_sig, transpose=0, flats=False, partial=0, collapse=True, pad=True, key='c \\major'):
    pref = key_pref(key)[0]; scale = scale_names(key)
    """(on, off, pitch|None) 목록 → LilyPond 음표 문자열 + 계이름 목록.
    partial: 못갖춘마디 틱 수."""
    BAR = bar_ticks(time_sig)
    total_end = max(e[1] for e in events)
    # 쉼표 채우기
    seq = []; cur = 0
    for on, off, p in events:
        if on > cur: seq.append((cur, on, None))
        seq.append((on, off, p)); cur = off
    # 긴 쉼(한 마디 넘음)은 한 마디로 줄이고, 마지막 음은 마디 끝까지 채운다
    if collapse:
        seq2 = []; shift = 0
        for on, off, p in seq:
            on -= shift; off -= shift
            if p is None and off - on >= 2 * BAR:
                k = (off - on) // BAR - 1
                shift += k * BAR; off -= k * BAR
            seq2.append((on, off, p))
        seq = seq2
    if pad and seq and seq[-1][2] is not None:
        on, off, p = seq[-1]
        be = partial if off <= partial else partial + ((off - partial + BAR - 1) // BAR) * BAR
        seq[-1] = (on, be, p)
    out = []; sol = []
    def bar_of(t):  # 마디 시작 틱
        if t < partial: return 0
        return partial + ((t - partial) // BAR) * BAR
    def bar_end(t):
        return partial if t < partial else bar_of(t) + BAR
    for on, off, p in seq:
        pos = on
        first = True
        while pos < off:
            seg_end = min(off, bar_end(pos))
            vals, rem = split_value(seg_end - pos)
            if rem: vals.append('16')  # 잔여(양자화 오차) 보정
            for i, v in enumerate(vals):
                last = (i == len(vals) - 1) and (seg_end >= off)
                if p is None:
                    out.append('r' + v)
                else:
                    pp = p + transpose
                    nm_, so_ = spell(pp, pref, scale)
                    o = pp // 12 - 5
                    marks = "'" * (o + 1) if o >= -1 else "," * (-(o + 1))
                    out.append(nm_ + marks + v + ('' if last else '~'))
                    if first:
                        sol.append(so_); first = False
            pos = seg_end
            if pos < off or pos == off:
                if bar_end(pos) == pos or pos == bar_end(pos - 1):
                    out.append('|')
    text = ' '.join(out)
    text = re.sub(r'(\|\s*)+\|', '|', text)
    return text.strip(), sol

TEMPLATE = r'''\version "2.24.4"
#(set-global-staff-size %(staff)s)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  #(define fonts (set-global-fonts #:roman "%(font)s" #:sans "%(font)s" #:factor (/ staff-height pt 20)))
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 %(footer)s } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 %(footer)s } }
}
\header {
  title = \markup { \fontsize #%(tsize)s \bold "%(title_ko)s" }
  subtitle = \markup { \fontsize #%(ssize)s "%(subtitle)s" }
  composer = "%(composer)s"
  arranger = \markup { \fontsize #-1 "%(arranger)s" }
  tagline = ##f
}
melody = \absolute {
  \key %(key)s \time %(time)s \tempo 4 = %(tempo)s
  %(partial)s
  %(melody)s \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { %(lyrics)s }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
'''

def build(cfg, outdir):
    os.makedirs(outdir, exist_ok=True)
    if 'lily' in cfg:
        mel = cfg['lily']; sol = cfg.get('sol')
        if sol is None:
            # 문자열에서 계이름 계산
            flats = cfg.get('flats', False)
            sol = []
            for tok in mel.split():
                m = re.match(r"^([a-g])(isis|eses|is|es|s)?([',]*)(\d+\.*)?(~)?$", tok)
                if not m: continue
                base = {'c':0,'d':2,'e':4,'f':5,'g':7,'a':9,'b':11}[m.group(1)]
                acc = {'is':1,'es':-1,'s':-1,'isis':2,'eses':-2,None:0}[m.group(2)]
                sol.append(SOL_FLAT[(base+acc)%12] if acc < 0 else SOL_SHARP[(base+acc)%12])
            # 붙임줄 뒤 음은 가사 없음: LilyPond 가 자동 처리(멜리스마) → 붙임줄 앞 음만 셈
            toks = mel.split(); sol2 = []; k = 0
            for tok in toks:
                m = re.match(r"^([a-g])(isis|eses|is|es|s)?([',]*)(\d+\.*)?(~)?$", tok)
                if not m: continue
                sol2.append(sol[k]); k += 1
            # 붙임줄로 이어진 음 제거
            sol = []; prev_tied = False
            for tok in toks:
                m = re.match(r"^([a-g])(isis|eses|is|es|s)?([',]*)(\d+\.*)?(~)?$", tok)
                if not m: continue
                if not prev_tied: sol.append(sol2[len(sol) + sum(1 for _ in [])]) if False else None
                prev_tied = bool(m.group(5))
            # 간단히: 붙임줄 앞이 아닌 음(=이어받은 음) 건너뛰기
            sol = []; prev_tied = False; idx = 0
            for tok in toks:
                m = re.match(r"^([a-g])(isis|eses|is|es|s)?([',]*)(\d+\.*)?(~)?$", tok)
                if not m: continue
                if not prev_tied: sol.append(sol2[idx])
                idx += 1; prev_tied = bool(m.group(5))
    else:
        ev = notes_from_midi(cfg['midi'], cfg['track'], cfg['start'], cfg['end'], top=cfg.get('top', True), pmin=cfg.get('pmin'), legato_max=cfg.get('legato_max', 384), tscale=cfg.get('tscale', 1.0))
        if cfg.get('fallback_track') is not None:
            ev2 = notes_from_midi(cfg['midi'], cfg['fallback_track'], cfg['start'], cfg['end'], top=True, pmin=cfg.get('fallback_pmin'), legato_max=cfg.get('legato_max', 384))
            merged = []; cur = 0
            gaps = []
            for on, off, p in ev:
                if on - cur >= 768: gaps.append((cur, on))
                cur = max(cur, off)
            gaps.append((cur, cfg['end'] - cfg['start']))
            for on, off, p in ev:
                merged.append((on, off, p))
            for g0, g1 in gaps:
                for on, off, p in ev2:
                    if on >= g0 and on < g1:
                        merged.append((on, min(off, g1), p + cfg.get('fallback_transpose', 0)))
            merged.sort(); ev = [m for m in merged if m[1] > m[0]]
            # 겹침 제거
            fixed = []
            for on, off, p in ev:
                if fixed and on < fixed[-1][1]: fixed[-1] = (fixed[-1][0], on, fixed[-1][2])
                fixed.append((on, off, p))
            ev = [f for f in fixed if f[1] > f[0]]
        mel, sol = to_lily(ev, cfg['time'], cfg.get('transpose', 0), cfg.get('flats', False), cfg.get('partial_ticks', 0), collapse=cfg.get('collapse', True), pad=cfg.get('pad', True), key=cfg['key'])
    ly = TEMPLATE % dict(
        font=cfg.get('font', 'Nanum Gothic'),
        tsize=cfg.get('tsize', 3), ssize=cfg.get('ssize', 0),
        staff=cfg.get('staff', 24), footer=footer_lines(cfg.get('footer', '')), title_ko=cfg['title_ko'], subtitle=cfg.get('subtitle', ''),
        composer=cfg.get('composer', ''), arranger=cfg.get('arranger', '단선율 초급판 · 내 악보함'),
        key=cfg['key'], time=cfg['time'], tempo=cfg.get('tempo', 96),
        partial=('\\partial ' + cfg['partial']) if cfg.get('partial') else '', melody=mel, lyrics=' '.join(sol))
    base = os.path.join(outdir, cfg['id'])
    open(base + '.ly', 'w', encoding='utf-8').write(ly)
    r = subprocess.run([LP, '-dno-point-and-click', '-o', base, base + '.ly'], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stderr[-1500:]); raise SystemExit('lilypond failed: ' + cfg['id'])
    import fitz
    d = fitz.open(base + '.pdf'); pg = d[0]
    pg.get_pixmap(dpi=80).save(base + '.png')
    pix = pg.get_pixmap(dpi=60)
    from PIL import Image
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); im.thumbnail((340, 480)); im.save(base + '.webp', quality=80)
    return mel, sol

if __name__ == '__main__':
    cfgs = json.load(open(sys.argv[1], encoding='utf-8'))
    for c in cfgs:
        if len(sys.argv) > 2 and c['id'] not in sys.argv[2:]: continue
        mel, sol = build(c, os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), os.environ.get('OUTDIR', 'out')))
        print('##', c['id'], 'bars', mel.count('|'), '\n  ', mel[:300], '\n  ', ' '.join(sol)[:120])
