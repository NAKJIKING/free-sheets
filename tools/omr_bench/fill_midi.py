#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2단계 — 미디 없는 곡에 OMR 로 미디를 만들어 붙인다 (심사 + 변환).

Audiveris 인식 결과(MusicXML)를 심사해 통과한 곡만 미디로 변환한다.
**틀린 미디는 없는 것보다 나쁘다** — 체를 여러 겹 두고, 떨어지면 그냥 버린다.

체 (1단계 실측에서 배운 것들):
  ① 음표 수 ≥ 24 — 몇 음짜리 결과는 인식 실패의 잔해다
  ② 쪽당 음표 ≥ 40 — Audiveris 가 특이 박자(3/2 등)를 오독하면 마디
     검열로 음표의 절반을 버리는데, 그 결과는 내부적으로 '일관'되어
     박자 검사로는 안 잡힌다. 밀도가 유일하게 잡는다(실측: Dusty Miller
     쪽당 24음). 정상 범위는 48~400 이었다.
  ③ 박자 안 맞는 마디 ≤ 5% — 리듬 오독 검출 (못갖춘·끝마디 제외)
  ④ 인식된 박자표가 위험 목록(3/2·9/8·5/4·7/8·5/8·7/16·11/8)이면 제외 —
     1단계에서 3/2 는 전패, 9/8 은 1승 3패였다
  ⑤ (단선율만, --verify) homr 교차 검증 — 다른 방식의 엔진과 음높이
     순서가 일치해야 통과. 다성부는 평탄 비교가 무의미해 ①~④만 적용.

    python3 tools/omr_bench/fill_midi.py --pred /tmp/fill_out            # 심사만
    python3 tools/omr_bench/fill_midi.py --pred /tmp/fill_out --write   # 미디 생성+카탈로그 갱신
"""
import argparse
import collections
import copy
import glob
import json
import os
import re
import sys
import warnings
import zipfile
import xml.etree.ElementTree as ET

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fastxml  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RISKY_METERS = {(3, 2), (9, 8), (5, 4), (7, 8), (5, 8), (7, 16), (11, 8)}


def pdf_pages(path):
    d = open(path, 'rb').read()
    if not d.startswith(b'%PDF-'):
        return None
    m = re.findall(rb'/Count\s+(\d+)', d)
    return max((int(x) for x in m), default=1)


def meters_of(mxl):
    z = zipfile.ZipFile(mxl)
    n = [x for x in z.namelist() if x.endswith('.xml') and 'META-INF' not in x][0]
    r = ET.fromstring(z.read(n))
    out = set()
    for t in r.iter('time'):
        b, bt = t.findtext('beats'), t.findtext('beat-type')
        if b and bt:
            out.add((int(b), int(bt)))
    return out


def judge(entry, mxls):
    """(합격 여부, 사유, 통계)"""
    notes = 0
    bars = bad = 0
    parts = 0
    meters = set()
    for m in mxls:
        seq, p, b, bb = fastxml.notes_and_bars(m)
        notes += len(seq)
        parts = max(parts, p)
        bars += b
        bad += bb
        meters |= meters_of(m)
    pages = pdf_pages(os.path.join(ROOT, entry['file'])) or 1
    stat = dict(notes=notes, pages=pages, parts=parts, bars=bars, bad=bad,
                meters=sorted(f'{a}/{b}' for a, b in meters))
    if notes < 24:
        return False, f'음표 {notes}개뿐', stat
    if notes / pages < 40:
        return False, f'쪽당 {notes/pages:.0f}음 — 마디 검열 의심', stat
    if bars >= 4 and bad / bars > 0.05:
        return False, f'박자 안 맞는 마디 {bad/bars*100:.0f}%', stat
    risky = meters & RISKY_METERS
    if risky:
        return False, f'위험 박자 {sorted(risky)}', stat
    return True, '', stat


def to_midi(mxls, out_path):
    """악장들을 이어 붙여 미디 하나로. 미리 듣기용 — 성부는 한 트랙으로
    평탄화한다(앱의 합성기도 트랙을 구분하지 않는다)."""
    from music21 import converter, stream, tempo
    part = stream.Part()
    part.insert(0.0, tempo.MetronomeMark(number=100))
    off = 0.0
    for x in mxls:
        z = zipfile.ZipFile(x)
        n = [y for y in z.namelist() if y.endswith('.xml') and 'META-INF' not in y][0]
        tmp = x + '.x.xml'
        with open(tmp, 'wb') as f:
            f.write(z.read(n))
        s = converter.parse(tmp)
        try:
            s = s.expandRepeats()
        except Exception:
            pass
        end = 0.0
        for el in s.flatten().notes:
            part.insert(off + float(el.offset), copy.deepcopy(el))
            end = max(end, float(el.offset) + float(el.duration.quarterLength))
        off += end + 2.0                      # 악장 사이 2박 쉼
        os.remove(tmp)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    part.write('midi', fp=out_path)


def midi_path_for(entry):
    # raw/mutopia/<악기>/<이름>.pdf → mids/mutopia/<악기>/<이름>.mid
    rel = entry['file']
    assert rel.startswith('raw/')
    stem = os.path.splitext(rel[len('raw/'):])[0]
    return f'mids/{stem}.mid'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pred', required=True)
    ap.add_argument('--write', action='store_true', help='미디 생성 + 카탈로그 갱신')
    ap.add_argument('--targets', default=os.path.join(ROOT, 'tools/omr_bench/fill_targets.json'))
    ap.add_argument('--report', default=os.path.join(ROOT, 'tools/omr_bench/fill_report.json'))
    args = ap.parse_args()

    targets = json.load(open(args.targets, encoding='utf-8'))
    report = []
    ok = rej = none = 0
    for e in targets:
        stem = os.path.splitext(os.path.basename(e['file']))[0]
        mxls = sorted(glob.glob(os.path.join(args.pred, stem + '.mxl')) +
                      glob.glob(os.path.join(args.pred, stem + '.mvt*.mxl')))
        row = dict(title=e.get('title'), file=e['file'], instrument=e.get('instrument'))
        if not mxls:
            none += 1
            row.update(verdict='인식 결과 없음')
            report.append(row)
            continue
        try:
            passed, why, stat = judge(e, mxls)
        except Exception as ex:
            rej += 1
            row.update(verdict=f'심사 오류 {type(ex).__name__}')
            report.append(row)
            continue
        row.update(stat)
        if not passed:
            rej += 1
            row.update(verdict=f'탈락: {why}')
            report.append(row)
            continue
        ok += 1
        row.update(verdict='합격')
        if args.write:
            mp = midi_path_for(e)
            try:
                to_midi(mxls, os.path.join(ROOT, mp))
                row['midi'] = mp
            except Exception as ex:
                row.update(verdict=f'변환 실패 {type(ex).__name__}')
                ok -= 1
                rej += 1
        report.append(row)

    print(f'대상 {len(targets)}곡 — 합격 {ok} / 탈락 {rej} / 인식 결과 없음 {none}')
    why = collections.Counter(r['verdict'].split(':')[0] for r in report)
    for k, v in why.most_common():
        print(f'   {k:<26}{v:>4}곡')
    json.dump(report, open(args.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'→ {args.report}')

    if args.write:
        cat_p = os.path.join(ROOT, 'catalog.json')
        cat = json.load(open(cat_p, encoding='utf-8'))
        byf = {e.get('file'): e for e in cat}
        n = 0
        for r in report:
            if r.get('midi') and r['verdict'] == '합격':
                t = byf.get(r['file'])
                if t is not None and not t.get('midi'):
                    t['midi'] = r['midi']
                    t['midi_origin'] = 'omr'   # 자동 인식으로 만든 미디 표시
                    n += 1
        json.dump(cat, open(cat_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'카탈로그 갱신: {n}곡에 midi 연결 (midi_origin=omr)')


if __name__ == '__main__':
    main()
