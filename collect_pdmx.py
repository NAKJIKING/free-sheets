"""PDMX(MuseScore 파생 퍼블릭 도메인 25만 곡) 수집기.

1단계(정찰): Zenodo 레코드의 파일 목록·크기, 메타데이터 구조를 로그로 출력.
관악·현악(플루트·클라리넷·트럼펫·색소폰·바이올린·첼로) 위주로
no_license_conflict 서브셋에서 골라 PDF를 가져오는 것이 최종 목표.
"""
import json
import os
import urllib.request

RECORD = '15571083'
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (public-domain collector)'}


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if binary else data.decode('utf-8', 'replace')


def main():
    print('== PDMX 정찰: Zenodo 파일 목록', flush=True)
    rec = json.loads(fetch(f'https://zenodo.org/api/records/{RECORD}'))
    for f in rec.get('files', []):
        size_mb = f.get('size', 0) / 1e6
        print(f"  {f.get('key')}  {size_mb:.1f} MB  {f.get('links', {}).get('self', '')}",
              flush=True)
    print('== 레코드 설명(앞 2000자) ==', flush=True)
    desc = rec.get('metadata', {}).get('description', '')
    import re
    print(re.sub(r'<[^>]+>', ' ', desc)[:2000], flush=True)


if __name__ == '__main__':
    main()
