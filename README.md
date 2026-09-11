# EDU AI 0.9.6

0.9.5 교체용 학습 웹앱. 기존 모델 API를 사용하며 자체 학습한 GPT-6 복제 모델이 아니다.
OpenAI 기본 모델을 공식 API 모델 ID `gpt-6-astra`로 변경했다. 해당 모델의 계정 접근 권한과 API 결제가 필요하다.
ChatGPT와 동일한 전체 제품 기능이나 학습 정답률을 보장하지 않는다.

## 적용 순서

1. ZIP을 풀고 `edu-ai-0.9.6` 폴더 **안의 내용**을 GitHub 저장소 루트에 넣는다.
   기존 `app/`를 덮어쓰되 새 파일 `app/validation.py`도 반드시 추가한다.
2. Render Environment에서 아래 값을 설정한다. 키는 GitHub나 index.html에 넣지 않는다.

| 변수 | GPT-6 사용 설정 |
| --- | --- |
| AI_PROVIDER | openai |
| OPENAI_API_KEY | 본인 OpenAI API 키 |
| OPENAI_MODEL | gpt-6-astra |
| OPENAI_WEB_MODEL | gpt-6-astra |

기존 Render에 OPENAI_MODEL/OPENAI_WEB_MODEL이 설정돼 있으면 코드 기본값보다 우선하므로 둘 다 확인한다.
GEMINI_API_KEY만 있으면 GPT-6가 작동하는 것은 아니다.

3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. 배포 후 `/api/health`의 version이 `0.9.6`인지 확인한다.
6. 앱의 **AI 연결 시험**을 누른다. 실제 짧은 텍스트 생성을 요청하므로 비용이 발생할 수 있다.
   이미지/PDF/웹 검색 지원은 별도로 해당 기능을 실행해야 확인된다.
7. 자료 추가 → 파일 이름 선택 → AI 자료 분석 → 홈에서 해당 자료 선택 → 문제 생성 → 채점하기.

Render 주소에서도 앱 화면을 제공한다. GitHub Pages에서는 기존
`https://examine-tester-engine.onrender.com` 서버를 사용한다.
기존 브라우저에 `edu_ai_api_base` 설정이 있으면 그 값이 우선한다.

## Gemini와 자동 전환

- `AI_PROVIDER=openai`: OpenAI만 사용한다. GPT-6를 사용하려면 이 값을 선택한다.
- `AI_PROVIDER=gemini`: Gemini만 사용한다. 기존 기본 모델 `gemini-3.7-flash`를 유지했다.
- `AI_PROVIDER=auto` 또는 생략: 기존대로 Gemini를 먼저 시도하고 실패하면 OpenAI를 사용한다.
  따라서 자동 모드에서 항상 GPT-6를 사용하는 것은 아니다. 생성 결과에 사용 모델을 표시한다.
- 모델 ID는 각 계정에서 실제 사용할 수 있는 ID여야 한다. 접근 오류는 연결 시험에서 확인한다.

## 바뀐 기능

- 자료 요약을 저장하기 전에 필수 구조 검증. 판독 불확실한 부분과 출제용 원문 발췌를 분리.
- OpenAI의 JSON 모드와 서버 검증을 함께 사용. 모델 요청에 학습 도우미 지침 적용.
- 정확한 문제 수와 객관식 개수 검사. 객관식 개수는 문제 수 × 비율을 반올림한다.
- 잘못된 정답 번호, 빈/중복 보기, 중복 문항, 부족한 문항을 저장하지 않고 오류 처리.
- **정답 재검토** 선택 시 초안을 AI에 한 번 더 보내 검토. 기본은 꺼짐.
  추가 비용과 시간이 들며 독립 모델에 의한 검증 또는 정확도 보장을 의미하지 않는다.
- 서술형 채점 결과의 ID 누락·중복·비정상 점수를 차단. 미응답은 API 없이 0점.
- 오답에 문제 본문·정답·해설 표시. 정답은 채점 전 응답에 포함하지 않는다.
- 서버 접속과 AI 연결을 구분. 연결 시험 결과에 공급자·모델·실패 원인을 표시.
- 요약 노트는 필기체 없는 산세리프. 기존 전체 정렬과 좌측 학습 영역 유지.
- 분석 도중 다른 자료를 선택했을 때 결과가 엉뚱한 자료에 표시되는 문제 방지.
- 시험범위 입력 변경 시 이전 웹 조사 선택 해제.
- 기존 개별/선택/전체 삭제 유지. 원본 삭제 실패를 숨기지 않으며 퀴즈·채점 기록은 보존.

## 저장과 운영 범위

기존 SQLite DB 스키마를 유지한다. 기본 데이터 위치도 동일하다.
선택적으로 `DATA_DIR`로 저장 위치를 지정할 수 있다. 경로 변경 시 기존 `study_ai.db`와
`uploads/`를 함께 옮겨야 기존 기록을 사용할 수 있다. 임시 디스크의 데이터 지속성은 보장하지 않는다.

이 버전에는 Firebase 로그인/사용자별 데이터 격리가 없다. 같은 서버의 자료와 숙련도를 공유하는
개인용 구조다. 다중 사용자 공개 서비스로 운영하려면 인증·소유권 검사·호출 제한이 추가로 필요하다.
이미지 호환성이 불확실하면 JPG/PNG 또는 PDF를 사용한다. 원본 파일 크기 제한은 15MB다.
문제 생성은 전체 원본이 아니라 분석 노트와 원문 발췌를 입력으로 사용하므로 중요한 조건이
누락되지 않았는지 요약을 확인한다. API 비용은 사용 공급자 계정에서 별도로 발생한다.

## 검증

실제 API 키를 사용하지 않은 자동 테스트 15개 통과: 업로드/분석/출제/채점/삭제,
기존 기록 보존, 출력 구조 오류, 자동 전환, 재검토 요청, 빈 답안 처리 등.
JavaScript 문법 검사를 통과했다. 실제 유료 모델 호출·정답률·Render 배포는 검증하지 않았다.

로컬 재실행:

```sh
pip install -r requirements.txt
pip install pytest httpx
python -m pytest -q
```

## 공식 참고 문서

확인일: 2026-09-11.

- [GPT-6 Astra 모델과 지원 기능](https://developers.openai.com/api/docs/models/gpt-6-astra)
- [OpenAI JSON 출력](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Gemini generateContent 구조화 출력](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
