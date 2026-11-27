"""영상 한 개를 시각이 찍힌 미리보기 한 장으로 만든다 (장면 고를 때, 자막이 화면과 맞는지 볼 때).

  python tools/sheet.py 20240501_1030                    전체를 24칸으로
  python tools/sheet.py 20240501_1030 --ss 36 --dur 9 --every 0.5
  python tools/sheet.py out/example/example_v1_1080p.mp4 --ss 300 --dur 60   완성본도 가능
결과: out/sheets/<이름>.jpg
"""
import argparse, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reviewloop.paths import ROOT, find, run

ap = argparse.ArgumentParser(); ap.add_argument('key'); ap.add_argument('--ss', type=float, default=0); ap.add_argument('--dur', type=float)
ap.add_argument('--every', type=float); ap.add_argument('--cols', type=int, default=6); a = ap.parse_args()
src = a.key if Path(a.key).exists() else find(a.key)
dur = a.dur or float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout) - a.ss
every = a.every or max(0.5, dur / 24); n = max(1, int(dur / every)); rows = math.ceil(n / a.cols)
out = ROOT / 'out' / 'sheets'; out.mkdir(parents=True, exist_ok=True); dst = out / (Path(src).stem[:40] + f'_{int(a.ss)}.jpg')
vf = (f"fps=1/{every},scale=-2:240,drawtext=fontfile=assets/fonts/Pretendard-Bold.otf:text='%{{pts\\:hms}}':fontcolor=yellow:fontsize=24:"
      f"box=1:boxcolor=black@0.6:x=4:y=4,tile={a.cols}x{rows}")
r = run(['ffmpeg', '-v', 'error', '-y', '-ss', str(a.ss), '-t', str(dur), '-i', src, '-vf', vf, '-frames:v', '1', '-q:v', '5', str(dst)])
print(('만들었습니다: ' + str(dst) + f'  (칸 간격 {every:.1f}초, 표시 시각은 --ss {a.ss}초 기준 상대 시각)') if r.returncode == 0 else '실패')
