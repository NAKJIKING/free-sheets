#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""찬송가 한국어 별칭 주입 — 카탈로그의 openhymnal 곡 제목을 한국
찬송가 제목과 매칭해 alias 필드를 채운다. 앱 검색이 한국어 제목으로도
찾을 수 있게 된다. (별칭은 사실 정보 매핑 — 저작권 무관)
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, 'catalog.json')

# 영문 제목(정규화 키) → 한국 찬송가 제목. 확실한 것만 수록.
ALIASES = {
    'AMAZING GRACE': '나 같은 죄인 살리신',
    'HOLY HOLY HOLY': '거룩 거룩 거룩 전능하신 주님',
    'WHAT A FRIEND WE HAVE IN JESUS': '죄짐 맡은 우리 구주',
    'NEARER MY GOD TO THEE': '내 주를 가까이 하게 함은',
    'IT IS WELL WITH MY SOUL': '내 평생에 가는 길',
    'BLESSED ASSURANCE': '예수로 나의 구주 삼고',
    'ROCK OF AGES': '만세 반석 열리니',
    'ABIDE WITH ME': '때 저물어서 날이 어두니',
    'SILENT NIGHT': '고요한 밤 거룩한 밤',
    'JOY TO THE WORLD': '기쁘다 구주 오셨네',
    'O COME ALL YE FAITHFUL': '참 반가운 성도여',
    'HARK THE HERALD ANGELS SING': '천사 찬송하기를',
    'AWAY IN A MANGER': '그 어린 주 예수',
    'THE FIRST NOEL': '저 들 밖에 한밤중에',
    'FIRST NOWELL': '저 들 밖에 한밤중에',
    'COME THOU FOUNT': '복의 근원 강림하사',
    'BE THOU MY VISION': '내 맘의 주여 소망 되소서',
    'ALL HAIL THE POWER': '주 예수 이름 높이어',
    'ONWARD CHRISTIAN SOLDIERS': '믿는 사람들은 군병 같으니',
    'STAND UP STAND UP FOR JESUS': '십자가 군병들아',
    'WHEN I SURVEY THE WONDROUS CROSS': '주 달려 죽은 십자가',
    'JESUS LOVES ME': '예수 사랑하심을',
    'JUST AS I AM': '큰 죄에 빠진 나를',
    'SWEET HOUR OF PRAYER': '기도하는 이 시간',
    'I NEED THEE EVERY HOUR': '주 음성 외에는',
    'NOTHING BUT THE BLOOD': '나의 죄를 씻기는',
    'ALAS AND DID MY SAVIOR BLEED': '웬 말인가 날 위하여',
    'O FOR A THOUSAND TONGUES': '만 입이 내게 있으면',
    'A MIGHTY FORTRESS': '내 주는 강한 성이요',
    'PRAISE GOD FROM WHOM ALL BLESSINGS FLOW': '만복의 근원 하나님',
    'DOXOLOGY': '만복의 근원 하나님',
    'SAVIOR LIKE A SHEPHERD LEAD US': '선한 목자 되신 우리 주',
    'THIS IS MY FATHERS WORLD': '참 아름다워라',
    'ALL CREATURES OF OUR GOD AND KING': '온 천하 만물 우러러',
    'CROWN HIM WITH MANY CROWNS': '면류관 가지고',
    'OLD RUGGED CROSS': '갈보리산 위에',
    'STANDING ON THE PROMISES': '주의 약속하신 말씀 위에서',
    'TRUST AND OBEY': '예수 따라가며',
    'BRINGING IN THE SHEAVES': '새벽부터 우리',
    'TAKE MY LIFE AND LET IT BE': '내 생명 드리니',
    'I SURRENDER ALL': '내게 있는 모든 것을',
    'HIGHER GROUND': '저 높은 곳을 향하여',
    'ALL THE WAY MY SAVIOR LEADS ME': '나의 갈 길 다 가도록',
    'JESUS LOVER OF MY SOUL': '비바람이 칠 때와',
    'I GAVE MY LIFE FOR THEE': '내 너를 위하여',
    'GOD BE WITH YOU TILL WE MEET': '다시 만날 때까지',
    'NOW THANK WE ALL OUR GOD': '다 감사드리세',
    'PRAISE TO THE LORD THE ALMIGHTY': '다 찬양하여라',
    'ANGELS WE HAVE HEARD ON HIGH': '천사들의 노래가',
    'O LITTLE TOWN OF BETHLEHEM': '오 베들레헴 작은 골',
    'WHAT CHILD IS THIS': '그 맑고 환한 밤중에',
    'CHRIST THE LORD IS RISEN TODAY': '예수 부활했으니',
    'LOW IN THE GRAVE HE LAY': '무덤에 머물러',
    'IN THE SWEET BY AND BY': '해보다 더 밝은 저 천국',
    'WHEN THE ROLL IS CALLED UP YONDER': '하나님의 나팔 소리',
    'THERE IS A FOUNTAIN': '샘물과 같은 보혈은',
    'BATTLE HYMN OF THE REPUBLIC': '마귀들과 싸울지라',
    'MINE EYES HAVE SEEN THE GLORY': '마귀들과 싸울지라',
    'COUNT YOUR BLESSINGS': '받은 복을 세어 보아라',
    'GREAT IS THY FAITHFULNESS': '오 신실하신 주',
    'O COME O COME EMMANUEL': '곷 오소서 임마누엘',
    'THERE IS POWER IN THE BLOOD': '죄에서 자유를 얻게 함은',
    'WOULD YOU BE FREE FROM THE BURDEN': '죄에서 자유를 얻게 함은',
    'WERE YOU THERE': '거기 너 있었는가',
    'MORE LOVE TO THEE': '내 구주 예수를 더욱 사랑',
}


def norm(t):
    t = re.sub(r'[^A-Za-z0-9 ]', ' ', t.upper())
    return re.sub(r'\s+', ' ', t).strip()


def main():
    with open(CATALOG, encoding='utf-8') as f:
        catalog = json.load(f)
    hit = 0
    for e in catalog:
        if e.get('source') != 'openhymnal' or e.get('alias'):
            continue
        nt = norm(e.get('title', ''))
        for k, v in ALIASES.items():
            if k in nt or (len(nt) > 10 and nt in k):
                e['alias'] = v
                hit += 1
                break
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)
    total = sum(1 for e in catalog if e.get('source') == 'openhymnal')
    print(f'찬송가 {total}곡 중 별칭 주입 {hit}곡', flush=True)


if __name__ == '__main__':
    main()
