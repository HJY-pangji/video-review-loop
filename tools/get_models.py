"""필요한 모델을 models/ 아래에 내려받는다. 한 번만 실행하면 된다.

  python tools/get_models.py            전부
  python tools/get_models.py denoise    잡음 제거 모델만 (렌더링에 필요)
  python tools/get_models.py asr        음성 인식 모델만 (받아쓰기에 필요, 약 540MB)

- 잡음 제거: RNNoise 모델 2개 (github.com/GregorR/rnnoise-models). git이 설치되어 있어야 한다.
- 음성 구간 검출: silero VAD, 음성 인식: whisper turbo (github.com/k2-fsa/sherpa-onnx 배포본)
"""
import shutil, subprocess, sys, tarfile, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / 'models'; M.mkdir(exist_ok=True)
REL = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/'
what = sys.argv[1] if len(sys.argv) > 1 else 'all'


def fetch(url, dst):
    print(f'내려받는 중: {dst.name}', flush=True)
    urllib.request.urlretrieve(url, dst, lambda b, bs, total: print(f'\r  {b*bs/1e6:6.0f} / {total/1e6:.0f} MB', end='', flush=True) if b % 200 == 0 else None)
    print()


if what in ('all', 'denoise'):
    rn = M / 'rnnoise'; rn.mkdir(exist_ok=True)
    if (rn / 'bd.rnnn').exists() and (rn / 'cb.rnnn').exists(): print('잡음 제거 모델: 이미 있음')
    else:
        with tempfile.TemporaryDirectory() as t:
            subprocess.run(['git', 'clone', '-q', '--depth', '1', 'https://github.com/GregorR/rnnoise-models', t + '/r'], check=True)
            shutil.copy2(t + '/r/beguiling-drafter-2018-08-30/bd.rnnn', rn / 'bd.rnnn')
            shutil.copy2(t + '/r/conjoined-burgers-2018-08-28/cb.rnnn', rn / 'cb.rnnn')
        print('잡음 제거 모델: 완료')

if what in ('all', 'asr'):
    if (M / 'silero_vad.onnx').exists(): print('음성 구간 검출 모델: 이미 있음')
    else: fetch(REL + 'silero_vad.onnx', M / 'silero_vad.onnx')
    dst = M / 'sherpa-onnx-whisper-turbo'
    if (dst / 'turbo-encoder.int8.onnx').exists(): print('음성 인식 모델: 이미 있음')
    else:
        tar = M / 'whisper-turbo.tar.bz2'; fetch(REL + 'sherpa-onnx-whisper-turbo.tar.bz2', tar)
        print('압축 푸는 중…', flush=True)
        with tarfile.open(tar, 'r:bz2') as t: t.extractall(M)
        tar.unlink(); print('음성 인식 모델: 완료')
