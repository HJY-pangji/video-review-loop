"""예시 대본. 이 파일을 복사해 편마다 하나씩 만든다 (episodes/ep1.py 등).

쓰는 법 (저장소 루트에서)
  python episodes/example.py check          자막 규칙 검사 + 총 길이 (원본 영상 없이도 동작)
  python episodes/example.py timeline       장면 번호와 완성본 시각 표
  python episodes/example.py at 0:12        그 시각이 몇 번 장면인지 (리뷰 메모를 반영할 때)
  python episodes/example.py check gain     목소리 장면의 음량 보정값까지 (원본 필요)
  python episodes/example.py all            전체 렌더링 → 이어 붙이기 → 소리 마무리
  python episodes/example.py 2 join         2번 장면만 다시 만들고 전체 다시 합치기
  python episodes/example.py audio          소리만 다시 섞기
  ... publish                               끝에 붙이면 완성본을 리뷰 폴더의 컨펌본으로 복사

버전을 올릴 때는 VERSION만 바꾼다. 장면 키 설명은 reviewloop/engine.py 맨 위에 있다.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reviewloop.engine import Episode
from reviewloop.paths import find

VERSION = 'v1'


def clip(key):
    """파일 이름 조각으로 원본을 찾는다. 아직 원본이 없어도 check / timeline / at 은 쓸 수 있게 한다."""
    try: return find(key)
    except FileNotFoundError: return key


# 원본 영상: config.json의 sources 폴더에서 파일 이름 조각으로 찾는다
ARRIVE = clip('20240501_1030')
TALK = clip('20240501_1105')
VIEW = clip('20240501_1420')

C1 = 'DAY 1  도착'

S = [
    # 콜드 오픈: 가장 궁금한 장면을 실제 목소리로. (글, 시작, 끝) 튜플은 말소리에 맞춘 자막
    dict(src=TALK, ss=12.0, dur=6.0, mode='voice', music='off', badge='여행 첫날',
         caps=[('여기가 어디냐면요', 0.4, 2.4), ('저도 잘 모르겠습니다', 2.6, 5.0)]),
    dict(card=('어쩌다 여기까지 왔냐면', '하루 전'), dur=2.8, music='off'),
    # 타이틀: 이 장면부터 음악 시작 (assets/music/main.wav)
    dict(src=VIEW, ss=3.0, dur=4.4, mode='noise', music='main', fadein=True, title=('여행 EP.1', '예시 편'), caps=[]),
    # 말이 없는 장면: 문자열 자막은 길이에 맞춰 자동 배치된다
    dict(src=ARRIVE, ss=0, dur=8.0, mode='amb', badge=C1, caps=['공항에 도착했습니다', '(짐 담당은 접니다)']),
    dict(src=TALK, ss=30.0, dur=9.0, mode='voice', dnmix=1.0, badge=C1,
         caps=[('커피 한 잔에 얼마지?', 0.5, 2.6), ('(물가 계산 중입니다)', 4.0, 7.0)]),
    dict(src=VIEW, ss=20.0, dur=7.0, mode='mute', badge=C1, fadeout=True, caps=['바다 색이 말이 안 됩니다']),
    dict(endcard=('다음 편', '둘째 날'), dur=4.5),
]

if __name__ == '__main__':
    Episode('example', VERSION, S, chapters=(C1,), handle='채널명 @example').main()
