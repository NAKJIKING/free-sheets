# -*- coding: utf-8 -*-
"""토큰 → 연주 음표 → SMF 파이썬 기준(다트 omr_core/lib/src/score.dart 와 같은 식).

전개는 lib_lines.unfold_tokens, 붙임줄 병합·쉼표 누적·SMF 배치는
evaluate.write_midi 를 그대로 따르고, 셈여림 세기(f 100 / mf 80 / p 60,
기본 80)만 덧붙였다. 셈여림이 없으면 write_midi(unfold(tokens)) 와 바이트가
같아야 한다(make_fixture.py 가 전수 검사).
"""
import struct
import sys

sys.path.insert(0, r'C:\Users\user\free-sheets\tools\omr_factory')
from lib_lines import unfold_tokens  # noqa: E402

DYN_VEL = {-6: 100, -8: 80, -7: 60}
DEFAULT_VEL = 80
TPQ, Q = 480, 12


def build_score(lines):
    toks = unfold_tokens([tuple(t) for l in lines for t in l])
    seq, vel = [], DEFAULT_VEL
    for t in toks:
        if t[0] < 0:
            vel = DYN_VEL.get(t[0], vel)
            continue
        seq.append((t, vel))
    out, tick, i = [], 0, 0
    while i < len(seq):
        (p, d, tie), v = seq[i]
        i += 1
        while tie and i < len(seq) and seq[i][0][0] == p:
            d += seq[i][0][1]
            tie = seq[i][0][2]
            i += 1
        if p > 0:
            out.append((tick, d, p, v))
        tick += d
    return out, tick


def _vlq(v):
    b = [v & 0x7f]
    v >>= 7
    while v:
        b.append((v & 0x7f) | 0x80)
        v >>= 7
    return bytes(reversed(b))


def write_midi_parts(parts, totals, bpm=90, program=0):
    """파트별 SMF — 파트 하나면 write_midi_bytes 와 같은 바이트(형식 0),
    둘 이상이면 형식 1·파트마다 트랙·채널 j(9 건너뜀)·빠르기는 첫 트랙."""
    if len(parts) == 1:
        return write_midi_bytes(parts[0], totals[0], bpm, program)
    out = b'MThd' + struct.pack('>IHHH', 6, 1, len(parts), TPQ)
    k = TPQ // Q
    for j, (notes, total) in enumerate(zip(parts, totals)):
        ch = j if j < 9 else j + 1
        ev = bytearray()
        if j == 0:
            ev += b'\x00\xff\x51\x03' + struct.pack('>I', int(60_000_000 / bpm))[1:]
        ev += bytes([0x00, 0xc0 | ch, program])
        at = 0
        for s, d, p, v in notes:
            ev += _vlq((s - at) * k) + bytes([0x90 | ch, p, v])
            ev += _vlq(d * k) + bytes([0x80 | ch, p, 0])
            at = s + d
        ev += _vlq(max(0, total - at) * k) + b'\xff\x2f\x00'
        out += b'MTrk' + struct.pack('>I', len(ev)) + bytes(ev)
    return out


def write_midi_bytes(notes, total, bpm=90, program=0):
    ev = bytearray()
    ev += b'\x00\xff\x51\x03' + struct.pack('>I', int(60_000_000 / bpm))[1:]
    ev += b'\x00\xc0' + bytes([program])
    k, at = TPQ // Q, 0
    for s, d, p, v in notes:
        ev += _vlq((s - at) * k) + bytes([0x90, p, v])
        ev += _vlq(d * k) + bytes([0x80, p, 0])
        at = s + d
    ev += _vlq(max(0, total - at) * k) + b'\xff\x2f\x00'
    return (b'MThd' + struct.pack('>IHHH', 6, 0, 1, TPQ) +
            b'MTrk' + struct.pack('>I', len(ev)) + bytes(ev))
