"""직접 조판한 초급 단선율 악보 → free-sheets 카탈로그 항목 + 파일 배치."""
import json, os, shutil, sys
FS = '/home/user/free-sheets'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out2')
MUT = 'https://www.mutopiaproject.org/ftp/'
TAGS = '초등 초급 단선율 계이름 쉬운 악보 리코더 멜로디언 바이올린 플루트 easy melody beginner recorder kids 儿童 简易 einfach fácil facile'
META = [
 # id, title(en), alias(ko), composer, level, license, source_url, extra tags
 ('ode', 'Ode to Joy (easy melody)', '환희의 송가', 'Ludwig van Beethoven', 1, 'CC0 (내 악보함 조판)', 'https://github.com/NAKJIKING/free-sheets', '베토벤 교향곡 9번 합창 Symphony No.9'),
 ('twinkle', 'Twinkle, Twinkle, Little Star (easy melody)', '반짝반짝 작은 별', 'Traditional', 1, 'CC0 (내 악보함 조판)', 'https://github.com/NAKJIKING/free-sheets', '작은별 반짝반짝 모차르트 변주곡 Ah vous dirai-je maman 小星星'),
 ('elise', 'Für Elise — A section (easy melody)', '엘리제를 위하여 (첫 부분)', 'Ludwig van Beethoven', 2, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'BeethovenLv/WoO59/fur_Elise_WoO59/', '엘리제 Fur Elise 致爱丽丝'),
 ('lullaby', "Brahms' Lullaby — Wiegenlied Op.49 No.4 (easy melody)", '브람스 자장가', 'Johannes Brahms', 1, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'BrahmsJ/LullabyBrahms-C/', '자장가 Lullaby Cradle Song 摇篮曲'),
 ('musette', 'Musette in D major BWV Anh.126 (melody)', '뮤제트 D장조', 'Anonymous', 2, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'BachJS/BWVAnh126/anna-magdalena-22/', '바흐 안나 막달레나 소곡집 Bach Notebook'),
 ('minuet', 'Minuet in G major BWV Anh.114 (melody)', '미뉴에트 G장조', 'Christian Petzold', 1, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'BachJS/BWVAnh114/anna-magdalena-04/', '바흐 미뉴에트 안나 막달레나 소곡집 Bach Minuet 小步舞曲'),
 ('turca', 'Rondo alla turca — theme (easy melody)', '터키 행진곡 주제', 'Wolfgang Amadeus Mozart', 2, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'MozartWA/KV331/KV331_3_RondoAllaTurca/', '터키행진곡 Turkish March 土耳其进行曲 K.331'),
 ('danube', 'The Blue Danube — waltz theme (easy melody)', '아름답고 푸른 도나우 주제', 'Johann Strauss II', 1, 'CC BY-SA 4.0 (내 악보함 조판 · 원본 Mutopia)', MUT + 'StraussJJ/O314/blue_danube/', '도나우 왈츠 Blue Danube Donau 蓝色多瑙河'),
 ('forelle', 'Die Forelle — The Trout (easy melody)', '송어', 'Franz Schubert', 2, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'SchubertF/D550/forelle/', '송어 Trout 鳟鱼 D.550'),
 ('greensleeves', 'Greensleeves (easy melody)', '그린슬리브즈', 'Traditional', 1, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'Traditional/greensleeves/', '그린슬리브스 영국 민요 绿袖子'),
 ('landmann', 'The Happy Farmer — Fröhlicher Landmann Op.68 No.10 (melody)', '즐거운 농부', 'Robert Schumann', 2, 'CC BY-SA 2.5 (내 악보함 조판 · 원본 Mutopia)', MUT + 'SchumannR/O68/schumann-op68-10-gai-laboureur/', '즐거운 농부 슈만 유겐트 앨범 Happy Farmer Merry Peasant 快乐的农夫'),
 ('gymno', 'Gymnopédie No.1 (melody)', '짐노페디 1번', 'Erik Satie', 1, 'CC0 (내 악보함 조판 · 원본 Mutopia PD)', MUT + 'SatieE/gymnopedie_1/', '짐노페디 사티 Gymnopedie 裸体歌舞'),
 ('largo', "Largo from the New World Symphony — Goin' Home (easy melody)", '꿈속의 고향 (신세계 교향곡 라르고)', 'Antonín Dvořák', 1, 'CC BY-SA 3.0 (내 악보함 조판 · 원본 Mutopia)', MUT + 'DvorakA/O95/Sym9/', '신세계 교향곡 라르고 꿈속의 고향 드보르작 New World Symphony Largo 自新大陆'),
]

def main(write):
    cat = json.load(open(os.path.join(FS, 'catalog.json'), encoding='utf-8'))
    have = {e['file'] for e in cat}
    new = []
    for pid, title, alias, comp, level, lic, url, extra in META:
        pdf = f'raw/original/{pid}.pdf'; mid = f'mids/original/{pid}.mid'; th = f'thumbs/original/{pid}.webp'
        e = {'source': 'original', 'source_url': url, 'file': pdf, 'title': title, 'composer': comp, 'instrument': 'Piano',
             'license': lic, 'thumb': th, 'midi': mid, 'alias': alias, 'tags': (extra + ' ' + TAGS).strip(), 'level': level}
        if write:
            for sub in ('raw/original', 'mids/original', 'thumbs/original'):
                os.makedirs(os.path.join(FS, sub), exist_ok=True)
            shutil.copy(os.path.join(OUT, pid + '.pdf'), os.path.join(FS, pdf))
            shutil.copy(os.path.join(OUT, pid + '.midi'), os.path.join(FS, mid))
            shutil.copy(os.path.join(OUT, pid + '.webp'), os.path.join(FS, th))
        if pdf in have:
            for i, x in enumerate(cat):
                if x['file'] == pdf: cat[i] = e
        else:
            cat.append(e)
        new.append(e)
    if write:
        json.dump(cat, open(os.path.join(FS, 'catalog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(new), 'entries', 'written' if write else 'dry')
    for e in new: print('  ', e['level'], e['alias'], '|', e['title'][:50], '|', e['license'][:40])

if __name__ == '__main__':
    main('--write' in sys.argv)
