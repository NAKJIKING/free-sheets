#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4단계 데이터 공장 ② 실행기 — 라이브러리 미디 → 한 줄 악보 학습쌍.

    # 연기 시험 (곡 20개)
    python tools/omr_factory/make_lib_lines.py --out C:/Users/me/omr_lines --limit 20
    # 전체
    python tools/omr_factory/make_lib_lines.py --out C:/Users/me/omr_lines

설계 근거·받아들이는 조건은 `lib_lines.py` 머리말 참조.
**LILYPOND 환경변수로 실행 파일을 지정한다**(윈도우는 lilypond.exe).

정답 대조: 렌더할 때 LilyPond 가 같이 낸 미디를 다시 읽어 우리 토큰의
붙임줄 병합 음고열과 대조한다. 어긋나면 그 청크는 버리고 mismatch 로 센다
(.ly 작성 버그가 조용히 데이터에 섞이는 것을 막는 장치).
"""
import argparse
import hashlib
import json
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_lines as L

LILY = os.environ.get('LILYPOND', '/opt/lily/lilypond-2.24.4/bin/lilypond')


def plan_song(path, bars_per_line, max_chunks, keys_per_song, pool, mids_root):
    """미디 한 개 → 렌더할 작업 목록. 실패 이유는 문자열로 돌려준다."""
    got = L.melody_of(path)
    if not got:
        return None, '단선율없음/격자밖'
    notes, ts, ks = got
    if tuple(ts) not in L.TIMESIGS:
        return None, f'박자표제외 {ts[0]}/{ts[1]}'
    bt = L.bar_ticks(ts)
    bars = L.to_bars(notes, bt)
    if not bars:
        return None, '마디화실패'
    # 줄 길이를 박자표와 무관하게 비슷하게 맞춘다(2/4 4마디 = 8박, 4/4 4마디 =
    # 16박이라 그대로 두면 이미지 폭이 두 배씩 벌어진다).
    per = max(2, min(16, int(round(bars_per_line * 48 / bt))))
    if len(bars) < per:
        per = len(bars)                            # 짧은 곡은 있는 만큼 한 줄로
    if per < 2:
        return None, '너무짧음'
    tail = max(2, per // 2)                        # 꼬리 줄은 절반 이상이면 받는다
    key = L.song_key(path)
    var = L.variant_key(path, mids_root)
    shifts = L.pick_shifts(var, keys_per_song, pool)
    med = statistics.median(p for p, _s, _d in notes)
    jobs = []
    for ci in range(0, min(len(bars), max_chunks * per), per):
        sl = bars[ci:ci + per]
        if len(sl) < tail:
            break                                  # 꼬리의 너무 짧은 줄은 버린다
        if not any(p for bar in sl for p, _d, _t in bar):
            continue                               # 온통 쉼표
        idx = ci // per
        for sh in shifts:
            if not L.key_ok(ks, sh):
                continue                           # 조표 8개 이상 → 비현실
            h = int(hashlib.md5(f'{var}/{idx}/{sh}'.encode()).hexdigest(), 16)
            staff = (18, 20, 22, 24, 26)[h % 5]
            clef = 'bass' if med + sh < 55 else 'treble'
            tempo = (60, 72, 84, 96, 108, 120, 132)[h % 7] if idx == 0 else 0
            # 관문 3b — 도돌이·볼타 결정적 주입(~35% 줄). i0≥1 이라 |: 가
            # 항상 지면에 보인다(줄 머리 반복은 기호가 안 찍혀 라벨-그림 불일치).
            h2 = int(hashlib.md5(f'{var}/{idx}/{sh}/rep3b'.encode())
                     .hexdigest(), 16)
            n = len(sl)
            rep = None
            if h2 % 100 < 35 and n >= 2:
                if n >= 4 and (h2 >> 8) % 2:
                    i0 = 1 + (h2 >> 20) % (n - 3)      # 1..n-3
                    rep = [i0, n - 2, n - 1, n]        # 볼타 1·2 각 1마디
                else:
                    i0 = 1 + (h2 >> 9) % (n - 1)       # 1..n-1
                    i1 = n
                    if n - i0 >= 2 and (h2 >> 13) % 3 == 0:
                        i1 = i0 + 1 + (h2 >> 15) % (n - i0 - 1)
                    rep = [i0, i1]
            if rep:
                # 구조 경계를 붙임줄이 넘으면 전개 의미가 깨진다(2번째 연주에서
                # 다른 음으로 이어짐) → 그 줄은 주입 포기.
                for b in rep:
                    if 0 < b < n and sl[b - 1] and sl[b - 1][-1][2]:
                        rep = None
                        break
            jobs.append(dict(path=path, song=key, var=var, chunk=idx, shift=sh,
                             staff=staff, rep=rep,
                             clef=clef, tempo=tempo, ts=ts, ks=ks,
                             bars=[[list(e) for e in bar] for bar in sl]))
    return jobs, None


def run_job(a):
    out_root, j = a
    key, sharps = L.KEYSIG.get(j['ks'], ('c \\major', True))
    notes, tokens = L.bars_to_ly([[tuple(e) for e in bar] for bar in j['bars']],
                                 sharps, rep=j.get('rep'))
    if notes is None:
        return dict(st='표기불가', song=j['song'])
    src = L.SNIPPET % dict(
        staff=j['staff'], shift=L.SHIFT_NAME[j['shift']], clef=r'\clef ' + j['clef'],
        key=key, time=f"{j['ts'][0]}/{j['ts'][1]}",
        tempo=(f"\\tempo 4 = {j['tempo']}" if j['tempo'] else ''), notes=notes)
    safe = j['var']              # 파일 단위 폴더 — 같은 곡의 악기 판본끼리 안 겹침
    stem = f"c{j['chunk']:02d}_k{j['shift']:+d}".replace('+', 'p').replace('-', 'm')
    d = os.path.join(out_root, safe)
    png = os.path.join(d, stem + '.png')
    mid = L.found_midi(os.path.join(d, stem))
    st = 'ok'
    if os.path.exists(png) and mid:
        st = 'skip'                  # 재개 — 단, 대조는 건너뛰지 않는다(아래)
    else:
        png, mid, err = L.render(LILY, d, stem, src)
        if not png:
            return dict(st='렌더실패', song=j['song'], err=err)
    # 🔴 토큰은 반드시 '이미지에 보이는 음'(조옮김 후)으로 저장한다.
    # 이전 판은 조옮김 전 토큰을 저장하고 대조식에서만 시프트를 더해서,
    # 검사는 통과하는데 학습 라벨은 이미지와 어긋나는 결함이 있었다
    # (시프트≠0 표본 전부가 오답 라벨 = 데이터의 (keys-1)/keys).
    # cache/dataset/evaluate 는 토큰을 그대로 쓰므로 여기가 유일한 진실 지점.
    # 구조 토큰(p<0)은 음이 아니므로 조옮김하지 않는다 (관문 3b)
    tokens = [((tp + j['shift']) if tp > 0 else tp, td, tt)
              for tp, td, tt in tokens]
    # 정답 대조 — LilyPond 미디의 음고열 == 우리 토큰의 붙임줄 병합 음고열.
    # 재개(skip)한 줄도 반드시 대조한다. 안 하면 지난 실행에서 불일치로 버린
    # 파일이 다음 실행에서 조용히 통과해 데이터에 섞인다.
    # 미디는 \unfoldRepeats 로 전개돼 나오므로 우리 토큰도 전개해 대조 —
    # 구조 기호의 의미(연주 순서)까지 함께 검증된다 (관문 3b).
    want = L.merged_pitches(L.unfold_tokens(tokens))
    try:
        have = L.midi_notes(mid)
    except Exception as e:
        return dict(st='미디읽기실패', song=j['song'], err=repr(e)[:120])
    if want != have:
        return dict(st='대조불일치', song=j['song'],
                    err=f'want{want[:8]} have{have[:8]} len{len(want)}/{len(have)}')
    return dict(st=st, song=j['song'], var=safe, chunk=j['chunk'],
                shift=j['shift'], png=f'{safe}/{stem}.png',
                midi=f'{safe}/{os.path.basename(mid)}', tokens=tokens)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--mids', default='mids', help='미디 뿌리 폴더')
    ap.add_argument('--limit', type=int, default=0, help='곡 수 제한(연기 시험)')
    ap.add_argument('--bars', type=int, default=4, help='한 줄에 넣을 마디 수')
    ap.add_argument('--max-chunks', type=int, default=6, help='곡당 최대 줄 수')
    ap.add_argument('--keys', type=int, default=3, help='곡당 조 개수(0 포함)')
    ap.add_argument('--key-pool', default=','.join(str(k) for k in L.SHIFT_NAME))
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    ap.add_argument('--only', nargs='*', help='파일 경로에 이 문자열이 든 것만')
    a = ap.parse_args()
    pool = [int(x) for x in a.key_pool.split(',')]
    for s in pool:
        assert s in L.SHIFT_NAME, f'시프트 {s} 범위 밖'

    paths = []
    for root, _d, fs in os.walk(a.mids):
        for f in sorted(fs):
            if f.endswith(('.mid', '.midi')):
                paths.append(os.path.join(root, f).replace('\\', '/'))
    paths.sort()
    if a.only:
        paths = [p for p in paths if any(o in p for o in a.only)]
    if a.limit:
        paths = paths[:a.limit]
    print(f'미디 {len(paths)}개 조사 중…', flush=True)

    jobs, why = [], {}
    for p in paths:
        js, err = plan_song(p, a.bars, a.max_chunks, a.keys, pool, a.mids)
        if err:
            why[err] = why.get(err, 0) + 1
        else:
            jobs.extend(js)
    print(f'렌더 작업 {len(jobs)}건 (병렬 {a.jobs}) / 곡 탈락 {sum(why.values())} {why}',
          flush=True)

    os.makedirs(a.out, exist_ok=True)
    mpath = os.path.join(a.out, 'manifest.jsonl')
    cnt = {}
    n = 0
    with open(mpath, 'w', encoding='utf-8') as mf, \
            ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for r in ex.map(run_job, ((a.out, j) for j in jobs), chunksize=8):
            cnt[r['st']] = cnt.get(r['st'], 0) + 1
            n += 1
            if r['st'] in ('ok', 'skip'):
                mf.write(json.dumps(dict(song=r['song'], var=r['var'],
                                         chunk=r['chunk'], shift=r['shift'],
                                         png=r['png'], midi=r['midi'],
                                         tokens=r['tokens']),
                                    ensure_ascii=False) + '\n')
            elif cnt[r['st']] <= 3:
                print(f"  ! {r['st']} {r['song']} {r.get('err','')}", flush=True)
            if n % 2000 == 0:
                print(f'  {n}/{len(jobs)} {cnt}', flush=True)
    print(f'끝: {cnt} → {mpath}', flush=True)


if __name__ == '__main__':
    main()
