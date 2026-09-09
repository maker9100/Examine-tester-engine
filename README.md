# EDU AI V0.8

이번 버전은 **GitHub Pages에서 CSS/JS 경로가 깨지는 문제를 막기 위해 `index.html` 하나에 UI CSS와 JS를 모두 내장**했습니다.

## UI 배치
- EDU AI + 학습 시작
- 자료 / 문제 설정 2분할
- 문제 및 오답노트
- 피드백
- 하단 고정 메뉴

## 정렬
- 문제 / 오답노트 / 요약노트: 좌측 정렬
- 그 외: 가운데 정렬

## 폰트
서초바탕 우선:
`"서초바탕", "SeochoBatang", "AppleMyungjo", "Noto Serif KR", "Batang", serif`

폰트 파일은 포함하지 않았습니다.

## GitHub Pages
루트의 `index.html`만 있어도 UI가 깨지지 않습니다.
GitHub Pages에서는 데모 모드가 자동으로 켜져 버튼/문제/채점 UI를 테스트할 수 있습니다.

## 실제 AI
```bash
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload
```

`.env`:
```env
GEMINI_API_KEY=YOUR_KEY
GEMINI_MODEL=gemini-2.5-flash
```
