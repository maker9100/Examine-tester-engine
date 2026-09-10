# EDU AI 0.9.3 Gemini patch

이 패치는 현재 0.9.2 Render/FastAPI 백엔드를 Gemini 우선 멀티-AI 구조로 바꾼다.

## 변경점
- `GEMINI_API_KEY` 지원
- `AI_PROVIDER=auto|gemini|openai`
- 기본 Gemini 모델: `gemini-3.7-flash`
- Gemini Google Search grounding으로 시험범위 조사
- OpenAI 키가 나중에 생겨도 그대로 함께 사용 가능
- 자료 삭제 API 추가: `DELETE /api/materials/{id}`
- health 응답에 현재 AI provider 표시
- 버전 0.9.3

## Render 환경 변수
필수:
- `GEMINI_API_KEY` = 네 Gemini API 키

선택:
- `AI_PROVIDER` = `auto` (기본값)
- `GEMINI_MODEL` = `gemini-3.7-flash`
- 나중에 GPT 추가 시 `OPENAI_API_KEY`, `OPENAI_MODEL`

`auto`에서는 Gemini 키가 있으면 Gemini를 먼저 사용하고, Gemini 키가 없고 OpenAI 키가 있으면 OpenAI를 사용한다.

## GitHub에서 교체할 파일
- `app/ai.py`
- `app/main.py`
- `app/db.py`
- `requirements.txt`

교체 후 Render에서 최신 커밋을 재배포한다.

## 확인 주소
`https://examine-tester-engine.onrender.com/api/health`

정상이면 JSON에 `"version":"0.9.3"`와 `"ai_provider":"gemini"`가 표시된다.

주의: 현재 Render 무료 인스턴스의 로컬 SQLite/업로드 파일은 영구 저장용이 아니다. Firebase 연결 전까지는 테스트용으로 사용한다.
