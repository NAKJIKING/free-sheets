#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audiveris 기준선 채점 — 캐논 2중주 실물 사진 (우리 모델과 같은 지표).

    python tools/omr_bench/score_canon_av.py \
        --pred C:/Users/user/omr_av_out \
        --truth C:/Users/user/omr_dense/truth_canon.json \
        -o C:/Users/user/omr_av_out/av_canon.json

지표를 우리 evaluate_duet 와 맞춘다: 음표 = (미디 음높이, 길이[4분음표=12]),
쉼표 제외, 붙임줄 병합, NER = 편집거리 / 정답 음수(사진당 438·쉼표 제외 436).
인식된 파트들을 두 성부에 **최적 배정**(전 조합 최소 오류)하고, 남는 파트는
삽입 오류, 모자란 성부는 통째 삭제 오류 — 우리 채점과 같은 정직 규칙.
악장 분할(.mvt1·.mvt2)은 이어 붙인다(README 함정 표 그대로).
"""
import argparse
import glob
import itertools
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                + '/omr_factory')
from train import edit  # noqa: E402

Q = 12


def _root(path):
    if path.endswith('.mxl'):
        z = zipfile.ZipFile(path)
        n = [x for x in z.namelist()
             if x.endswith('.xml') and 'META-INF' not in x][0]
        return ET.fromstring(z.read(n))
    return ET.parse(path).getroot()


def parts_of(path):
    """MusicXML → 파트별 [(pitch, dur12), ...] — 쉼표 제외, 붙임줄 병합,
    꾸밈음 제외, 화음은 머리음만."""
    r = _root(path)
    out = []
    for part in r.findall('part'):
        div = 1
        seq = []
        tie_open = False
        for m in part.findall('measure'):
            a = m.find('attributes')
            if a is not None:
                d = a.findtext('divisions')
                if d:
                    div = int(d)
            for n in m.findall('note'):
                if n.find('grace') is not None or n.find('chord') is not None:
                    continue
                d_ = int(n.findtext('duration') or 0)
                u = int(round(d_ * Q / max(1, div)))
                if n.find('rest') is not None:
                    tie_open = False
                    continue
                p = n.find('pitch')
                if p is None:
                    continue
                step = p.findtext('step')
                alt = int(float(p.findtext('alter') or 0))
                octv = int(p.findtext('octave'))
                midi = {'C': 0, 'D': 2, 'E': 4, 'F': 5,
                        'G': 7, 'A': 9, 'B': 11}[step] + alt + 12 * (octv + 1)
                ties = [t.get('type') for t in n.findall('tie')]
                if tie_open and seq and seq[-1][0] == midi:
                    seq[-1] = (midi, seq[-1][1] + u)      # 병합
                else:
                    seq.append((midi, u))
                tie_open = 'start' in ties and 'stop' not in ties \
                    or ('start' in ties and 'stop' in ties and tie_open)
        out.append(seq)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pred', required=True)
    ap.add_argument('--truth', required=True)
    ap.add_argument('--photos', default='C:/Users/user/omr_av_in',
                    help='입력 사진 폴더 — 출력 없는 사진을 완전 실패로 셈')
    ap.add_argument('-o', required=True)
    a = ap.parse_args()

    tr = json.load(open(a.truth, encoding='utf-8'))
    voices = [[(p, d) for p, d, _t in v if p > 0]
              for v in [[tuple(t) for t in vv] for vv in tr['voices']]]
    pt_photo = sum(len(v) for v in voices)

    # 사진 이름(stem) → mxl 목록 (책 폴더 하위까지, 악장 분할 포함)
    mxls = glob.glob(os.path.join(a.pred, '**', '*.mxl'), recursive=True)
    by = {}
    for p in mxls:
        stem = os.path.basename(p).split('.')[0]
        by.setdefault(stem, []).append(p)

    # 기대 사진 목록 — 인식 출력이 아예 없는 사진은 전량 삭제 오류(정직 채점)
    expect = sorted(os.path.splitext(os.path.basename(p))[0]
                    for p in glob.glob(os.path.join(a.photos, '*.jpg')))
    photos = expect if expect else sorted(by)
    ne = nt = 0
    fails = 0
    per = []
    for stem in photos:
        if stem not in by:
            fails += 1
            ne += pt_photo
            nt += pt_photo
            per.append(dict(photo=stem, parts=0, err=pt_photo,
                            notes=pt_photo, ner=1.0))
            continue
        parts = []
        for p in sorted(by[stem]):          # .mvt1, .mvt2 순서로 이어붙임
            for i, seq in enumerate(parts_of(p)):
                if i < len(parts):
                    parts[i] = parts[i] + seq
                else:
                    parts.append(seq)
        parts = [s for s in parts if s]
        # 파트→성부 최적 배정
        best = None
        idx = list(range(len(parts)))
        cands = [(None, None)] if not idx else \
            [(i, j) for i in idx + [None] for j in idx + [None]
             if i != j or (i is None and j is None)]
        for i, j in cands:
            e = 0
            e += edit(parts[i], voices[0]) if i is not None else len(voices[0])
            e += edit(parts[j], voices[1]) if j is not None else len(voices[1])
            e += sum(len(parts[k]) for k in idx if k not in (i, j))
            if best is None or e < best:
                best = e
        ne += best
        nt += pt_photo
        per.append(dict(photo=stem, parts=len(parts), err=best,
                        notes=pt_photo, ner=best / pt_photo))
    print(f'채점 {len(photos)}사진 (완전 실패 {fails}장 = 100% 오류로 포함)')
    ner = ne / max(1, nt)
    print(f'■ Audiveris 음표 NER {ner:.4%} ({ne}/{nt}음)')
    srt = sorted(per, key=lambda p: p['ner'])
    for p in srt[:3] + srt[-3:]:
        print(f"  {p['ner']:7.2%}  {p['photo']} (파트 {p['parts']})")
    json.dump(dict(ner_notes=ner, err=ne, notes=nt, per_photo=per),
              open(a.o, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('→', a.o)


if __name__ == '__main__':
    main()
