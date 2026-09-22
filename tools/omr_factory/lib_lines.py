# -*- coding: utf-8 -*-
"""4단계 데이터 공장 ② — **라이브러리 전체(12,879곡)** 를 학습쌍으로.

`make_lines.py` 는 우리 자체 조판 `.ly` 만 쓴다(all_out 에 24곡 × 9악기).
사장님 지시(2026-09-18) "이미 라이브러리에 만곡이 넘는 곡이 있어, 그걸 활용해줘"
에 따라 **저장소의 미디 7,336개**에서 단선율 멜로디를 뽑아 학습쌍을 만든다.

왜 미디에서 뽑나
  - 라이브러리의 기호 원본(thesession ABC·mutopia .ly·PDMX MusicXML)은 저장소에
    없다(수집 스크립트가 외부에서 받아 PDF·미디만 커밋). 저장소 안에서 자급
    가능한 기호 데이터는 `mids/` 뿐이다.
  - 이 미디들은 **사람 연주가 아니라 abc2midi·MuseScore·LilyPond 가 찍은 것**
    이라 격자에 정확히 붙어 있다(실측: 곡의 82.9% 가 16분 격자에 전음 정합).
    연구문서의 "midi2ly 금지"는 *사람이 연주한* 미디에 대한 경고다.
  - **정답이 어긋날 수 없다**: 우리가 토큰 목록을 먼저 정하고 그것으로 .ly 를
    써서 렌더하므로 이미지와 정답이 같은 원천에서 나온다. 게다가 LilyPond 가
    같이 낸 미디를 다시 읽어 우리 토큰과 대조한다(.ly 작성 버그 자동 검출).

받아들이는 조건 (하나라도 어긋나면 그 청크를 버린다)
  - 트랙이 단선율(겹침 없음), 음 16개 이상
  - 모든 온셋·길이가 **16분음표 격자**(Q=12 에서 3의 배수)
    → 셋잇단(4·8틱)은 **관문 3a(2026-09-23)부터 수용** — 박 안에 온전히 든
    순수 셋잇단 창만. 그 밖의 비격자는 여전히 제외.
  - 길이가 우리 표기 집합으로 분해 가능(3의 배수는 항상 가능)

출력: DIR/<곡키>/c<청크>_k<시프트>.png + .mid + manifest.jsonl
manifest 한 줄 = {song, src, chunk, shift, png, midi, tokens:[[pitch,dur],...]}
  pitch 0 = 쉼표. dur 단위 = 4분음표 12.
"""
import hashlib
import json
import os
import re
import subprocess

import mido

Q = 12                       # 4분음표 = 12틱
GRID = 3                     # 16분음표 = 3틱 (받아들이는 최소 격자)

# 반음 시프트 → \transpose c <목표> (make_lines.py 와 같은 표)
SHIFT_NAME = {0: 'c', 1: 'des', 2: 'd', 3: 'ees', 4: 'e', 5: 'f', 6: 'fis',
              -1: 'b,', -2: 'bes,', -3: 'a,', -4: 'aes,', -5: 'g,'}

# 틱 → LilyPond 음길이 기호. 큰 것부터 그리디 분해 + 붙임줄.
PLAIN = [(72, '1.'), (48, '1'), (42, '2..'), (36, '2.'), (24, '2'),
         (21, '4..'), (18, '4.'), (12, '4'), (9, '8.'), (6, '8'), (3, '16')]
PLAIN_BY_SYM = [(sym, v) for v, sym in PLAIN]

SHARP = ['c', 'cis', 'd', 'dis', 'e', 'f', 'fis', 'g', 'gis', 'a', 'ais', 'b']
FLAT = ['c', 'des', 'd', 'ees', 'e', 'f', 'ges', 'g', 'aes', 'a', 'bes', 'b']

# 미디 조표 이름 → (LilyPond \key, 올림표 쓰는 조인가)
KEYSIG = {
    'C': ('c \\major', True), 'G': ('g \\major', True), 'D': ('d \\major', True),
    'A': ('a \\major', True), 'E': ('e \\major', True), 'B': ('b \\major', True),
    'F#': ('fis \\major', True), 'C#': ('cis \\major', True),
    'F': ('f \\major', False), 'Bb': ('bes \\major', False),
    'Eb': ('ees \\major', False), 'Ab': ('aes \\major', False),
    'Db': ('des \\major', False), 'Gb': ('ges \\major', False),
    'Cb': ('ces \\major', False),
    'Am': ('a \\minor', True), 'Em': ('e \\minor', True), 'Bm': ('b \\minor', True),
    'F#m': ('fis \\minor', True), 'C#m': ('cis \\minor', True),
    'G#m': ('gis \\minor', True), 'D#m': ('dis \\minor', True),
    'A#m': ('ais \\minor', True),
    'Dm': ('d \\minor', False), 'Gm': ('g \\minor', False),
    'Cm': ('c \\minor', False), 'Fm': ('f \\minor', False),
    'Bbm': ('bes \\minor', False), 'Ebm': ('ees \\minor', False),
    'Abm': ('aes \\minor', False),
}

# 조표의 5도권 위치(올림표 개수, 음수는 내림표). 조옮김하면 여기에
# 아래 SHIFT_FIFTHS 가 더해진다 — 합이 ±7 을 넘으면 플랫 8개짜리
# 비현실 악보가 되므로 그 조합은 만들지 않는다.
KEY_FIFTHS = {'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
              'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7,
              'Am': 0, 'Em': 1, 'Bm': 2, 'F#m': 3, 'C#m': 4, 'G#m': 5, 'D#m': 6,
              'A#m': 7, 'Dm': -1, 'Gm': -2, 'Cm': -3, 'Fm': -4, 'Bbm': -5,
              'Ebm': -6, 'Abm': -7}
# \transpose c <목표> 가 조표를 몇 칸 옮기는가 (SHIFT_NAME 과 짝)
SHIFT_FIFTHS = {0: 0, 1: -5, 2: 2, 3: -3, 4: 4, 5: -1, 6: 6,
                -1: 5, -2: -2, -3: 3, -4: -4, -5: 1}


def key_ok(ks, shift):
    """조옮김 결과가 사람이 쓰는 조표 범위(±7)에 드는가."""
    return abs(KEY_FIFTHS.get(ks, 0) + SHIFT_FIFTHS[shift]) <= 7


SNIPPET = r'''\version "2.24.4"
#(set-global-staff-size %(staff)d)
\paper {
  #(set! paper-width (* 500 mm)) #(set! paper-height (* 70 mm))
  indent = 0\mm line-width = 480\mm
  top-margin = 4\mm bottom-margin = 4\mm left-margin = 6\mm right-margin = 6\mm
  ragged-right = ##t page-breaking = #ly:one-line-auto-height-breaking
  oddHeaderMarkup = ##f evenHeaderMarkup = ##f
  oddFooterMarkup = ##f evenFooterMarkup = ##f
}
\score {
  { \transpose c %(shift)s { %(clef)s \key %(key)s \time %(time)s %(tempo)s %(notes)s } }
  \layout { \context { \Score \omit BarNumber } }
  \midi { }
}
'''


# ─────────────────────────── 미디에서 멜로디 뽑기 ───────────────────────────

def read_tracks(mf):
    """트랙별 (pitch, start, end) 절대틱 목록 + 첫 박자표·조표."""
    ts = ks = None
    out = []
    for tr in mf.tracks:
        t, on, notes = 0, {}, []
        for m in tr:
            t += m.time
            if m.type == 'time_signature' and ts is None:
                ts = (m.numerator, m.denominator)
            elif m.type == 'key_signature' and ks is None:
                ks = m.key
            elif m.type == 'note_on' and m.velocity > 0:
                on.setdefault(m.note, []).append(t)
            elif m.type == 'note_off' or (m.type == 'note_on' and m.velocity == 0):
                if on.get(m.note):
                    s = on[m.note].pop(0)
                    if t > s:
                        notes.append((m.note, s, t))
        notes.sort(key=lambda n: (n[1], n[0]))
        out.append(notes)
    return out, ts, ks


def is_mono(notes, tpb):
    tol = max(1, tpb // 16)
    return all(b[1] >= a[2] - tol for a, b in zip(notes, notes[1:]))


def melody_of(path):
    """(음표목록[(pitch,start,dur) Q=12틱], 박자표, 조표) 또는 None."""
    try:
        mf = mido.MidiFile(path)
    except Exception:
        return None
    tpb = mf.ticks_per_beat
    if not tpb:
        return None
    trs, ts, ks = read_tracks(mf)
    cands = [n for n in trs if len(n) >= 16 and is_mono(n, tpb)]
    if not cands:
        return None
    best = max(cands, key=len)
    out = []
    for p, s, e in best:
        qs, qe = s / tpb * Q, e / tpb * Q
        rs, re_ = round(qs), round(qe)
        if abs(qs - rs) > 0.12 or abs(qe - re_) > 0.12:
            return None                         # 격자에서 너무 벗어남
        if re_ <= rs:
            return None
        out.append((p, rs, re_ - rs))
    # 앞의 못갖춘마디는 버린다 — 첫 마디 경계부터 시작하도록 원점을 옮긴다
    return out, (ts or (4, 4)), (ks or 'C')


# ─────────────────────────── 마디·토큰 만들기 ───────────────────────────

# 실제 악보에 나오는 박자표만 받는다. abc2midi·MuseScore 가 1/8·1/4·1/2 같은
# 퇴화 박자표를 쓰는 경우가 있고(실측 ~350곡) 그대로 조판하면 8분음표마다
# 마디줄이 그어진 비현실 악보가 나온다.
TIMESIGS = {(2, 2), (3, 2), (4, 2), (2, 4), (3, 4), (4, 4), (5, 4), (6, 4),
            (3, 8), (5, 8), (6, 8), (7, 8), (9, 8), (12, 8)}


def bar_ticks(ts):
    n, d = ts
    return int(round(n * Q * 4 / d))


def to_bars(notes, bt):
    """(pitch,start,dur) 목록 → 마디별 [(pitch|0, dur, tie_to_next)] 목록.

    원점은 첫 음이 든 마디의 시작. 쉼표는 pitch 0. 마디를 넘는 음은
    붙임줄로 쪼갠다. 격자(3틱) 밖이면 None.
    """
    if not notes:
        return None
    origin = (notes[0][1] // bt) * bt
    seq = [(p, s - origin, d) for p, s, d in notes]

    def ok(s_, d_):
        if s_ % GRID == 0 and d_ % GRID == 0:
            return True                     # 16분 격자 (기존)
        # 관문 3a: 셋잇단 8분(4틱)·셋잇단 4분(8틱) — 박(12틱) 안에 온전히
        # 들어가고 4틱 격자에 붙은 것만. 그 밖의 비격자는 여전히 제외.
        return (s_ % 4 == 0 and d_ in (4, 8)
                and s_ // Q == (s_ + d_ - 1) // Q)

    if any(not ok(s, d) for _, s, d in seq):
        return None
    end = max(s + d for _, s, d in seq)
    nbars = -(-end // bt)                       # 올림
    total = nbars * bt

    # 겹침 제거(단선율이지만 tol 때문에 1틱 겹칠 수 있다) + 쉼표 채우기
    flat, cur = [], 0
    for p, s, d in seq:
        if s < cur:
            d -= (cur - s)
            s = cur
            if d < GRID:
                continue
        if s > cur:
            flat.append((0, cur, s - cur))
        flat.append((p, s, d))
        cur = s + d
    if cur < total:
        flat.append((0, cur, total - cur))

    bars = [[] for _ in range(nbars)]
    for p, s, d in flat:
        while d > 0:
            bi = s // bt
            room = (bi + 1) * bt - s
            take = min(d, room)
            bars[bi].append((p, take, p != 0 and take < d))
            s += take
            d -= take
    return bars


def split_dur(t):
    """틱 → LilyPond 음길이 기호 목록(둘 이상이면 붙임줄로 이어야 함)."""
    out = []
    while t > 0:
        for v, sym in PLAIN:
            if v <= t:
                out.append(sym)
                t -= v
                break
        else:
            return None
    return out


def ly_pitch(midi, sharps):
    name = (SHARP if sharps else FLAT)[midi % 12]
    octv = midi // 12 - 1                       # 60 → 4
    mark = "'" * (octv - 3) if octv >= 3 else ',' * (3 - octv)
    return name + mark


def bars_to_ly(bars, sharps):
    """마디 목록 → (LilyPond 음표 문자열, 토큰목록[[pitch, dur, tie]]).

    토큰 하나 = 악보에 보이는 음표머리 하나(붙임줄로 쪼갠 것도 각각 한 개).
    tie=1 이면 다음 토큰과 붙임줄로 이어진다 → 미디에서는 한 음으로 병합된다.
    """
    TUP = {4: '8', 8: '4'}          # 셋잇단 창 안 표기 (관문 3a)
    parts, tokens = [], []
    for bar in bars:
        # 마디 안 위치를 계산해 12틱(4분음표) 창 단위로 셋잇단을 묶는다.
        items, pos = [], 0
        for p, d, tie in bar:
            items.append((pos, p, d, tie))
            pos += d
        cell, i = [], 0
        while i < len(items):
            s0, p, d, tie = items[i]
            if d % GRID == 0:
                syms = split_dur(d)
                if syms is None:
                    return None, None
                head = ly_pitch(p, sharps) if p else 'r'
                for k, sym in enumerate(syms):
                    last = k == len(syms) - 1
                    joined = bool(p) and (not last or tie)
                    cell.append(head + sym + ('~' if joined else ''))
                    tokens.append([p, dict(PLAIN_BY_SYM)[sym], 1 if joined else 0])
                i += 1
                continue
            # 셋잇단 창: 같은 12틱 창의 4·8틱 아이템을 모아 정확히 12틱이어야 한다
            w0 = (s0 // Q) * Q
            grp = []
            tot = 0
            while i < len(items) and tot < Q:
                s_, p_, d_, t_ = items[i]
                if d_ % GRID == 0 and tot == 0:
                    break
                if d_ not in (4, 8) or s_ // Q != w0 // Q:
                    return None, None
                grp.append((p_, d_, t_))
                tot += d_
                i += 1
            if tot != Q:
                return None, None
            inner = []
            for p_, d_, t_ in grp:
                head = ly_pitch(p_, sharps) if p_ else 'r'
                joined = bool(p_) and bool(t_)
                inner.append(head + TUP[d_] + ('~' if joined else ''))
                tokens.append([p_, d_, 1 if joined else 0])
            cell.append('\\tuplet 3/2 { ' + ' '.join(inner) + ' }')
        parts.append(' '.join(cell))
    return ' | '.join(parts) + ' |', tokens


def merged_pitches(tokens):
    """붙임줄을 병합한 음고 목록 — LilyPond 가 낸 미디와 대조할 기대값."""
    out, carry = [], False
    for p, _d, tie in tokens:
        if p and not carry:
            out.append(p)
        carry = bool(p) and bool(tie)
    return out


# ─────────────────────────── 렌더 ───────────────────────────

CLEFS = ('treble', 'treble', 'treble', 'bass')   # 대부분 높은음자리표


def make_ly(bars, ks, ts, staff, shift, clef, tempo):
    key, sharps = KEYSIG.get(ks, ('c \\major', True))
    notes, tokens = bars_to_ly(bars, sharps)
    if notes is None:
        return None, None
    src = SNIPPET % dict(staff=staff, shift=SHIFT_NAME[shift], clef=(r'\clef ' + clef),
                         key=key, time=f'{ts[0]}/{ts[1]}',
                         tempo=(f'\\tempo 4 = {tempo}' if tempo else ''), notes=notes)
    return src, tokens


def midi_notes(path):
    """렌더된 미디에서 음고 목록(등장 순) — 메타 이벤트는 해석하지 않는다.

    mido 로 읽으면 LilyPond 가 먼 조로 옮길 때 내는 조표(플랫 8개 이상)에
    `KeySignatureError` 가 난다. 우리는 음고만 필요하므로 메타는 길이만 보고
    건너뛰는 최소 파서를 쓴다(실측: 이 오류로 학습쌍이 버려지고 있었다).
    """
    with open(path, 'rb') as f:
        buf = f.read()
    ev, pos = [], 0
    if buf[:4] != b'MThd':
        raise ValueError('MThd 아님')
    hlen = int.from_bytes(buf[4:8], 'big')
    pos = 8 + hlen
    while pos + 8 <= len(buf):
        cid, clen = buf[pos:pos + 4], int.from_bytes(buf[pos + 4:pos + 8], 'big')
        pos += 8
        end = min(pos + clen, len(buf))
        if cid != b'MTrk':
            pos = end
            continue
        t, running = 0, None
        p = pos
        while p < end:
            # 가변길이 델타타임
            d = 0
            while p < end:
                b = buf[p]
                p += 1
                d = (d << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            t += d
            if p >= end:
                break
            b = buf[p]
            if b & 0x80:
                status = b
                p += 1
                if status < 0xF0:
                    running = status
            else:
                status = running
                if status is None:
                    break
            if status == 0xFF:                   # 메타 — 길이만 읽고 건너뛴다
                p += 1                           # type
                ln = 0
                while p < end:
                    b2 = buf[p]
                    p += 1
                    ln = (ln << 7) | (b2 & 0x7F)
                    if not b2 & 0x80:
                        break
                p += ln
            elif status in (0xF0, 0xF7):         # 시스템 배타 — 길이만 읽고 건너뛴다
                ln = 0
                while p < end:
                    b2 = buf[p]
                    p += 1
                    ln = (ln << 7) | (b2 & 0x7F)
                    if not b2 & 0x80:
                        break
                p += ln
            else:
                hi = status & 0xF0
                n = 1 if hi in (0xC0, 0xD0) else 2
                data = buf[p:p + n]
                p += n
                if hi == 0x90 and len(data) == 2 and data[1] > 0:
                    ev.append((t, data[0]))
        pos = end
    ev.sort()
    return [n for _, n in ev]


def found_midi(stem_path):
    for ext in ('.midi', '.mid'):
        if os.path.exists(stem_path + ext):
            return stem_path + ext
    return None


def render(lily, out_dir, stem, src):
    os.makedirs(out_dir, exist_ok=True)
    ly = os.path.join(out_dir, stem + '.ly')
    with open(ly, 'w', encoding='utf-8') as f:
        f.write(src)
    r = subprocess.run([lily, '-dresolution=300', '--png', '-dno-point-and-click',
                        '-o', os.path.join(out_dir, stem), ly],
                       capture_output=True, text=True, timeout=180)
    png = os.path.join(out_dir, stem + '.png')
    mid = found_midi(os.path.join(out_dir, stem))
    if os.path.exists(png) and mid:
        os.remove(ly)
        return png, mid, None
    return None, None, (r.stderr or '')[-300:]


def song_key(path):
    """**곡** 식별자 — 같은 곡의 악기 판본이 학습/시험 양쪽에 갈라지지 않게.

    같은 곡이 학습과 시험에 동시에 있으면 시험이 무효다. 악기별 파일
    (mids/original/<악기>/elise.mid 9개)과 thesession 의 같은 곡 다른 설정
    (…-118 / …-7335)을 하나의 곡으로 묶는다.
    """
    p = path.replace('\\', '/')
    base = os.path.splitext(os.path.basename(p))[0]
    m = re.search(r'(?:^|/)mids/(original|mutopia|pdmx2?)/[^/]+/[^/]+$', p)
    if m:
        return f'{m.group(1)}:{base}'            # 악기 폴더는 뗀다 → 곡 단위
    m = re.match(r'^(s|h|q)_(.+?)-(\d+)$', base)
    if m:
        return f'{m.group(1)}:{m.group(2)}'      # thesession/hymnal/quartet
    return 'lieder:' + base


def variant_key(path, mids_root='mids'):
    """**파일** 식별자 — 출력 폴더 이름. 곡 하나에 악기 9개가 있어도 안 겹친다."""
    p = os.path.relpath(path, mids_root).replace('\\', '/')
    p = os.path.splitext(p)[0]
    return re.sub(r'[^0-9A-Za-z._-]+', '_', p.replace('/', '__'))


def pick_shifts(key, n, pool):
    """곡마다 결정적으로 n개 조를 고른다(난수 없이 재현 가능). 0 은 항상 포함."""
    rest = [s for s in pool if s != 0]
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    out = [0] if 0 in pool else []
    for i in range(min(n - len(out), len(rest))):
        out.append(rest[(h >> (5 * i)) % len(rest)])
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    i = 0
    while len(uniq) < min(n, len(pool)) and i < len(rest):
        if rest[i] not in seen:
            uniq.append(rest[i])
            seen.add(rest[i])
        i += 1
    return uniq
