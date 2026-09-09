# EDU AI V0.7 UI

사용자 스케치 기준으로 UI를 다시 배치한 버전.

## 화면 배치

1. EDU AI 헤더 + 학습 시작
2. 자료 / 문제 설정 2분할
3. 문제 및 오답노트
4. 피드백
5. 하단 고정 메뉴

## 정렬 규칙

- 기본 UI 텍스트: 가운데 정렬
- 문제: 좌측 정렬
- 오답노트/채점 해설: 좌측 정렬
- 요약노트: 좌측 정렬

## 폰트

기본 CSS:

```css
font-family:
  "서초바탕",
  "SeochoBatang",
  "AppleMyungjo",
  "Noto Serif KR",
  "Batang",
  serif;
```

서초바탕이 기기에 설치되어 있으면 우선 사용합니다.
폰트 파일 자체는 프로젝트에 포함하지 않습니다.

## GitHub Pages

GitHub Pages에서는 UI 테스트용 데모 모드가 자동으로 켜집니다.

데모 모드에서 테스트 가능:
- 메뉴 이동
- 파일 선택/미리보기
- 요약 노트 UI
- 문제 생성 UI
- 문제 풀이
- 채점/오답 UI
- 취약 개념/숙련도 UI

실제 AI 분석은 FastAPI 서버에서 실행할 때 사용합니다.

## 실제 AI 실행

`.env.example`을 `.env`로 복사하고 Gemini API 키를 입력합니다.

```env
GEMINI_API_KEY=YOUR_KEY
GEMINI_MODEL=gemini-3.8-flash
```

설치:

```bash
pip install -r requirements.txt
```

실행:

```bash
python -m uvicorn app.main:app --reload
```

브라우저:

```text
http://127.0.0.1:8000
```

## GitHub에 올리면 안 되는 파일

- `.env`
- `study_ai.db`
- 실제 업로드 자료

`.gitignore`에 포함되어 있습니다.
