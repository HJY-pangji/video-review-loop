# 윈도우 세팅 (처음 한 번)

각 단계가 끝나면 결과를 확인하고 다음으로 넘어간다. 설치 명령은 2026-11 기준이므로 실패하면 최신 방법을 확인한다.
이 도구는 리눅스에서만 시험했다. 윈도우에서는 아래 "알려진 주의점"부터 의심한다.

## 1. 프로그램 설치

| 프로그램 | 확인 명령 | 없으면 |
|---|---|---|
| Python 3.11 이상 | `python --version` | `winget install Python.Python.3.12` |
| ffmpeg (full 빌드) | `ffmpeg -version` | `winget install Gyan.FFmpeg` |
| git | `git --version` | `winget install Git.Git` |
| 파이썬 패키지 | | `pip install -r requirements.txt` |

ffmpeg에 필요한 기능이 들어 있는지 확인한다. 세 줄 모두 결과가 나와야 한다.

```
ffmpeg -hide_banner -filters | findstr arnndn
ffmpeg -hide_banner -filters | findstr ebur128
ffmpeg -hide_banner -encoders | findstr libx264
```

## 2. 서체, 음악, 모델 넣기

저장소에는 들어 있지 않다. 각자 준비한다.

| 무엇 | 어디에 | 어떻게 |
|---|---|---|
| 자막 서체 | `assets/fonts/Pretendard-Bold.otf`, `Pretendard-SemiBold.otf`, `Pretendard-ExtraBold.otf` | Pretendard 배포본(github.com/orioncactus/pretendard, SIL Open Font License)에서 세 파일을 복사 |
| 배경 음악 | `assets/music/<이름>.wav` | 사용 권한이 있는 곡을 아래 명령으로 음량을 맞춰 넣는다. 대본에서 `music='<이름>'`으로 쓴다 |
| 잡음 제거 모델 | `models/rnnoise/` | `python tools/get_models.py denoise` |
| 음성 인식 모델 | `models/` | `python tools/get_models.py asr` (약 540MB, 받아쓰기를 할 때만 필요) |

```
ffmpeg -i 원본.mp3 -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 -ac 2 assets/music/main.wav
```

가사가 있는 곡은 말소리와 겹치므로 피한다.

## 3. 원본 영상과 리뷰 폴더 알려 주기

`config.example.json`을 `config.json`으로 복사하고 경로를 고친다. `config.json`은 git에 올라가지 않는다.

- `sources`: 원본 영상이 든 폴더들. 하위 폴더까지 찾는다. 대본에서는 파일 이름의 일부로 원본을 가리킨다.
- `review_dir`: 리뷰 폴더. 아래 구조로 만든다.

```
review\
├─ review.html      저장소의 review/review.html을 복사
├─ 컨펌본\        검토할 영상 (publish 명령이 여기로 복사한다)
└─ 피드백\        리뷰 페이지가 메모를 저장하는 곳 (자동 생성)
```

## 4. 동작 확인

원본 없이도 되는 것부터 확인한다.

```
python episodes/example.py check
python episodes/example.py timeline
python episodes/example.py at 0:12
```

"example v1: 총 길이 41.7초 = 0분 41초, 장면 7개"와 "0:12 → 장면 S02"가 나오면 된다.

그 다음 `episodes/example.py`를 복사해 자기 영상에 맞게 고친 뒤 한 장면을 만들어 본다.

```
python episodes/ep1.py 0
python episodes/ep1.py all publish
```

## 5. 리뷰 흐름

1. `review_dir`의 `review.html`을 크롬이나 엣지로 직접 연다(더블클릭). 처음 한 번 리뷰 폴더를 선택한다.
2. 영상을 보다가 고칠 곳에서 메모를 쓴다. 메모는 `피드백/<영상이름>.json`에 시각과 함께 저장된다.
3. 편집 담당이 메모를 읽고 고친다.

```
python tools/feedback.py list
python episodes/ep1.py at 6:28
python episodes/ep1.py 12 join publish
python tools/feedback.py done <id> "무엇을 어떻게 고쳤는지" --in ep1_v2_1080p.mp4
```

리뷰 페이지는 4초마다 메모 파일을 다시 읽으므로 체크 표시와 답글이 바로 보인다.

## 알려진 주의점

- 윈도우 경로(`C:\...`)를 ffmpeg 필터 문자열 안에 쓰면 콜론 때문에 실패한다. 엔진은 ffmpeg를 저장소 루트에서 실행하고 잡음 제거 모델과 서체를 상대 경로로 넘긴다.
- 텍스트 파일은 모두 UTF-8이다. 윈도우 기본 인코딩(cp949)으로 열면 한글이 깨진다.
- 리뷰 페이지는 크롬·엣지에서만 동작한다(폴더에 직접 저장하는 기능 때문). 다른 페이지 안에 끼워진 미리보기 창에서는 폴더 선택이 막히므로 파일을 직접 연다.
- `tools/feedback.py`가 기록하는 시각은 한국 표준시(UTC+9) 고정이다.
- 음성 인식은 소음 구간에서 없는 말을 지어내기도 한다. 같은 구간을 두 번 이상 돌려 결과가 갈리면 자막에 쓰지 않는다.
