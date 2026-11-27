"""리뷰 페이지에서 남긴 메모(JSON)를 읽고, 반영한 항목에 체크 표시를 한다.

  python tools/feedback.py list                         가장 최근 메모 파일의 대기 항목
  python tools/feedback.py list --all                   반영된 항목까지
  python tools/feedback.py done <id> "무엇을 어떻게 고쳤는지" --in example_v2_1080p.mp4
  python tools/feedback.py note <id> "반영하지 못한 이유 또는 되묻는 질문"     (대기 상태 유지)
  --file <경로> 로 다른 메모 파일을 지정할 수 있다.

규칙: id, t, time, text는 절대 바꾸지 않는다. 파일을 통째로 다시 쓰지 말고 이 도구로만 고친다.
"""
import argparse, json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reviewloop.paths import REVIEW

ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['list', 'done', 'note']); ap.add_argument('id', nargs='?'); ap.add_argument('reply', nargs='?')
ap.add_argument('--in', dest='fixed_in'); ap.add_argument('--file'); ap.add_argument('--all', action='store_true'); a = ap.parse_args()
if a.file: f = Path(a.file)
else:
    if not REVIEW: sys.exit('config.json에 review_dir이 없습니다')
    fs = sorted((REVIEW / '피드백').glob('*.json'), key=lambda p: p.stat().st_mtime)
    if not fs: sys.exit('메모 파일이 없습니다: ' + str(REVIEW / '피드백'))
    f = fs[-1]
d = json.loads(f.read_text(encoding='utf-8')); items = d.get('items', [])
if a.cmd == 'list':
    print(f'{f.name}  (영상: {d.get("video")}, 대기 {sum(i["status"] != "done" for i in items)} / 전체 {len(items)})')
    for i in items:
        if i['status'] == 'done' and not a.all: continue
        print(f'\n[{i["id"]}] {i["time"]} ({i["t"]}초)  {"✓ 반영됨" if i["status"] == "done" else "대기"}' + ('  ← 다시 요청됨' if i.get('reopened') and i['status'] != 'done' else ''))
        print('  메모: ' + i['text'].replace('\n', '\n        '))
        if i.get('caption'): print('  그 시점 자막: ' + i['caption'])
        if i.get('reply'): print('  이전 답: ' + i['reply'])
    sys.exit()
if not a.id or not a.reply: sys.exit('id와 답글이 필요합니다')
it = next((i for i in items if i['id'] == a.id), None)
if not it: sys.exit('그런 id가 없습니다: ' + a.id)
now = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
it['reply'] = a.reply
if a.cmd == 'done': it['status'] = 'done'; it['done_at'] = now; it['fixed_in'] = a.fixed_in
d['updated'] = now
tmp = f.with_suffix('.tmp'); tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'); os.replace(tmp, f)
print(('반영됨으로 표시: ' if a.cmd == 'done' else '답글만 기록(대기 유지): ') + f'[{it["id"]}] {it["time"]} {it["text"][:30]}')
