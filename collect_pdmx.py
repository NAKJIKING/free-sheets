"""PDMX(MuseScore 파생 퍼블릭 도메인 25만 곡) 수집기.

2단계(정찰2): PDMX.csv 헤더·샘플 행, subset_paths 목록, metadata JSON 구조 확인.
목표: 관악·현악 솔로/이중주 악보를 no_license_conflict 서브셋에서 골라
pdf.tar.gz 를 스트리밍하며 해당 PDF만 추출.
"""
import csv
import io
import json
import tarfile
import urllib.request

BASE = 'https://zenodo.org/api/records/15571083/files'
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (public-domain collector)'}


def open_url(name):
    req = urllib.request.Request(f'{BASE}/{name}/content', headers=UA)
    return urllib.request.urlopen(req, timeout=300)


def main():
    print('== 정찰2a: PDMX.csv 헤더 + 샘플 3행', flush=True)
    with open_url('PDMX.csv') as r:
        text = io.TextIOWrapper(r, encoding='utf-8', errors='replace')
        reader = csv.reader(text)
        header = next(reader)
        print('컬럼:', header, flush=True)
        for i, row in enumerate(reader):
            print(f'--- 행 {i} ---', flush=True)
            for k, v in zip(header, row):
                print(f'  {k} = {v[:120]}', flush=True)
            if i >= 2:
                break

    print('== 정찰2b: subset_paths.tar.gz 구성', flush=True)
    with open_url('subset_paths.tar.gz') as r:
        with tarfile.open(fileobj=r, mode='r|gz') as tf:
            for m in tf:
                print(f'  {m.name}  {m.size/1e6:.1f} MB', flush=True)
                # 첫 텍스트 파일의 앞 3줄 훔쳐보기
                if m.isfile() and m.size > 0 and m.size < 50e6:
                    f = tf.extractfile(m)
                    head = f.read(500).decode('utf-8', 'replace')
                    print('    앞부분:', head[:300].replace('\n', ' | '), flush=True)

    print('== 정찰2c: metadata.tar.gz 첫 JSON 구조', flush=True)
    with open_url('metadata.tar.gz') as r:
        with tarfile.open(fileobj=r, mode='r|gz') as tf:
            shown = 0
            for m in tf:
                if not m.isfile() or not m.name.endswith('.json'):
                    continue
                data = json.loads(tf.extractfile(m).read().decode('utf-8', 'replace'))
                print(f'  파일: {m.name}', flush=True)
                print('  키:', list(data.keys())[:30], flush=True)
                print('  샘플:', json.dumps(data, ensure_ascii=False)[:800], flush=True)
                shown += 1
                if shown >= 2:
                    break
    print('done', flush=True)


if __name__ == '__main__':
    main()
