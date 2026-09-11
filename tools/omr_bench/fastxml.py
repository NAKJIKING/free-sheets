"""MusicXML 에서 음높이 순서를 직접 뽑는다 — music21 없이.

music21 의 converter.parse 는 파일당 몇 초가 걸려 표본 수백 곡에 못 쓴다.
우리가 필요한 것은 음높이 순서·성부 수·마디 길이뿐이라 XML 을 바로 읽는다.
"""
import zipfile, os
import xml.etree.ElementTree as ET
from fractions import Fraction

STEP = {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}

def _root(path):
    if path.endswith('.mxl'):
        z = zipfile.ZipFile(path)
        n = [x for x in z.namelist() if x.endswith('.xml') and 'META-INF' not in x][0]
        return ET.fromstring(z.read(n))
    return ET.parse(path).getroot()

def notes_and_bars(path):
    """(음높이 순서, 성부 수, 검사한 마디 수, 박자 안 맞는 마디 수)"""
    r = _root(path)
    parts = r.findall('part')
    seq = []
    tot = bad = 0
    for part in parts:
        ms = part.findall('measure')
        div = 1; beats = None; btype = None
        pend_tie = None          # 붙임줄로 이어지는 중인 음높이
        for k, m in enumerate(ms):
            a = m.find('attributes')
            if a is not None:
                d = a.findtext('divisions')
                if d: div = int(d)
                t = a.find('time')
                if t is not None:
                    bb, bt = t.findtext('beats'), t.findtext('beat-type')
                    if bb and bt: beats, btype = int(bb), int(bt)
            dur = 0
            for n in m.findall('note'):
                if n.find('grace') is not None:       # 꾸밈음 제외
                    continue
                d_ = n.findtext('duration')
                d_ = int(d_) if d_ else 0
                is_chord = n.find('chord') is not None
                if not is_chord:
                    dur += d_
                p = n.find('pitch')
                if p is None:                          # 쉼표
                    pend_tie = None
                    continue
                midi = (int(p.findtext('octave')) + 1) * 12 \
                       + STEP.get(p.findtext('step'), 0) \
                       + int(p.findtext('alter') or 0)
                ties = [t.get('type') for t in n.findall('tie')]
                if 'stop' in ties and pend_tie == midi:
                    if 'start' not in ties: pend_tie = None
                    continue                           # 붙임줄로 이어진 음 — 한 번만 센다
                seq.append(midi)
                pend_tie = midi if 'start' in ties else None
            if beats and 0 < k < len(ms) - 1:
                tot += 1
                # 한 마디의 기대 길이(divisions 단위):
                #   beats × (4/beat-type) × divisions   — divisions 는 4분음표당 단위 수
                exp = Fraction(beats * 4 * div, btype)
                if abs(Fraction(dur) - exp) > Fraction(div, 16):
                    bad += 1
    return seq, len(parts), tot, bad
