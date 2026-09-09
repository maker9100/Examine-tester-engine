# EDU AI V0.4 UI

Firebase 없이 로컬/일반 서버에서 실행하는 AI 학습 웹앱 MVP.

## 기능

- PDF / 교과서 이미지 업로드
- Gemini가 자료 직접 분석
- AI 요약노트
- 객관식 / 서술형 비율 선택
- 난이도 및 문제 수 선택
- 객관식 자동 채점
- 서술형 AI 채점
- 오답 유형 분석
- 개념별 취약도 누적
- SQLite 저장
- 모바일 / iPad 반응형
- 필기체 완전 금지

## 구조

```text
study-ai-v01/
├─ app/
│  ├─ main.py
│  ├─ ai.py
│  └─ db.py
├─ static/
│  ├─ index.html
│  ├─ style.css
│  └─ app.js
├─ uploads/
├─ requirements.txt
├─ .env.example
├─ run.bat
└─ README.md
```

## 1. Python 설치

Python 3.11 이상 권장.

## 2. 패키지 설치

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Gemini API 키

`.env.example`을 `.env`로 복사한다.

```env
GEMINI_API_KEY=여기에_키
GEMINI_MODEL=gemini-3.8-flash
```

`.env`는 `.gitignore`에 포함되어 있으므로 GitHub에 올라가지 않는다.

## 4. 실행

```bash
python -m uvicorn app.main:app --reload
```

또는 Windows에서 `run.bat`.

브라우저:

```text
http://127.0.0.1:8000
```

## GitHub

이 폴더를 그대로 저장소에 올리면 된다.

절대 올리면 안 되는 것:

- `.env`
- `study_ai.db`
- 실제 업로드 파일

`.gitignore`에 이미 포함되어 있다.

## 현재 데이터 저장 위치

- 학습 기록: `study_ai.db`
- 원본 자료: `uploads/`

현재는 한 서버의 한 사용자용 구조다.
나중에 Firebase/Auth를 붙일 때 사용자 ID 컬럼을 추가해서 계정별 데이터를 분리하면 된다.

## 주의

이 버전은 MVP다. AI가 만든 문제나 서술형 채점은 틀릴 수 있으므로 실제 시험/평가의 최종 채점 용도로 사용하지 말 것.


## V0.3 UI 변경
- 사이드바 제거
- 상단 4개 탭으로 단순화
- 홈 카드 최소화
- 불필요한 문구/배지 축소
- 문제 생성 설정을 한 카드 안에 정리
- 모바일에서도 같은 구조 유지


## V0.4
프로토타입 판대기 수준에서 벗어나 실제 제품형 UI로 전면 수정: 브랜드 헤더, 히어로, 학습 플로우, 빈 상태, 라이브러리, 요약 워크스페이스, 퀴즈 빌더, 숙련도 분석 UI, 반응형 UI.
