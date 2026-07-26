#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""다국어 검색 태그 주입 — 카탈로그 각 곡에 검색 전용 tags 필드를 채운다.

앱 검색이 제목·작곡가·별칭에 더해 tags 도 보므로, 앱이 지원하는
언어들(한국어·중국어·독일어·프랑스어·스페인어·포르투갈어·인도네시아어)
로 작곡가 이름·유명 곡 제목·장르어 검색이 가능해진다. 영어는 원제
그대로 검색된다.

덤으로 발음구별기호를 벗긴 표기도 넣는다 — "Für Elise"를 fur elise 로,
"Dvořák"을 dvorak 으로 찾을 수 있다.

tags 는 화면에 표시되지 않는다 — 표시용 한국어 제목은 alias 가 맡는다.
매 실행마다 전부 새로 계산하므로 사전만 고치고 다시 돌리면 된다.
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')

# 정규화된 작곡가 이름(normalize_composers.py 결과) → 다국어 표기.
# 한국어·중국어(간체)·통용되는 유럽어 변형 철자를 띄어쓰기로 이어 쓴다.
COMPOSER_TAGS = {
    'Johann Sebastian Bach': '바흐 巴赫',
    'Ludwig van Beethoven': '베토벤 贝多芬',
    'Wolfgang Amadeus Mozart': '모차르트 莫扎特',
    'Frédéric Chopin': '쇼팽 肖邦',
    'Franz Schubert': '슈베르트 舒伯特',
    'Johannes Brahms': '브람스 勃拉姆斯',
    'Robert Schumann': '슈만 舒曼',
    'Clara Schumann': '클라라 슈만 克拉拉 舒曼',
    'Franz Liszt': '리스트 李斯特',
    'Claude Debussy': '드뷔시 德彪西',
    'Maurice Ravel': '라벨 拉威尔',
    'Erik Satie': '사티 萨蒂',
    'Gabriel Fauré': '포레 福雷',
    'Camille Saint-Saëns': '생상스 생상 圣桑',
    'Georges Bizet': '비제 比才',
    'Joseph Haydn': '하이든 海顿',
    'George Frideric Handel': '헨델 亨德尔 Händel Haendel',
    'Antonio Vivaldi': '비발디 维瓦尔第',
    'Johann Pachelbel': '파헬벨 帕赫贝尔',
    'Georg Philipp Telemann': '텔레만 泰勒曼',
    'Henry Purcell': '퍼셀 珀塞尔',
    'Domenico Scarlatti': '스카를라티 斯卡拉蒂',
    'François Couperin': '쿠프랭 库普兰',
    'Jean-Philippe Rameau': '라모 拉莫',
    'Felix Mendelssohn': '멘델스존 门德尔松',
    'Fanny Hensel': '파니 헨젤 파니 멘델스존 芬妮 门德尔松',
    'Pyotr Ilyich Tchaikovsky':
        '차이콥스키 차이코프스키 柴可夫斯基 Tschaikowski Tchaikovski Chaikovski',
    'Sergei Rachmaninoff': '라흐마니노프 拉赫玛尼诺夫 Rachmaninov',
    'Alexander Scriabin': '스크랴빈 스크리아빈 斯克里亚宾 Skrjabin',
    'Modest Mussorgsky': '무소르그스키 穆索尔斯基 Moussorgski Mussorgski',
    'Nikolai Rimsky-Korsakov': '림스키코르사코프 里姆斯基 Rimski',
    'Antonín Dvořák': '드보르자크 드보르작 德沃夏克',
    'Bedřich Smetana': '스메타나 斯美塔那',
    'Edvard Grieg': '그리그 格里格',
    'Jean Sibelius': '시벨리우스 西贝柳斯',
    'Edward Elgar': '엘가 埃尔加',
    'Gustav Holst': '홀스트 霍尔斯特',
    'Gustav Mahler': '말러 马勒',
    'Anton Bruckner': '브루크너 布鲁克纳',
    'Richard Wagner': '바그너 瓦格纳',
    'Giuseppe Verdi': '베르디 威尔第',
    'Giacomo Puccini': '푸치니 普契尼',
    'Gioachino Rossini': '로시니 罗西尼',
    'Luigi Boccherini': '보케리니 博凯里尼',
    'Niccolò Paganini': '파가니니 帕格尼尼',
    'Pablo de Sarasate': '사라사테 萨拉萨蒂',
    'Henryk Wieniawski': '비에니아프스키 维尼亚夫斯基',
    'Isaac Albéniz': '알베니스 阿尔贝尼斯',
    'Enrique Granados': '그라나도스 格拉纳多斯',
    'Francisco Tárrega': '타레가 塔雷加',
    'Fernando Sor': '소르 索尔',
    'Mauro Giuliani': '줄리아니 朱利亚尼',
    'Ferdinando Carulli': '카룰리 卡鲁利',
    'Matteo Carcassi': '카르카시 卡尔卡西',
    'John Dowland': '다울랜드 道兰',
    'Scott Joplin': '조플린 乔普林',
    'George Gershwin': '거슈윈 格什温',
    'Carl Czerny': '체르니 车尔尼',
    'Charles-Louis Hanon': '하농 哈农',
    'Friedrich Burgmüller': '부르크뮐러 부르그뮐러 布格缪勒',
    'Muzio Clementi': '클레멘티 克莱门蒂',
    'Friedrich Kuhlau': '쿨라우 库劳',
    'Cornelius Gurlitt': '구를리트 古尔利特',
    'Ignaz Moscheles': '모셸레스 莫谢莱斯',
    'Sigismond Thalberg': '탈베르크 塔尔贝格',
    'Charles-Valentin Alkan': '알캉 阿尔坎',
    'Moritz Moszkowski': '모슈코프스키 莫什科夫斯基',
    'Cécile Chaminade': '샤미나드 夏米娜德',
    'Hugo Wolf': '후고 볼프 沃尔夫',
    'Traditional': '민요 전통곡 民谣 传统 tradicional tradisional',
    'Anonymous': '작자미상 미상 佚名 anonimo anonim',
}

# 제목 패턴(대소문자 무시) → 다국어 태그. 위에서 아래로 전부 검사해
# 맞는 태그를 모두 붙인다 — 짧은 단어는 \b 로 오탐을 막는다.
# 표기 순서: 한국어 · 중국어 · 독일어/프랑스어/스페인어/포르투갈어 변형.
TITLE_TAGS = [
    (r'f[üu]r elise', '엘리제를 위하여 致爱丽丝 Para Elisa Lettre à Élise'),
    (r'moonlight',
     '월광 月光 Mondschein Sonate au clair de lune Claro de Luna ao Luar'),
    (r'path[ée]tique', '비창 悲怆'),
    (r'appassionata', '열정 热情'),
    (r'alla turca|turkish march',
     '터키 행진곡 土耳其进行曲 Türkischer Marsch Marche turque Marcha Turca'),
    (r'twinkle|ah,? vous dirai', '작은 별 반짝반짝 小星星'),
    (r'four seasons|quattro stagioni',
     '사계 四季 Jahreszeiten Quatre Saisons Cuatro Estaciones '
     'Quatro Estações'),
    (r'canon in d', '캐논 卡农 Kanon'),
    (r'air on (the )?g string', 'G선상의 아리아 G弦上的咏叹调'),
    (r'ave maria', '아베마리아 아베 마리아 圣母颂'),
    (r'wedding march|bridal chorus',
     '결혼행진곡 결혼 행진곡 婚礼进行曲 Hochzeitsmarsch Marche nuptiale '
     'Marcha Nupcial'),
    (r'hungarian dance|ungarischer tanz',
     '헝가리 무곡 匈牙利舞曲 Danza húngara'),
    (r'hungarian rhapsod', '헝가리 광시곡 匈牙利狂想曲'),
    (r'la campanella', '라 캄파넬라 钟'),
    (r'liebestraum', '사랑의 꿈 爱之梦 Sueño de amor'),
    (r'clair de lune', '달빛 月光'),
    (r'gymnop[ée]die', '짐노페디'),
    (r'gnossienne', '그노시엔느'),
    (r'arabesque', '아라베스크 阿拉伯风格曲'),
    (r'r[êe]verie', '몽상 梦幻'),
    (r'tr[äa]umerei', '트로이메라이 꿈 梦幻曲'),
    (r'kinderszenen|scenes from childhood', '어린이 정경 童年情景'),
    (r'songs? without words|lieder ohne worte',
     '무언가 无词歌 Romances sans paroles'),
    (r'spring song|fr[üu]hlingslied', '봄노래 봄의 노래 春之歌'),
    (r'swan lake',
     '백조의 호수 天鹅湖 Schwanensee Lac des cygnes Lago de los Cisnes '
     'Lago dos Cisnes'),
    (r'nutcracker|casse.?noisette',
     '호두까기 인형 胡桃夹子 Nussknacker Cascanueces Quebra-Nozes'),
    (r'waltz of the flowers',
     '꽃의 왈츠 花之圆舞曲 Blumenwalzer Valse des fleurs Vals de las Flores '
     'Valsa das Flores'),
    (r'\bthe swan\b|le cygne', '백조 天鹅 Schwan Cisne'),
    (r'carnival of the animals',
     '동물의 사육제 动物狂欢节 Karneval der Tiere Carnaval des animaux '
     'Carnaval de los Animales'),
    (r'pomp and circumstance', '위풍당당 행진곡 威风堂堂'),
    (r'minute waltz|valse minute', '강아지 왈츠 小狗圆舞曲'),
    (r'raindrop', '빗방울 전주곡 雨滴'),
    (r'fantaisie.?impromptu', '환상 즉흥곡 즉흥환상곡 幻想即兴曲'),
    (r'tristesse|chanson de l\'adieu', '이별의 곡 离别曲'),
    (r'revolutionary', '혁명 革命'),
    (r'h[ée]ro[iï]que', '영웅 폴로네즈 英雄'),
    (r'military polonaise', '군대 폴로네즈 军队'),
    (r'polonaise', '폴로네즈 波兰舞曲 Polonesa'),
    (r'goldberg', '골드베르크 변주곡 哥德堡变奏曲'),
    (r'well.?tempered|wohltemperierte', '평균율 平均律'),
    (r'\binvention', '인벤션 创意曲'),
    (r'toccata (and|und) fug', '토카타와 푸가 托卡塔与赋格'),
    (r'brandenburg', '브란덴부르크 勃兰登堡'),
    (r'cello suite|suite for (unaccompanied )?cello',
     '무반주 첼로 모음곡 大提琴组曲'),
    (r'jesu,? joy|jesus bleibet', '예수는 인간 소망의 기쁨'),
    (r'messiah', '메시아 弥赛亚 Messias Mesías'),
    (r'hallelujah', '할렐루야 哈利路亚 Aleluya Aleluia'),
    (r'water music|wassermusik', '수상음악 水上音乐'),
    (r'ombra mai fu', '라르고 옴브라 마이 푸'),
    (r'eine kleine nachtmusik', '아이네 클라이네 나흐트무지크 소야곡'),
    (r'queen of the night|h[öo]lle rache', '밤의 여왕 夜后'),
    (r'(marriage|nozze) (of|di) figaro',
     '피가로의 결혼 费加罗的婚礼 Hochzeit des Figaro Noces de Figaro '
     'Bodas de Fígaro'),
    (r'magic flute|zauberfl[öo]te',
     '마술피리 魔笛 Flauta Mágica Flûte enchantée'),
    (r'vltava|moldau', '몰다우 伏尔塔瓦河'),
    (r'new world', '신세계 自新世界 Neue Welt Nouveau Monde Nuevo Mundo'),
    (r'humoresque|humoreske', '유모레스크 幽默曲'),
    (r'flight of the bumblebee',
     '왕벌의 비행 野蜂飞舞 Hummelflug Vol du bourdon Vuelo del Moscardón '
     'Voo do Besouro'),
    (r'blue danube|blauen donau',
     '아름답고 푸른 도나우 蓝色多瑙河 Danubio Azul Danúbio Azul'),
    (r'radetzky', '라데츠키 행진곡 拉德茨基进行曲'),
    (r'william tell|guillaume tell', '윌리엄 텔 威廉退尔 Guillermo Tell'),
    (r'barb(er|iere) (of|di) sevil',
     '세비야의 이발사 塞维利亚的理发师 Barbero de Sevilla '
     'Barbeiro de Sevilha'),
    (r'la donna [èe] mobile', '여자의 마음 善变的女人'),
    (r'libiamo|brindisi', '축배의 노래 饮酒歌'),
    (r'o sole mio', '오 솔레 미오 我的太阳'),
    (r'funicul[iì]', '푸니쿨리 푸니쿨라'),
    (r'santa lucia', '산타 루치아 桑塔露琪亚'),
    (r'home,? sweet home', '즐거운 나의 집 甜蜜的家'),
    (r'auld lang syne', '올드 랭 사인 석별의 정 友谊地久天长'),
    (r'danny boy|londonderry air', '대니 보이 丹尼男孩'),
    (r'greensleeves', '그린슬리브즈 绿袖子'),
    (r'ode to joy|an die freude',
     '환희의 송가 欢乐颂 Hymne à la joie Himno de la Alegría'),
    (r'salut d\'amour', '사랑의 인사 爱的礼赞 Liebesgruß'),
    (r'erlk[öo]nig|erl.?king', '마왕 魔王'),
    (r'forelle|\btrout\b', '송어 鳟鱼'),
    (r's[ée]r[ée]nade|st[äa]ndchen|serenata', '세레나데 小夜曲'),
    (r'wiegenlied|lullaby|berceuse|cradle song',
     '자장가 摇篮曲 Canción de cuna Canção de ninar'),
    (r'csik[oó]s post', '크시코스의 우편마차'),
    (r'the entertainer', '엔터테이너'),
    (r'maple leaf rag', '메이플 리프 래그 枫叶'),
    (r'\brag(time)?\b', '래그타임 拉格泰姆'),
    (r'tarantell?a', '타란텔라 塔兰泰拉'),
    (r'bol[ée]ro', '볼레로 波莱罗'),
    (r'pavane', '파반느 帕凡舞曲 Pavana'),
    (r'sicilien(ne|o)|siciliano', '시칠리아노 西西里舞曲 Siciliana'),
    (r'la fille aux cheveux de lin', '아마빛 머리의 소녀 亚麻色头发的少女'),
    (r'golliwog', '골리워그'),
    (r'nocturne|notturno', '녹턴 야상곡 夜曲 Nocturno Noturno'),
    (r'\bwaltz\b|\bvalse\b|\bwalzer\b', '왈츠 圆舞曲 华尔兹 Vals Valsa'),
    (r'minuet|menuett?', '미뉴에트 小步舞曲 Minueto Minuetto'),
    (r'pr[ée]lude|pr[äa]ludium', '전주곡 프렐류드 前奏曲 Preludio'),
    (r'[ée]tude|et[üu]de', '연습곡 에튀드 练习曲 Estudio Estudo'),
    (r'impromptu', '즉흥곡 即兴曲'),
    (r'mazurka', '마주르카 玛祖卡 Mazurca'),
    (r'ballade', '발라드 叙事曲 Balada'),
    (r'scherzo', '스케르초 谐谑曲'),
    (r'rhapsod', '광시곡 랩소디 狂想曲 Rapsodia Rapsódia Rhapsodie'),
    (r'symphon|sinfoni', '교향곡 심포니 交响曲 Symphonie Sinfonía Sinfonia'),
    (r'concert(o|ino)|konzert', '협주곡 콘체르토 协奏曲 Concierto'),
    (r'sonatin[ae]', '소나티네 소나티나 小奏鸣曲 Sonatine'),
    (r'sonat[ae]\b', '소나타 奏鸣曲 Sonate'),
    (r'variation|variazioni', '변주곡 变奏曲 Variaciones Variações'),
    (r'\bfug(ue|a|e)\b', '푸가 赋格'),
    (r'\bmarch\b|\bmarche\b|\bmarsch\b', '행진곡 进行曲 Marcha'),
    (r'christmas|carol|no[ëe]l\b|weihnacht',
     '캐럴 크리스마스 성탄 圣诞 Weihnachten Navidad villancico Natal'),
]
TITLE_TAGS = [(re.compile(p, re.IGNORECASE), t) for p, t in TITLE_TAGS]

# 발음구별기호 벗기기 — NFKD 로 분해되지 않는 글자는 손으로 잇는다.
_FOLD_MAP = str.maketrans({
    'ß': 'ss', 'ø': 'o', 'Ø': 'O', 'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D',
    'æ': 'ae', 'Æ': 'AE', 'œ': 'oe', 'Œ': 'OE', 'ð': 'd', 'þ': 'th',
    'ı': 'i',
})


def fold(s):
    s = unicodedata.normalize('NFKD', s.translate(_FOLD_MAP))
    return ''.join(ch for ch in s if not unicodedata.combining(ch))


def tags_for(e):
    words = []
    composer = e.get('composer', '')
    ko = COMPOSER_TAGS.get(composer)
    if ko:
        words.append(ko)
    title = e.get('title', '')
    for rx, t in TITLE_TAGS:
        if rx.search(title):
            words.append(t)
    # 찬송가는 장르어로도 찾게 한다.
    if e.get('source') == 'openhymnal':
        words.append('찬송가 찬송 성가 赞美诗 圣诗 himno hino')
    # 발음구별기호 없는 표기 — 제목·작곡가가 접힌 꼴과 다르면 덧붙인다.
    for src in (title, composer):
        f = fold(src)
        if f.lower() != src.lower():
            words.append(f)
    # 중복 단어 제거(순서 유지).
    seen, out = set(), []
    for w in ' '.join(words).split():
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
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
    print(f'{len(catalog)}곡 중 검색 태그 주입 {hit}곡', flush=True)


if __name__ == '__main__':
    main()
