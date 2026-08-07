#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카탈로그 정리 — 앱에 보이는 품질 문제를 일괄 교정한다.

병합(merge2·merge3) 뒤에 항상 실행한다. 재실행 안전(멱등).

① 제목 없는 항목: 파일명에서 제목 복구 (mutopia 51곡이 앱에서 아예
   안 보이던 문제. 앱은 제목 없는 항목을 건너뛴다)
② 인코딩 깨진 글자: UTF-8을 latin-1로 잘못 읽어 바이트가 유실된 항목.
   되돌릴 수 없으므로 — 제목이 통째로 깨졌으면 제외, 작곡가만 깨졌으면
   작곡가를 비운다.
③ 같은 곡 중복: 같은 작품이 여러 번 올라온 것(예: 파가니니 24 카프리스
   17줄)을 하나로. 단 민속곡(thesession)은 같은 이름의 서로 다른 곡이
   많으므로(예: Paddy Fahey's 29곡) 중복으로 보지 않는다.
④ 정렬: 첫 화면에 알려진 곡이 오도록 소스 우선순위로 재배열.
   민속곡은 뒤로 보낸다.
"""
import json
import os
import re

from normalize_composers import normalize as normalize_composer

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')

# 깨진 인코딩 판별.
# 주의: Ä·Å·Ö는 스웨덴어·독일어에서 정상으로 쓰인다('Äppelbo Gånglåt',
# 'An eine Äolsharfe'). 정상 표기를 지우지 않도록 손상 고유의 흔적만 잡는다.
#  - 'Ã', 'â€'는 정상 표기에 나오지 않는다 → 손상 확정
#  - 낱말 중간에 오는 대문자 악센트(TraviÄka, SkaÄe, krustÄ)는 손상.
#    정상 표기는 낱말 첫 글자에만 온다(Äppelbo, Är, Ästhetik)
#  - 키릴 오독(Ð·Ñ 연속)은 손상
ACCENT_UPPER = 'ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ'
_MIDWORD = re.compile('[a-zà-öø-ÿ][' + ACCENT_UPPER + ']')
_CYR = re.compile('[ÐÑ][-¿†-›]|[ÐÑ].[ÐÑ]')


def is_broken(s):
    """되돌릴 수 없이 손상된 문자열인지."""
    s = s or ''
    if not s:
        return False
    if 'Ã' in s or 'â€' in s:
        return True
    if _MIDWORD.search(s):
        return True
    # 키릴 오독: Ð/Ñ가 여러 번 반복되면 손상
    if sum(s.count(c) for c in 'ÐÑ') >= 3:
        return True
    return False

# ⓪ 저작권·품질 차단 목록 — 2026-07 전수 점검 결과.
#    병합이 다시 담아 와도 여기서 늘 걸러진다 (source_url 기준).
#    원칙: 작곡가가 특정되는 현대곡(사후 70년 미경과)은 제거.
#    연주자 이름만 붙은 전통곡(Cooley's 등)은 유지.
BLOCKED_URLS = {
    # ── thesession: 비틀즈·영화·게임 유래 ─────────────────────
    'https://thesession.org/tunes/2705',   # Hey Jude (McCartney)
    'https://thesession.org/tunes/12615',  # Zelda (현대 추정)
    'https://thesession.org/tunes/4197',   # Rohan (현대 추정)
    # ── thesession: 현대 작곡가 작품 (트래드로 통용되지만 저작권 존속) ──
    'https://thesession.org/tunes/4997',   # Ashokan Farewell (Jay Ungar 1982)
    'https://thesession.org/tunes/346',    # Music for a Found Harmonium (Jeffes †1997)
    'https://thesession.org/tunes/1016',   # Josefin's (Roger Tallroth 생존)
    'https://thesession.org/tunes/15',     # Calliope House (Dave Richardson 생존)
    'https://thesession.org/tunes/1863',   # Da Slockit Light (Tom Anderson †1991)
    'https://thesession.org/tunes/5020',   # Midnight on the Water (Thomasson)
    'https://thesession.org/tunes/211',    # Inisheer (Thomas Walsh 1979)
    'https://thesession.org/tunes/562',    # Crested Hens (Gilles Chabenat 생존)
    'https://thesession.org/tunes/703',    # Catharsis (Amy Cann 생존)
    'https://thesession.org/tunes/3014',   # Ed Reavy's (†1988)
    'https://thesession.org/tunes/8921',   # Reavy's (†1988)
    'https://thesession.org/tunes/302',    # Maudabawn Chapel (Ed Reavy)
    'https://thesession.org/tunes/472',    # The Hunter's House (Ed Reavy)
    'https://thesession.org/tunes/636',    # The Otter's Holt (Junior Crehan †1998)
    'https://thesession.org/tunes/256',    # Mist Covered Mountain (Junior Crehan)
    'https://thesession.org/tunes/36',     # The Golden Keyboard (V. Broderick †2008)
    'https://thesession.org/tunes/4724',   # Darby's Farewell to London (McDermott †1992)
    'https://thesession.org/tunes/14008',  # Glen Allen (Sean Ryan †1985)
    'https://thesession.org/tunes/3270',   # Road to Cashel (Charlie Lennon 추정)
    'https://thesession.org/tunes/112',    # Trip to Pakistan (Tommy Peoples †2018)
    'https://thesession.org/tunes/192',    # Tommy Peoples' (†2018)
    'https://thesession.org/tunes/1100',   # Tommy Peoples' (†2018)
    'https://thesession.org/tunes/1323',   # Tommy Peoples' (†2018)
    'https://thesession.org/tunes/451',    # Brendan Tonra's (†2013)
    'https://thesession.org/tunes/2716',   # Carmel Mahoney Mulhaire (Mulhaire †2017)
    'https://thesession.org/tunes/2115',   # Charlie Lennon's (생존)
    'https://thesession.org/tunes/5248',   # Charlie Lennon's Scottish Concerto
    'https://thesession.org/tunes/12406',  # Maurice Lennon's Tribute (생존)
    'https://thesession.org/tunes/8668',   # Finbarr Dwyer's (†2014)
    'https://thesession.org/tunes/5623',   # Finbarr Dwyer's (†2014)
    'https://thesession.org/tunes/3330',   # Finbarr Dwyer's (†2014)
    'https://thesession.org/tunes/8258',   # Finbarr Dwyer's (†2014)
    # ── pdmx2: 'Traditional' 오표기로 통과한 현대곡 ─────────────
    'https://musescore.com/score/4880956',  # Theme Song from Titanic (Horner 추정)
    'https://musescore.com/score/5028778',  # MacAllister's Dirk (현대 파이프곡 추정)
    # ── archive(3권): 악보가 아닌 자료 (논문·사전·도록 등) ───────
    'https://archive.org/details/exileidentityart00vera',
    'https://archive.org/details/arxiv-0903.3905',
    'https://archive.org/details/arxiv-1502.01586',
    'https://archive.org/details/arxiv-1605.09387',
    'https://archive.org/details/arxiv-1502.01587',
    'https://archive.org/details/mustafayasinbascetin2019klasikserhlerinmetodolojisimethodologyofclassicalcommentarytexts_202001',
    'https://archive.org/details/pubmed-PMC3560109',
    'https://archive.org/details/pronouncingdicti00claruoft',
    'https://archive.org/details/cihm_00666',
    'https://archive.org/details/catalogueofkohle00kohlrich',
    'https://archive.org/details/arxiv-1508.04267',
    'https://archive.org/details/arxiv-1605.02564',
    'https://archive.org/details/arxiv-1701.08258',
    'https://archive.org/details/methodologyforco6811bran',
    'https://archive.org/details/jstor-737943',
    # ── 2026-07-31 전수조사 확정분 (실물 PDF·제목 확인) ──────
    'https://musescore.com/score/5834139',  # Youngblood / 5 Seconds of Summer (2018)
    'https://musescore.com/score/5912945',  # Mission: Impossible / Lalo Schifrin (1966)
    'https://musescore.com/score/5921558',  # Mission: Impossible arr. C. Sweedy
    'https://musescore.com/score/5888245',  # Simone / Frank Foster (†2011)
    'https://musescore.com/score/5893332',  # Philip Wesley (생존, 본인 판매 중)
    'https://musescore.com/score/5838347',  # Mohabbatein (2000) 영화 테마
    'https://musescore.com/score/5769215',  # Victoria Booth-Clipborn Demarest (†1982)
    'https://musescore.com/score/5909165',  # Keith Jarrett 채보 (생존)
    'https://musescore.com/score/5650234',  # Banana Boat Song / Irving Burgie (†2019)
    'https://musescore.com/score/5962531',  # Oh Noel / Piffer·Weekes (생존)
    'https://musescore.com/score/5707163',  # Fantaisie-impromptu arr. Jacob Koller (생존)
    'https://musescore.com/score/5420495',  # Himno de la Alegría / Miguel Ríos (생존)
    'https://musescore.com/score/6049167',  # waste / Kurstin·Foster
    'https://musescore.com/score/4574648',  # How Great Thou Art — Hine 영어 가사
    # 정책성(기존 '거부감 우려' 기준과 통일) — 저작권과 별개
    'https://musescore.com/score/5881036',  # Funkerlied (국방군 군가)
    'https://musescore.com/score/5866544',  # Mi General, Augusto Pinochet
    'https://musescore.com/score/5946346',  # Die Wacht am Rhein
    # ── PDF 본문에서 편곡자·채보자가 확인된 곡 (2차적저작물 권리) ──
    'https://musescore.com/score/5578965',  # To A Wild Rose arranged for Violin Sol / arr. Matthew TATEOSSIAN
    'https://musescore.com/score/6290624',  # 24 Caprices for Solo Violin Op.1 / Niccolo Paganini arr. Brandon Andr
    'https://musescore.com/score/5911887',  # 3 Gymnopédies / (Arranged by dddiam)
    'https://musescore.com/score/5752228',  # I saw my lady weepe / James Gibb editions
    'https://musescore.com/score/5488033',  # L Arlesienne Suite No 1 Violin I / Arr: Hilary Day 2/20/2019
    'https://musescore.com/score/5764368',  # When others sings Venite exultemus (Th / James Gibb editions
    'https://musescore.com/score/5992590',  # Chanson de l'Oignon / arr. Ben Neithardt
    'https://musescore.com/score/5790470',  # Old Folks At Home / This edition produced by Andrew Si
    'https://musescore.com/score/5790350',  # i saw three ships / This edition  Andrew Sims 2014
    'https://musescore.com/score/5924039',  # Violin Sonata in D minor Op.5 No.12 'L / Simplified Arrangement
    'https://musescore.com/score/5468765',  # Brahms: Nachtwandler Op. 86 Nº 3 / Arr. Max Laurischkus
    'https://musescore.com/score/5757900',  # I know not if or dark or bright / James Gibb editions
    'https://musescore.com/score/5861792',  # Canon and Gigue in D major P.37 / Arr.Eliaz Bobadilla(Flute Cool)
    'https://musescore.com/score/5757543',  # Alma redemptoris Mater / James Gibb editions
    'https://musescore.com/score/4811958',  # Swan Lake (ballet) Op.20 / arr. by Jacob Solis
    'https://musescore.com/score/5785683',  # What Child is this? / This edition  Andrew Sims 2014
    'https://musescore.com/score/5484201',  # Le nozze di Figaro K.492 / arr. Anton Bernhard Furstenau
    'https://musescore.com/score/5895364',  # jim jones at botany bay / Nyoongar Song (transcribed 1852 by
    'https://musescore.com/score/5788844',  # Unto us is born a Son / This edition  Andrew Sims 2014
    'https://musescore.com/score/5410325',  # 2 Sonatinas for Piano Anh.5 / Arrangement für zwei Violinen
    'https://musescore.com/score/5750479',  # flow my tears / James Gibb editions
    'https://musescore.com/score/6367611',  # Violin Sonata in C major K.14 / arr. Rampal / Veyron-Lacroix
    'https://musescore.com/score/5581291',  # Violinkonzert_Nr._4_A minor / Niccolo Paganini (Transcripted to 
    'https://musescore.com/score/5216102',  # The Washington Post March / Arranged by Andrew Balent
    'https://musescore.com/score/5788795',  # Macht hoch die Tür die Tor macht weit / Harmony: arr. A.S.
    'https://musescore.com/score/2577231',  # Violin Concerto in D major Op.61 / transcribed for violin and piano a
    'https://musescore.com/score/165019',  # String Quintet K.Anh.83/592b / 
    'https://musescore.com/score/1156641',  # Canonic Sonata Number One / transcribed for B♭ clarinet
    'https://musescore.com/score/86309',  # Concerto in D Allegro (2) / Arr. & Cadenza by Michel Rondeau
    'https://musescore.com/score/6269453',  # Jesu der du meine Seele BWV 78 / arr. André Papillon
    'https://musescore.com/score/5873890',  # god rest ye merry gentlemen / Arranged by: David Archuleta and C
    'https://musescore.com/score/5927365',  # molly malone / arr. Florian Brambock
    'https://musescore.com/score/6212249',  # 14 Romances Op.34 / arrangiamento per flauto  Vasco Ma
    'https://musescore.com/score/6371663',  # Manucript Wandembrile 84 / Transcription n°80 du Manuscrit Wa
    'https://musescore.com/score/203281',  # Mélancolie per Flauto / Cesar Franck (arr. Valentino Minut
    'https://musescore.com/score/5766979',  # Then sit thee downe&amp; say thy Nunc  / James Gibb editions
    'https://musescore.com/score/5789299',  # Here We Come A-Wassailing / This edition  Andrew Sims 2014
    'https://musescore.com/score/6280206',  # Herr Jesu Christ du höchstes Gut BWV 1 / arr. André Papillon
    'https://musescore.com/score/5746441',  # An die Musik D.547 / James Gibb editions
    'https://musescore.com/score/5872132',  # Morrison's jig / Arranged by Ollie Stevens
    'https://musescore.com/score/6265878',  # Preise Jerusalem den Herren BWV 119 / arr. André Papillon
    'https://musescore.com/score/167419',  # the irish washerwoman / 
    'https://musescore.com/score/5792453',  # Illumina oculos meos / James Gibb editions
    'https://musescore.com/score/5783808',  # The first Nowell / arr. John Stainer
    'https://musescore.com/score/4852365',  # The Nutcracker (ballet) Op.71 / arranged by Aaron Gascon
    'https://musescore.com/score/5874724',  # the first noel / Arr. Jason Garrison
    'https://musescore.com/score/5790378',  # O Jesulein süß o Jesulein mild BWV 493 / arr. J.S. Bach
    'https://musescore.com/score/5790446',  # Cranham / This edition  Andrew Sims 2014
    'https://musescore.com/score/4880134',  # Salut d'amour Op.12 / Composed by Eward Elgar, Arranged 
    'https://musescore.com/score/32273',  # Folk Medley for Clarinets / 
    'https://musescore.com/score/4063251',  # Clarinet Concerto K.622 / (Solo Transcribed for Flute)
    'https://musescore.com/score/4889687',  # The House of the Rising Sun / Arranged by: Ryan Davenport
    'https://musescore.com/score/5771237',  # Gabriel's Message (51324) / This edition  Andrew Sims 2014
    'https://musescore.com/score/3571656',  # Canon and Gigue in D major P.37 / Transcriber: yyaname
    'https://musescore.com/score/6285767',  # Schweigt stille plaudert nicht BWV 211 / arr. André Papillon
    'https://musescore.com/score/5750692',  # Vide Domine / James Gibb editions
    'https://musescore.com/score/5764469',  # Tua Jesu dilectio / James Gibb editions
    'https://musescore.com/score/6272513',  # Gott der Herr ist Sonn und Schild BWV  / arr. André Papillon
    'https://musescore.com/score/5909670',  # Azeri Folk Music / Azari Trad. Arr. Lennard Farwick
    'https://musescore.com/score/5785364',  # While Shepherds Watched Their Flocks / This edition  Andrew Sims 2014
    'https://musescore.com/score/5999394',  # Piano Sonata No.14 Op.27 No.2 / Ludwig van Beethoven (arr. Charley
    'https://musescore.com/score/126815',  # a la nanita nana / Ritmo Chocoano 2013, Transposed an
    'https://musescore.com/score/5746456',  # Of one that is so fair and bright / This edition  Andrew Sims 2016
    'https://musescore.com/score/3475681',  # Piano Sonata No.24 Op.78 / Arranged for clarinet and piano by
    'https://musescore.com/score/5926589',  # Brillante Phantaisie / Arban, arr. Dennis Geurts
    'https://musescore.com/score/5747423',  # Symphony No.9 Op.95 / Arr. by Jacob Dellinger
    'https://musescore.com/score/6308738',  # Mer hahn en neue Oberkeet BWV 212 / arr. André Papillon
    'https://musescore.com/score/554151',  # christmas medley / Arranged
    'https://musescore.com/score/4619976',  # Piano Sonata No.14 Op.27 No.2 / Arranged by Hayley & Sachiko
    'https://musescore.com/score/6288369',  # Süsser Trost mein Jesus kömmt BWV 151 / arr. André Papillon
    'https://musescore.com/score/6291560',  # Was Gott tut das ist wohlgetan BWV 99 / arr. André Papillon
    'https://musescore.com/score/5862513',  # orchestral suite no 2 in b minor bwv 1 / Arr. by Philip R.M.
    'https://musescore.com/score/5976504',  # Lute Suite in E minor BWV 996 / arr. Mark Bücker
    'https://musescore.com/score/6149240',  # Maler for folkemusikk / Arr:
    'https://musescore.com/score/5785237',  # Tenebrae factae sunt / James Gibb editions
    'https://musescore.com/score/5436903',  # Greensleeves / Arranged by Pierre-Antoine Roby
    'https://musescore.com/score/2875806',  # Sonata for Bassoon and Cello in B-flat / arr. Jeff Slade
    'https://musescore.com/score/5923120',  # Don Carlo / arr:Allan James
    'https://musescore.com/score/471871',  # Rigadoon in C major Z.653 / 
    'https://musescore.com/score/5939783',  # La fille aux cheveux de lin / Arrangé par Olivér Nagy
    'https://musescore.com/score/108610',  # Ave Maria D.839 / semplificata e arrangiata per sax 
    'https://musescore.com/score/5290059',  # Ave Maria / Arrangement by Jaime A. Sánchez
    'https://musescore.com/score/5782875',  # Hark the Herald Angels Sing / This edition  Andrew Sims 2014
    'https://musescore.com/score/4818780',  # Air 'on the G string' Orchestral Suite / Arranged by Banuwarsa
    'https://musescore.com/score/5813678',  # Jeg Ser Deg Sote Lam - for Flute and P / arr. Susanna Lundeng
    'https://musescore.com/score/5857214',  # Hocus Pocus / Transcribed by Paul Wagner
    'https://musescore.com/score/2838536',  # Scarborough Faire with variations / Traditional - arr: M Graham
    'https://musescore.com/score/5901821',  # Air 'on the G string' Orchestral Suite / arr. Ruth Bearden
    'https://musescore.com/score/6270178',  # Liebster Gott wenn werd ich sterben? B / arr. André Papillon
    'https://musescore.com/score/5789386',  # Angels from the realms of glory / This edition  Andrew Sims 2014
    'https://musescore.com/score/4920576',  # 12 Horn Duos K.487/496a / Arranged by Watson Forbes
    'https://musescore.com/score/5789821',  # Alla Trinita Beata / This edition  Andrew Sims 2014
    'https://musescore.com/score/5913255',  # Cabar Feidh / arranged by Allan Ferguson
    'https://musescore.com/score/4862281',  # the first noel / Arr. Jason Garrison
    'https://musescore.com/score/152011',  # Cello Concerto Op.85 / Arr. thefoilist
    'https://musescore.com/score/1955181',  # The Thunderer / Arr. for Bb Cornet by Benned Hedeg
    'https://musescore.com/score/5193656',  # The Children of Haimon / Arranged from Quadrille
    'https://musescore.com/score/5743952',  # God save the king / This edition produced by Andrew Si
    'https://musescore.com/score/5968074',  # locomotion / Transcribed by Paul Wagner
    'https://musescore.com/score/5786207',  # In monte Oliveti / James Gibb editions
    'https://musescore.com/score/5949119',  # Piano Sonata No.20 Op.49 No.2 / arr. for Alto Saxophone Duet by Ca
    'https://musescore.com/score/5845011',  # Carmen / Arranged by RICHARD SAUCEDO
    'https://musescore.com/score/2838491',  # House of the Rising Sun / Traditional - arr M Graham
    'https://musescore.com/score/5789359',  # Good Christian men rejoice / This edition  Andrew Sims 2014
    'https://musescore.com/score/6274529',  # Was frag ich nach der Welt BWV 94 / arr. André Papillon
    'https://musescore.com/score/5752800',  # Slav'sya / This edition  Andrew Sims 2012
    'https://musescore.com/score/711261',  # bonny portmore / Irish traditional (Arr. Erik Malta
    'https://musescore.com/score/6367748',  # Violin Sonata No.9 Op.47 / Transcribed by alliebaster
    'https://musescore.com/score/5861011',  # Pas de Deux / (arr. T.Inaba)
    'https://musescore.com/score/5748631',  # Ständchen D.889 / James Gibb editions
    'https://musescore.com/score/6008001',  # Piano Sonata No.18 Op.31 No.3 / Arr. Berkheimer
    'https://musescore.com/score/6267196',  # Brich dem Hungrigen dein Brot BWV 39 / arr. André Papillon
    'https://musescore.com/score/5661986',  # Murka / Murka. Author unknown, ca. 1920. A
    'https://musescore.com/score/5450727',  # Children's Album Op.39 / Arrangement for two violins by A. 
}
# ── 규칙 기반 차단 — 2026-07-31 전수조사 결과 ────────────────────
# URL 열거는 수집기가 새로 담아오는 곡을 막지 못한다. 아래는 패턴으로
# 막아 재수집·재병합에도 계속 걸러지게 한 규칙들.

# ⓵ archive: 악보가 아닌 자료(논문·초록·도록). 저자란에 클래식 작곡가
#    이름이 자동으로 붙어 '저작자 아닌 자를 저작자로 표시'까지 된다.
NON_SCORE_ID = re.compile(
    r'(?i)/details/(arxiv-|pubmed-|PMC\d|jstor-|cihm_|osti|'
    r'nasa|ERIC_|DTIC|bub_gb_)')

# ⓶ thesession: 작곡가가 특정되는 튠은 전통곡이 아니다.
#    The Session 은 composer 필드를 따로 제공하므로, 그 값이 있는 튠은
#    현대 창작곡으로 보고 제외한다(생존 작곡가 다수 확인).
#    tune_id 목록은 조사 산출물에서 가져온다.
def _load_session_block():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'blocked_session_tunes.txt')
    if not os.path.exists(p):
        return set()
    out = set()
    for line in open(p, encoding='utf-8'):
        line = line.split('#')[0].strip()
        if line:
            out.add(f'https://thesession.org/tunes/{line}')
    return out

SESSION_BLOCKED = _load_session_block()

# ⓷ 편곡자·채보자가 명시된 곡 — 편곡물은 2차적저작물이라 원곡이 PD여도
#    편곡자의 권리가 따로 산다. 업로더의 CC0 선언은 자기 편곡 층위만
#    커버할 뿐 원곡 이용허락을 대신하지 못한다.
ARRANGER = re.compile(
    r'(?i)\b(arr\.|arrang|transcrib|transcription by|realization by|'
    r'harmon(y|ized) by|adapted by|edited by)\b')

# ⓸ 작곡가란이 사람 이름이 아니라 계정명·설명문인 경우 — 출처 불명이라
#    권리 상태를 확인할 길이 없다(현대 창작곡이 이 경로로 들어왔다).
BAD_COMPOSER = re.compile(
    r'(?i)^(dont know|unknown artist|me\b|myself|anonymous user|'
    r'various|n/?a|none|test|asdf)$')

# ⓹ 사후 70년 미경과가 확인된 작곡가 (2026년 기준 1955년 이전 사망만 PD)
BLOCKED_COMPOSERS = {
    'andré popp', 'andre popp',                    # †2014
    'victoria booth-clipborn demarest',            # †1982
    'gayle kowalchyk',                             # 생존
    'dekkadeci',                                   # 생존(필명)
    'wesley steenbergen',                          # 생존
    'paul ernst ruppel',                           # †2006
    'harry d. clarke',                             # †1957
    'cyprien katsaris',                            # 생존
    'anna cramer',                                 # †1968
    'roy turk & russell robinson',                 # †1963/1966
    'billy rose',                                  # †1966
    'philip wesley',                               # 생존
    'lalo schifrin',                               # †2025
    'keith jarrett',                               # 생존
    'irving burgie',                               # †2019
    'jacob koller',                                # 생존
    'miguel ríos', 'miguel rios',                  # 생존
}

# 이름이 곧 작곡가인 현대 곡 무더기 — Paddy Fahey(†2019)의 무제 곡들은
# 전부 "Paddy Fahey's"로 불린다. URL을 나열하는 대신 제목으로 잡는다.
BLOCKED_TITLE = re.compile(r"(?i)^paddy fahey'?s?$")


# ⓺ PDMX 수집분은 '작곡가가 PD 명단에 있는 곡'만 남긴다.
#    차단 목록이 아니라 허용 목록이다 — 이름을 나열해 빼는 방식은
#    새 이름이 들어올 때마다 샌다.
#
#    특히 'Traditional'·'Anonymous' 표기만으로는 통과시키지 않는다.
#    그 값은 업로더가 직접 적은 것이라 검증된 사실이 아니고, 2026-07
#    점검에서 이 경로로 들어온 곡에서 실제 침해가 확인됐다
#    (전통곡 표기 아래 현대 편곡·팝 편곡이 섞여 있었다).
#
#    판정 기준은 수집기와 같은 파일(pd_match.py)을 쓴다 —
#    수집기만 고치고 정리 스크립트를 안 고치면 다시 어긋난다.
from pd_match import is_pd_composer  # noqa: E402

# 작곡가가 PD 명단에 있어야만 남기는 소스 — 수집기와 같은 기준을
# 정리 쪽에서도 강제한다(수집기만 고치면 어긋난다).
# 이 소스들은 업로더·기여자가 메타데이터를 직접 적는 곳이라
# 표기만 믿을 수 없다. Mutopia·OpenScore 처럼 편집진이 통제하는
# 소스는 여기 넣지 않는다.
STRICT_PD_SOURCES = {'pdmx', 'pdmx2', 'cpdl', 'imslp'}
PDMX_SOURCES = STRICT_PD_SOURCES   # 옛 이름 (다른 스크립트가 참조)


# ⓻ 교본(archive) 중 작곡가 표기를 원본 메타데이터로 확인하지 못한 곡.
#    수집기가 "Czerny" 로 검색해 나온 결과에 그 이름을 작곡가로 붙여,
#    그 사람이 편집만 한 남의 작품에도 이름이 달렸다(체르니 교정판
#    평균율 등). 목록은 free-sheets-3/verify_archive_meta.py 가 만든다.
def _load_archive_block():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'blocked_archive.txt')
    if not os.path.exists(p):
        return set()
    return {ln.strip() for ln in open(p, encoding='utf-8')
            if ln.strip() and not ln.startswith('#')}


ARCHIVE_BLOCKED = _load_archive_block()


# ⓼ Open Hymnal 중 제한 라이선스 곡 — ABC 원문에 "All other rights
#    reserved"(예배용 한정)가 명시된 저작물. 'Public Domain' 표기는
#    배포 zip 전체에 대한 가정이었고 곡별 검사에서 뒤집혔다.
def _load_hymnal_block():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'blocked_openhymnal.txt')
    if not os.path.exists(p):
        return set()
    return {ln.split('\t')[0].strip() for ln in open(p, encoding='utf-8')
            if ln.strip() and not ln.startswith('#')}


HYMNAL_BLOCKED = _load_hymnal_block()


# 4) 2026-08 전수 감사 차단 — 현대곡·매시업·현대 편곡, Traditional 오표기,
#    비악보 자료, 미국 미발효(1930년 이후 발행) 등. blocked_audit.txt 관리.
def _load_audit_block():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'blocked_audit.txt')
    if not os.path.exists(p):
        return set()
    return {ln.split('\t')[0].strip() for ln in open(p, encoding='utf-8')
            if ln.strip() and not ln.startswith('#')}


AUDIT_BLOCKED = _load_audit_block()

# 같은 이름의 다른 곡이 흔한 소스 — 제목 기준 중복 제거에서 제외.
DUP_EXEMPT = {'thesession'}

# 첫 화면 노출 우선순위 (작을수록 앞). 알려진 클래식·교재를 앞에,
# 무명 민속곡을 뒤로.
SOURCE_ORDER = {
    'mutopia': 0,             # 정전 클래식 (큐레이션)
    'openscore_lieder': 1,    # 가곡 정전
    'openscore_quartets': 2,  # 실내악 정전
    'archive': 3,             # 교재·교본
    'cpdl': 4,                # 합창 정전 (라이선스 명시 소스)
    'imslp': 5,               # 원판 스캔 (파일별 PD 표기 확인)
    'pdmx': 6,                # 인기 편곡
    'pdmx2': 7,
    'openhymnal': 8,          # 찬송가
    'thesession': 9,          # 민속곡 — 맨 뒤
}


def title_from_file(path):
    """파일명에서 사람이 읽을 제목을 만든다.

    'raw/mutopia/piano/Rumores_de_la-caleta-a4.pdf' → 'Rumores de la Caleta'
    """
    stem = os.path.splitext(os.path.basename(path or ''))[0]
    # 판형·편집 접미사 제거 (-a4, -let, -a4-2 등)
    stem = re.sub(r'-(a4|let|letter)(-\d+)?$', '', stem, flags=re.I)
    stem = re.sub(r'[_-]+', ' ', stem).strip()
    if not stem:
        return ''
    # 전부 소문자면 단어 첫 글자만 대문자로 (이미 대소문자가 섞였으면 존중)
    if stem == stem.lower():
        stem = ' '.join(w[:1].upper() + w[1:] for w in stem.split())
    return stem


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


def main():
    data = json.load(open(CATALOG, encoding='utf-8'))
    before = len(data)
    stat = {'제목복구': 0, '깨짐제외': 0, '작곡가비움': 0, '중복제거': 0}

    out = []
    for e in data:
        title = (e.get('title') or '').strip()

        # ⓪ 저작권·품질 차단 — URL 목록 + 규칙(재수집 대비)
        url = e.get('source_url') or ''
        comp = (e.get('composer') or '').strip()
        blob = f'{title} {comp}'
        why = None
        if url in BLOCKED_URLS:
            why = '차단목록'
        elif BLOCKED_TITLE.match(title):
            why = '차단제목'
        elif url in SESSION_BLOCKED:
            why = 'session작곡가'
        elif NON_SCORE_ID.search(url):
            why = '비악보'
        elif ARRANGER.search(blob):
            why = '편곡자권리'
        elif BAD_COMPOSER.match(comp):
            why = '작곡가불명'
        elif comp.lower() in BLOCKED_COMPOSERS:
            why = '보호기간중'
        elif (e.get('source') in STRICT_PD_SOURCES
              and not is_pd_composer(comp, '')):
            why = 'PD판정실패'
        elif url in ARCHIVE_BLOCKED:
            why = '교본표기미확인'
        elif (e.get('file') or '') in HYMNAL_BLOCKED:
            why = '찬송가제한라이선스'
        elif (e.get('file') or '') in AUDIT_BLOCKED:
            why = '감사차단'
        if why:
            stat[why] = stat.get(why, 0) + 1
            continue

        # ① 제목 복구
        if not title:
            title = title_from_file(e.get('file'))
            if title:
                e['title'] = title
                stat['제목복구'] += 1
            else:
                continue  # 제목을 못 만들면 목록에 못 쓴다

        # ② 깨진 인코딩
        if is_broken(title):
            stat['깨짐제외'] += 1
            continue
        if is_broken(e.get('composer')):
            e['composer'] = ''
            stat['작곡가비움'] += 1

        # ②-1 작곡가 표기 정규화 (normalize_composers.py) —
        #     중복 제거 전에 해야 표기만 다른 같은 곡이 합쳐진다.
        nc = normalize_composer(e.get('composer', ''))
        if nc != e.get('composer', ''):
            e['composer'] = nc
            stat['작곡가정규화'] = stat.get('작곡가정규화', 0) + 1

        # ②-2 정규화·비움 뒤의 값으로 저작권 규칙 재평가.
        #     ⓪의 첫 평가는 원본 문자열을 본다 — 'X arr. Y'가 정규화로
        #     'X'가 되거나 깨진 표기가 비워지면, 첫 평가를 통과한 곡이
        #     검사 스크립트(check_catalog)에서는 걸려 정리와 검사가
        #     어긋난다. 최종 값으로 한 번 더 거른다.
        comp2 = (e.get('composer') or '').strip()
        why2 = None
        if BAD_COMPOSER.match(comp2):
            why2 = '작곡가불명'
        elif comp2.lower() in BLOCKED_COMPOSERS:
            why2 = '보호기간중'
        elif (e.get('source') in STRICT_PD_SOURCES
              and not is_pd_composer(comp2, '')):
            why2 = 'PD판정실패'
        if why2:
            stat[why2] = stat.get(why2, 0) + 1
            continue

        out.append(e)

    # ③ 같은 작품 중복 제거 (민속곡 제외).
    #    미디·썸네일이 있는 쪽을 남겨 미리듣기 품질을 지킨다.
    def richness(e):
        return (1 if e.get('midi') else 0) + (1 if e.get('thumb') else 0)

    best = {}
    order = []
    passthru = []
    for e in out:
        if (e.get('source') or '') in DUP_EXEMPT:
            passthru.append(e)
            continue
        key = (norm(e.get('title')), norm(e.get('composer')),
               e.get('instrument') or '')
        if key not in best:
            best[key] = e
            order.append(key)
        else:
            stat['중복제거'] += 1
            if richness(e) > richness(best[key]):
                best[key] = e
    deduped = [best[k] for k in order] + passthru

    # ④ 재배열 (안정 정렬 — 같은 순위 안에서는 기존 순서 유지).
    #    소스 우선순위 → 작곡가가 적힌 곡 먼저.
    #    파일명에서 복구한 제목('Bluemtns' 같은 축약형)은 작곡가가 없어
    #    자연히 뒤로 밀린다. 첫 화면에 알아볼 수 있는 곡이 오게 하는 목적.
    deduped.sort(key=lambda e: (SOURCE_ORDER.get(e.get('source'), 7),
                                0 if (e.get('composer') or '').strip() else 1))

    json.dump(deduped, open(CATALOG, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'정리: {before} → {len(deduped)}곡', flush=True)
    for k, v in stat.items():
        print(f'  {k}: {v}', flush=True)


if __name__ == '__main__':
    main()
