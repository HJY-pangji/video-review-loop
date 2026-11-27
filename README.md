# video-review-loop

**Edit a video with an AI coding agent, review it like a human, and let the agent apply your notes.**
A small, local toolkit for a scene-script → render → timestamped review → fix loop. Built for Korean travel vlogs with Claude Code, usable for any talking-head or vlog footage.

[한국어 설명은 아래에 있습니다](#한국어)

```
scene script (episodes/*.py) ──► engine renders draft ──► review/review.html
        ▲                                                      │  pause, type a note, Enter
        │                                                      ▼
   agent edits the scene ◄── tools/feedback.py ◄── notes saved as JSON (time + subtitle)
                                 marks each note "applied" with a one-line reply
```

## Why

AI agents can cut, caption and mix video with ffmpeg, but they can't watch it. The bottleneck is the human review. This project makes that review cheap and machine-readable:

- **Review page** (`review/review.html`): a single local HTML file. Start typing and the video pauses; press Enter and the note is saved with its timestamp and the subtitle on screen. Nothing leaves your computer.
- **Feedback loop** (`tools/feedback.py`): lists open notes, maps each timestamp to the scene that produced it (`engine.py at`), and marks notes as applied with a short reply that shows up on the page.
- **Engine** (`reviewloop/`): renders scenes from a plain Python scene list, checks subtitles, normalises loudness, and joins the result.

## Quick start

Requirements: Python 3.10+, ffmpeg on PATH, Chrome or Edge (the review page uses the File System Access API).

```bash
pip install -r requirements.txt
python tools/get_models.py          # optional: speech-to-text and noise-reduction models
cp config.example.json config.json  # point "sources" at your footage, "review_dir" at a review folder
python episodes/example.py check     # validate the example scene list
python episodes/example.py at 25     # which scene is at 0:25?
```

1. Copy `episodes/example.py` and describe your scenes (source clip, in/out, subtitles).
2. Render a draft into your review folder.
3. Open `review/review.html` in Chrome, choose the review folder, watch, and leave notes.
4. Ask your agent to "apply the feedback": it runs `tools/feedback.py`, edits the scenes, re-renders, and marks each note.

Windows setup notes: [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) (Korean). Tested on Linux; Windows is not yet tested.

## Status

Early and opinionated. UI text and comments are in Korean; English translations are welcome. Issues and pull requests are welcome.

## Third-party components (not included)

| Component | Use | License |
|---|---|---|
| ffmpeg | rendering | LGPL/GPL, installed separately |
| sherpa-onnx | speech recognition runtime | Apache-2.0 |
| Whisper models | speech recognition | MIT |
| RNNoise models (GregorR/rnnoise-models) | noise reduction | see that repository |
| Pretendard font | subtitles | SIL OFL 1.1 |

Bring your own music and make sure you have the rights to it.

---

## 한국어

AI 코딩 에이전트(Claude Code 등)로 영상을 편집하고, 사람이 리뷰 페이지에서 시점별 메모를 남기면, 에이전트가 그 메모를 읽고 반영하는 흐름을 위한 도구 모음입니다.

| 파일 | 하는 일 |
|---|---|
| `review/review.html` | 영상을 보며 시점별 메모를 남기는 로컬 페이지. 타이핑하면 멈추고 Enter로 저장, 메모는 JSON으로 저장 |
| `tools/feedback.py` | 대기 중인 메모를 보여 주고, 반영한 항목에 체크와 답글을 기록 |
| `reviewloop/engine.py` | 편집 엔진. 자막 검사, 장면 렌더링, 음량 맞춤, 합치기, 메모 시각으로 장면 찾기(`at`) |
| `reviewloop/draw.py` | 자막·타이틀·배지 그림 생성 |
| `reviewloop/paths.py` | 설정 읽기, 원본 영상 찾기, ffmpeg 실행 |
| `episodes/example.py` | 예시 대본(가상의 장면 7개) |
| `tools/transcribe.py` | 원본 영상 말소리 받아쓰기 |
| `tools/sheet.py` | 시각이 찍힌 미리보기 한 장 만들기 |
| `tools/get_models.py` | 음성 인식·잡음 제거 모델 내려받기 |
| `docs/SETUP_WINDOWS.md` | 윈도우 세팅 순서 |

영상, 음악, 모델, 개인 자료는 들어 있지 않습니다. 라이선스는 MIT입니다.
