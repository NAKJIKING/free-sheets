#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한글 검색 태그 주입 — 카탈로그 각 곡에 검색 전용 tags 필드를 채운다.

앱 검색이 제목·작곡가·별칭에 더해 tags 도 보므로, 한국에서 통용되는
작곡가 이름(바흐·쇼팽…)과 유명 곡 제목(엘리제를 위하여·월광…),
장르어(왈츠·녹턴·캐럴…)로 검색이 가능해진다.

tags 는 화면에 표시되지 않는다 — 표시용 한국어 제목은 alias 가 맡는다.
매 실행마다 전부 새로 계산하므로 사전만 고치고 다시 돌리면 된다.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')

# 정규화된 작곡가 이름(normalize_composers.py 결과) → 한글 표기.
# 두 표기가 통용되면 둘 다 넣는다 (띄어쓰기로 구분).
COMPOSER_KO = {
    'Johann Sebastian Bach': '바흐',
    'Ludwig van Beethoven': '베토벤',
    'Wolfgang Amadeus Mozart': '모차르트',
    'Frédéric Chopin': '쇼팽',
    'Franz Schubert': '슈베르트',
    'Johannes Brahms': '브람스',
    'Robert Schumann': '슈만',
    'Clara Schumann': '클라라 슈만',
    'Franz Liszt': '리스트',
    'Claude Debussy': '드뷔시',
    'Maurice Ravel': '라벨',
    'Erik Satie': '사티',
    'Gabriel Fauré': '포레',
    'Camille Saint-Saëns': '생상스 생상',
    'Georges Bizet': '비제',
    'Joseph Haydn': '하이든',
    'George Frideric Handel': '헨델',
    'Antonio Vivaldi': '비발디',
    'Johann Pachelbel': '파헬벨',
    'Georg Philipp Telemann': '텔레만',
    'Henry Purcell': '퍼셀',
    'Domenico Scarlatti': '스카를라티',
    'François Couperin': '쿠프랭',
    'Jean-Philippe Rameau': '라모',
    'Felix Mendelssohn': '멘델스존',
    'Fanny Hensel': '파니 헨젤 파니 멘델스존',
    'Pyotr Ilyich Tchaikovsky': '차이콥스키 차이코프스키',
    'Sergei Rachmaninoff': '라흐마니노프',
    'Alexander Scriabin': '스크랴빈 스크리아빈',
    'Modest Mussorgsky': '무소르그스키',
    'Nikolai Rimsky-Korsakov': '림스키코르사코프',
    'Antonín Dvořák': '드보르자크 드보르작',
    'Bedřich Smetana': '스메타나',
    'Edvard Grieg': '그리그',
    'Jean Sibelius': '시벨리우스',
    'Edward Elgar': '엘가',
    'Gustav Holst': '홀스트',
    'Gustav Mahler': '말러',
    'Anton Bruckner': '브루크너',
    'Richard Wagner': '바그너',
    'Giuseppe Verdi': '베르디',
    'Giacomo Puccini': '푸치니',
    'Gioachino Rossini': '로시니',
    'Luigi Boccherini': '보케리니',
    'Niccolò Paganini': '파가니니',
    'Pablo de Sarasate': '사라사테',
    'Henryk Wieniawski': '비에니아프스키',
    'Isaac Albéniz': '알베니스',
    'Enrique Granados': '그라나도스',
    'Francisco Tárrega': '타레가',
    'Fernando Sor': '소르',
    'Mauro Giuliani': '줄리아니',
    'Ferdinando Carulli': '카룰리',
    'Matteo Carcassi': '카르카시',
    'John Dowland': '다울랜드',
    'Scott Joplin': '조플린',
    'George Gershwin': '거슈윈',
    'Carl Czerny': '체르니',
    'Charles-Louis Hanon': '하농',
    'Friedrich Burgmüller': '부르크뮐러 부르그뮐러',
    'Muzio Clementi': '클레멘티',
    'Friedrich Kuhlau': '쿨라우',
    'Cornelius Gurlitt': '구를리트',
    'Ignaz Moscheles': '모셸레스',
    'Sigismond Thalberg': '탈베르크',
    'Charles-Valentin Alkan': '알캉',
    'Moritz Moszkowski': '모슈코프스키',
    'Cécile Chaminade': '샤미나드',
    'Hugo Wolf': '후고 볼프',
    'Traditional': '민요 전통곡',
    'Anonymous': '작자미상 미상',
}

# 제목 패턴(대소문자 무시) → 한글 태그. 위에서 아래로 전부 검사해
# 맞는 태그를 모두 붙인다 — 짧은 단어는 \b 로 오탐을 막는다.
TITLE_KO = [
    (r'f[üu]r elise', '엘리제를 위하여'),
    (r'moonlight', '월광'),
    (r'path[ée]tique', '비창'),
    (r'appassionata', '열정'),
    (r'alla turca|turkish march', '터키 행진곡'),
    (r'twinkle|ah,? vous dirai', '작은 별 반짝반짝'),
    (r'four seasons|quattro stagioni', '사계'),
    (r'canon in d', '캐논'),
    (r'air on (the )?g string', 'G선상의 아리아'),
    (r'ave maria', '아베마리아 아베 마리아'),
    (r'wedding march|bridal chorus', '결혼행진곡 결혼 행진곡'),
    (r'hungarian dance|ungarischer tanz', '헝가리 무곡'),
    (r'hungarian rhapsod', '헝가리 광시곡'),
    (r'la campanella', '라 캄파넬라'),
    (r'liebestraum', '사랑의 꿈'),
    (r'clair de lune', '달빛'),
    (r'gymnop[ée]die', '짐노페디'),
    (r'gnossienne', '그노시엔느'),
    (r'arabesque', '아라베스크'),
    (r'r[êe]verie', '몽상'),
    (r'tr[äa]umerei', '트로이메라이 꿈'),
    (r'kinderszenen|scenes from childhood', '어린이 정경'),
    (r'songs? without words|lieder ohne worte', '무언가'),
    (r'spring song|fr[üu]hlingslied', '봄노래 봄의 노래'),
    (r'swan lake', '백조의 호수'),
    (r'nutcracker|casse.?noisette', '호두까기 인형'),
    (r'waltz of the flowers', '꽃의 왈츠'),
    (r'\bthe swan\b|le cygne', '백조'),
    (r'carnival of the animals', '동물의 사육제'),
    (r'pomp and circumstance', '위풍당당 행진곡'),
    (r'minute waltz|valse minute', '강아지 왈츠'),
    (r'raindrop', '빗방울 전주곡'),
    (r'fantaisie.?impromptu', '환상 즉흥곡 즉흥환상곡'),
    (r'tristesse|chanson de l\'adieu', '이별의 곡'),
    (r'revolutionary', '혁명'),
    (r'h[ée]ro[iï]que', '영웅 폴로네즈'),
    (r'military polonaise', '군대 폴로네즈'),
    (r'polonaise', '폴로네즈'),
    (r'goldberg', '골드베르크 변주곡'),
    (r'well.?tempered|wohltemperierte', '평균율'),
    (r'\binvention', '인벤션'),
    (r'toccata (and|und) fug', '토카타와 푸가'),
    (r'brandenburg', '브란덴부르크'),
    (r'cello suite|suite for (unaccompanied )?cello', '무반주 첼로 모음곡'),
    (r'jesu,? joy|jesus bleibet', '예수는 인간 소망의 기쁨'),
    (r'messiah', '메시아'),
    (r'hallelujah', '할렐루야'),
    (r'water music|wassermusik', '수상음악'),
    (r'ombra mai fu', '라르고 옴브라 마이 푸'),
    (r'eine kleine nachtmusik', '아이네 클라이네 나흐트무지크 소야곡'),
    (r'queen of the night|h[öo]lle rache', '밤의 여왕'),
    (r'(marriage|nozze) (of|di) figaro', '피가로의 결혼'),
    (r'magic flute|zauberfl[öo]te', '마술피리'),
    (r'vltava|moldau', '몰다우'),
    (r'new world', '신세계'),
    (r'humoresque|humoreske', '유모레스크'),
    (r'flight of the bumblebee', '왕벌의 비행'),
    (r'blue danube|blauen donau', '아름답고 푸른 도나우'),
    (r'radetzky', '라데츠키 행진곡'),
    (r'william tell|guillaume tell', '윌리엄 텔'),
    (r'barb(er|iere) (of|di) sevil', '세비야의 이발사'),
    (r'la donna [èe] mobile', '여자의 마음'),
    (r'libiamo|brindisi', '축배의 노래'),
    (r'o sole mio', '오 솔레 미오'),
    (r'funicul[iì]', '푸니쿨리 푸니쿨라'),
    (r'santa lucia', '산타 루치아'),
    (r'home,? sweet home', '즐거운 나의 집'),
    (r'auld lang syne', '올드 랭 사인 석별의 정'),
    (r'danny boy|londonderry air', '대니 보이'),
    (r'greensleeves', '그린슬리브즈'),
    (r'ode to joy|an die freude', '환희의 송가'),
    (r'salut d\'amour', '사랑의 인사'),
    (r'erlk[öo]nig|erl.?king', '마왕'),
    (r'\bforelle\b|\btrout\b', '송어'),
    (r'st[äa]ndchen|serenade|serenata', '세레나데'),
    (r'wiegenlied|lullaby|berceuse|cradle song', '자장가'),
    (r'csik[oó]s post', '크시코스의 우편마차'),
    (r'the entertainer', '엔터테이너'),
    (r'maple leaf rag', '메이플 리프 래그'),
    (r'\brag(time)?\b', '래그타임'),
    (r'tarantell?a', '타란텔라'),
    (r'bol[ée]ro', '볼레로'),
    (r'pavane', '파반느'),
    (r'sicilien(ne|o)|siciliano', '시칠리아노'),
    (r'la fille aux cheveux de lin', '아마빛 머리의 소녀'),
    (r'golliwog', '골리워그'),
    (r'nocturne|notturno', '녹턴 야상곡'),
    (r'\bwaltz\b|\bvalse\b|\bwalzer\b', '왈츠'),
    (r'minuet|menuett?', '미뉴에트'),
    (r'pr[ée]lude|pr[äa]ludium', '전주곡 프렐류드'),
    (r'[ée]tude|et[üu]de', '연습곡 에튀드'),
    (r'impromptu', '즉흥곡'),
    (r'mazurka', '마주르카'),
    (r'ballade', '발라드'),
    (r'scherzo', '스케르초'),
    (r'rhapsod', '광시곡 랩소디'),
    (r'symphon|sinfoni', '교향곡 심포니'),
    (r'concert(o|ino)|konzert', '협주곡 콘체르토'),
    (r'sonatin[ae]', '소나티네 소나티나'),
    (r'sonat[ae]\b', '소나타'),
    (r'variation|variazioni', '변주곡'),
    (r'\bfug(ue|a|e)\b', '푸가'),
    (r'\bmarch\b|\bmarche\b|\bmarsch\b', '행진곡'),
    (r'christmas|carol|no[ëe]l\b|weihnacht', '캐럴 크리스마스 성탄'),
]
TITLE_KO = [(re.compile(p, re.IGNORECASE), t) for p, t in TITLE_KO]


def tags_for(e):
    words = []
    ko = COMPOSER_KO.get(e.get('composer', ''))
    if ko:
        words.append(ko)
    title = e.get('title', '')
    for rx, t in TITLE_KO:
        if rx.search(title):
            words.append(t)
    # 찬송가는 장르어로도 찾게 한다.
    if e.get('source') == 'openhymnal':
        words.append('찬송가 찬송 성가')
    # 중복 단어 제거(순서 유지).
    seen, out = set(), []
    for w in ' '.join(words).split():
        if w not in seen:
            seen.add(w)
            out.append(w)
    return ' '.join(out)


def main():
    with open(CATALOG, encoding='utf-8') as f:
        catalog = json.load(f)
    hit = 0
    for e in catalog:
        t = tags_for(e)
        if t:
            e['tags'] = t
            hit += 1
        else:
            e.pop('tags', None)
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    print(f'{len(catalog)}곡 중 한글 태그 주입 {hit}곡', flush=True)


if __name__ == '__main__':
    main()
