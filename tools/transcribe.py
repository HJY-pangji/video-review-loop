"""원본 영상의 말소리를 받아쓴다 (whisper turbo + 음성 구간 검출).

  python tools/transcribe.py 20240501_1030               파일 이름 조각으로 한 개
  python tools/transcribe.py 20240501 20240502           여러 개(조각이 들어간 파일 전부)
  python tools/transcribe.py --all                       sources의 모든 영상 (오래 걸림)
  python tools/transcribe.py 1030 --ss 30 --dur 20 --fine     구간만 촘촘하게 (자막 시각 맞출 때)

결과는 private/transcripts.json에 쌓인다 (지인 이름 등이 들어갈 수 있어 git에 올리지 않는다). AI 편집 도우미는 소리를 직접 듣지 못하므로 이 결과와 음량 측정이 판단 근거다.
주의: 소음 구간에서는 없는 말을 지어내기도 한다. 같은 구간을 두 번 이상 돌려 결과가 갈리면 자막에 쓰지 않는다.
먼저 python tools/get_models.py 로 모델을 받아야 한다.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from reviewloop.paths import ROOT, VAD, WHISPER, all_videos, run


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('keys', nargs='*'); ap.add_argument('--all', action='store_true')
    ap.add_argument('--ss', type=float, default=0); ap.add_argument('--dur', type=float); ap.add_argument('--fine', action='store_true')
    ap.add_argument('--redo', action='store_true'); a = ap.parse_args()
    if not (WHISPER / 'turbo-encoder.int8.onnx').exists(): sys.exit('음성 인식 모델이 없습니다. python tools/get_models.py 를 먼저 실행하세요.')
    import sherpa_onnx
    M = str(WHISPER) + '/'
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=M + 'turbo-encoder.int8.onnx', decoder=M + 'turbo-decoder.int8.onnx',
                                                     tokens=M + 'turbo-tokens.txt', language='ko', task='transcribe', num_threads=4)
    files = [p for p in all_videos() if a.all or any(k.lower() in p.name.lower() for k in a.keys)]
    if not files: sys.exit('해당하는 영상이 없습니다')
    outf = ROOT / 'private' / 'transcripts.json'; outf.parent.mkdir(exist_ok=True)
    out = json.loads(outf.read_text(encoding='utf-8')) if outf.exists() else {}
    part = a.ss or a.dur
    for f in files:
        if f.name in out and not a.redo and not part: print('건너뜀(이미 있음):', f.name); continue
        cut = (['-ss', str(a.ss)] if a.ss else []) + (['-t', str(a.dur)] if a.dur else [])
        raw = run(['ffmpeg', '-v', 'error', *cut, '-i', str(f), '-vn', '-af', 'highpass=f=100,dynaudnorm=f=250:g=15:m=20', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
        au = np.frombuffer(raw, dtype=np.float32)
        c = sherpa_onnx.VadModelConfig(); c.silero_vad.model = str(VAD); c.sample_rate = 16000
        c.silero_vad.threshold = 0.35 if a.fine else 0.3; c.silero_vad.min_silence_duration = 0.18 if a.fine else 0.35
        c.silero_vad.min_speech_duration = 0.2; c.silero_vad.max_speech_duration = 5 if a.fine else 15
        v = sherpa_onnx.VoiceActivityDetector(c, buffer_size_in_seconds=200); segs = []
        def drain():
            while not v.empty(): s = v.front; segs.append((s.start / 16000, np.array(s.samples))); v.pop()
        for i in range(0, len(au) - 512, 512): v.accept_waveform(au[i:i + 512]); drain()
        v.flush(); drain()
        res = []
        for st, smp in segs:
            s = rec.create_stream(); s.accept_waveform(16000, smp); rec.decode_stream(s); t = s.result.text.strip()
            if t: res.append([round(a.ss + st, 1), round(a.ss + st + len(smp) / 16000, 1), t])
        print(f'== {f.name}  ({len(au)/16000:.1f}초)', flush=True)
        for r in res: print(f'   {r[0]:6.1f}-{r[1]:6.1f}  {r[2]}', flush=True)
        if not part: out[f.name] = dict(dur=round(len(au) / 16000, 1), segs=res); outf.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
