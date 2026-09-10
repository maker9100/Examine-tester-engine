# EDU AI 0.9.4

0.9.3의 Gemini 백엔드는 유지하고, GPT 모델 설정은 변경하지 않은 프론트/오류처리 완성본입니다.

## 이번 수정
- GitHub Pages의 `demoMode` 완전 제거
- 실제 Render 백엔드 `https://examine-tester-engine.onrender.com` 연결
- 서버 연결 상태 표시
- 자료별 `AI 자료 분석` 버튼
- 자료별 `삭제` 버튼
- 체크박스 다중 선택 + `선택 삭제`
- `전체 삭제` + 확인창
- 자료 삭제 시 해당 자료의 요약/원본 삭제, 기존 퀴즈·오답 기록은 보존
- Gemini 429/RESOURCE_EXHAUSTED 오류를 긴 원문 대신 짧은 안내로 표시
- `GPT 분석` 등 GPT 전용 문구를 `AI 자료 분석`으로 변경
- 문제 생성/채점/숙련도 UI를 실제 API에 연결
- `app.js`, `style.css`의 옛 demo 코드를 제거하고 index.html 인라인 방식으로 통일

## GitHub에 넣을 위치
루트:
- `index.html`
- `app.js`
- `style.css`
- `requirements.txt`

`app/` 폴더:
- `app/__init__.py`
- `app/main.py`
- `app/ai.py`
- `app/db.py`

`__pycache__`나 `.pyc` 파일은 업로드하지 마세요.

## Render 설정
Build Command:
`pip install -r requirements.txt`

Start Command:
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`

필수 환경변수:
`GEMINI_API_KEY=...`

현재 GPT 설정은 변경하지 않았습니다.

## 확인
배포 후 아래 주소가 0.9.4를 반환해야 합니다.
`https://examine-tester-engine.onrender.com/api/health`

그다음 GitHub Pages에서 상단에 `서버 연결됨 · 0.9.4 · gemini`가 보이면 실제 백엔드 연결 성공입니다.
