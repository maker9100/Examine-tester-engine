import base64
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

def _client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")
    return genai.Client(api_key=api_key)

def _json_from_text(text: str):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [p for p in (text.find("{"), text.find("[")) if p >= 0]
        if not starts:
            raise
        start = min(starts)
        end_obj = text.rfind("}")
        end_arr = text.rfind("]")
        end = max(end_obj, end_arr)
        return json.loads(text[start:end+1])

def _file_input(path: Path, mime_type: str):
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    if mime_type == "application/pdf":
        return {"type": "document", "data": data, "mime_type": mime_type}
    return {"type": "image", "data": data, "mime_type": mime_type}

def _interaction_json(prompt: str, *, path: Path | None = None, mime_type: str | None = None):
    client = _client()
    input_items = [{"type": "text", "text": prompt}]
    if path is not None and mime_type is not None:
        input_items.insert(0, _file_input(path, mime_type))

    interaction = client.interactions.create(
        model=MODEL,
        input=input_items,
    )
    return _json_from_text(interaction.output_text)

def analyze_material(path: Path, mime_type: str):
    prompt = r"""
너는 한국 중·고등학생용 학습자료 분석기다.
첨부된 학습지/교과서 이미지 또는 PDF를 읽고 요약노트를 만든다.

반드시 JSON 하나만 출력한다. 마크다운 코드펜스 금지.

형식:
{
  "title": "자료 제목",
  "subject": "과목",
  "chapter": "단원/주제",
  "summary": "핵심 내용을 이해하기 쉬운 문장으로 요약",
  "key_points": ["핵심 개념 1", "핵심 개념 2"],
  "formulas": [
    {"name": "공식 또는 법칙 이름", "expression": "식", "meaning": "의미"}
  ],
  "terms": [
    {"term": "용어", "definition": "정의"}
  ],
  "study_tips": ["시험에서 주의할 점"],
  "concepts": ["취약도 추적에 쓸 짧은 개념명"]
}

규칙:
- 첨부 자료를 최우선 근거로 사용한다.
- 자료에 없는 내용을 함부로 만들어내지 않는다.
- 읽기 어려운 글자는 추측하지 말고 '판독 불확실'이라고 표시한다.
- 고등학생이 빠르게 복습할 수 있을 정도로 정리한다.
- 필기체/손글씨체/장식 글꼴을 절대 제안하지 않는다.
- 수식은 일반 텍스트 또는 LaTeX로 정확하게 적는다.
- 불필요하게 긴 문장은 피한다.
"""
    return _interaction_json(prompt, path=path, mime_type=mime_type)

def generate_quiz(note: dict, count: int, mcq_percent: int, difficulty: str):
    prompt = f"""
너는 한국 중·고등학교 시험 문제 출제기다.
아래 학습노트 범위 안에서 문제를 만든다.

문제 수: {count}
객관식 비율: 약 {mcq_percent}%
서술형 비율: 약 {100-mcq_percent}%
난이도: {difficulty}

학습노트:
{json.dumps(note, ensure_ascii=False)}

반드시 JSON 하나만 출력한다. 마크다운 코드펜스 금지.

형식:
{{
  "title": "퀴즈 제목",
  "questions": [
    {{
      "id": "q1",
      "type": "multiple_choice",
      "concept": "평가 개념",
      "difficulty": 1,
      "question": "문제",
      "choices": ["보기1","보기2","보기3","보기4"],
      "answer": 0,
      "explanation": "해설"
    }},
    {{
      "id": "q2",
      "type": "short_answer",
      "concept": "평가 개념",
      "difficulty": 2,
      "question": "서술형 문제",
      "choices": [],
      "answer": "모범답안",
      "explanation": "해설"
    }}
  ]
}}

규칙:
- 정확히 {count}문제를 만든다.
- 객관식은 보기 4개, answer는 0~3 정수.
- 서술형 choices는 빈 배열, answer는 모범답안 문자열.
- difficulty는 1~3 정수.
- 문제마다 concept를 반드시 넣는다.
- 문제를 반복하지 않는다.
- 학습노트 밖의 지식을 요구하지 않는다.
"""
    result = _interaction_json(prompt)
    questions = result.get("questions", [])[:count]
    for i, q in enumerate(questions, 1):
        q["id"] = f"q{i}"
    result["questions"] = questions
    return result

def grade_subjective(items: list[dict]):
    if not items:
        return {"results": []}

    prompt = f"""
너는 한국 중·고등학생의 서술형 답안을 채점한다.
핵심 의미가 맞으면 표현이 달라도 인정한다.

각 문항 score는 0.0~1.0.
오답 또는 부분정답이면 error_type을 다음 중 하나로 분류한다:
개념 이해 부족, 공식 기억 오류, 계산 실수, 조건 해석 오류,
문제 독해 오류, 개념 혼동, 풀이 과정 누락, 단순 실수

입력:
{json.dumps(items, ensure_ascii=False)}

반드시 JSON 하나만 출력한다:
{{
  "results": [
    {{
      "id": "q1",
      "score": 0.8,
      "correct": false,
      "feedback": "짧고 구체적인 피드백",
      "error_type": "풀이 과정 누락"
    }}
  ]
}}
"""
    return _interaction_json(prompt)
