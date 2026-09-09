# EDU AI V0.9 — GPT + Web Search

Gemini 대신 OpenAI Responses API를 사용하는 버전입니다.

## 새 기능

- GPT로 PDF/이미지 학습자료 분석
- 학년 / 과목 / 시험범위 직접 입력
- GPT Web Search로 공개 기출·모의고사·공개 교육자료의 출제 경향 조사
- 업로드 자료 + 웹 출제 경향 + 기존 취약 개념을 함께 사용해 문제 생성
- 문제마다 출제 출처 유형 표시
  - 업로드 자료
  - 공개 기출 유형 변형
  - AI 신규
  - 취약 개념 복습
- 객관식 자동 채점
- GPT 서술형 채점
- 오답 유형 분석
- 개념별 숙련도 누적

## 저작권 처리

웹 검색에서 상업 문제집/교재 문제를 그대로 긁어와 재배포하지 않습니다.
기본 동작은 공개 자료에서 **출제 유형/개념/난이도 경향을 분석**한 뒤 새 문제로 변형하는 것입니다.

## 설치

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

`.env.example`을 `.env`로 복사:

```env
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-5.6-luna
OPENAI_WEB_MODEL=gpt-5.6-luna
```

실행:

```bash
python -m uvicorn app.main:app --reload
```

브라우저:

```text
http://127.0.0.1:8000
```

## Render

`render.yaml` 포함.

Render 환경변수에 다음을 등록:

```text
OPENAI_API_KEY = 실제 API 키
OPENAI_MODEL = gpt-5.6-luna
OPENAI_WEB_MODEL = gpt-5.6-luna
```

API 키는 GitHub에 올리지 마세요.

## GitHub Pages

GitHub Pages는 Python 백엔드를 실행하지 못하므로 자동으로 데모 모드가 됩니다.
실제 GPT/Web Search 기능은 FastAPI/Render에서 실행합니다.

## UI 규칙

- 기본 폰트: 서초바탕 우선
- 문제: 좌측 정렬
- 오답노트: 좌측 정렬
- 요약노트: 좌측 정렬
- 그 외 UI: 가운데 정렬

CSS와 JavaScript는 `index.html`에도 직접 내장되어 있어서
GitHub Pages에서 경로 문제로 순정 HTML 화면이 뜨는 일을 줄였습니다.
