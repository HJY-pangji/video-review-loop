"""경로 설정. 저장소 위치와 config.json만 보고 모든 경로를 정한다 (윈도우·맥·리눅스 공통).

- 원본 영상은 저장소 밖에 둔다. config.json의 "sources"에 폴더를 적는다.
- ffmpeg는 항상 저장소 루트에서 실행한다(cwd=ROOT). 잡음 제거 모델을 상대 경로로 넘기기 위해서다.
  윈도우에서 "C:\\..." 같은 경로를 ffmpeg 필터 문자열에 넣으면 콜론 때문에 깨진다.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEO_EXT = {'.mp4', '.mov', '.m4v'}

for _s in (sys.stdout, sys.stderr):            # 윈도우 콘솔(cp949)에서 한글·기호 출력 오류 방지
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass


def _cfg():
    for name in ('config.json', 'config.example.json'):
        p = ROOT / name
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
    return {}


CFG = _cfg()
SOURCES = [Path(p).expanduser() for p in CFG.get('sources', [])]
REVIEW = Path(CFG['review_dir']).expanduser() if CFG.get('review_dir') else None
WHISPER = Path(CFG.get('whisper_dir') or ROOT / 'models' / 'sherpa-onnx-whisper-turbo').expanduser()
FONTS = ROOT / 'assets' / 'fonts'
MUSIC = ROOT / 'assets' / 'music'
# ffmpeg 필터에 들어가는 경로: 반드시 상대 경로 + 슬래시
RNN = {'bd': 'models/rnnoise/bd.rnnn', 'cb': 'models/rnnoise/cb.rnnn'}
VAD = ROOT / 'models' / 'silero_vad.onnx'

_index = None


def all_videos():
    """sources 아래의 모든 영상 파일 (하위 폴더 포함)"""
    global _index
    if _index is None:
        _index = []
        for s in SOURCES:
            if s.is_dir():
                _index += sorted(p for p in s.rglob('*') if p.suffix.lower() in VIDEO_EXT and '_sheets' not in p.parts)
    return _index


def find(key):
    """파일 이름에 key가 들어간 원본을 찾는다. key는 파일 이름의 일부면 된다 (예: 촬영 시각 '20240501_1030')."""
    hits = [p for p in all_videos() if key.lower() in p.name.lower()]
    if not hits:
        raise FileNotFoundError(f'원본 영상을 찾지 못했습니다: "{key}"\n  config.json의 sources를 확인하세요: {[str(s) for s in SOURCES]}')
    return str(hits[0])


def out_dir(ep):
    d = ROOT / 'out' / ep
    d.mkdir(parents=True, exist_ok=True)
    return str(d) + '/'


def run(cmd, **kw):
    """ffmpeg/ffprobe 실행 (항상 저장소 루트에서)"""
    kw.setdefault('stdin', subprocess.DEVNULL)
    return subprocess.run(cmd, cwd=str(ROOT), **kw)
