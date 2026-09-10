import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
OPENAI_WEB_MODEL = os.getenv("OPENAI_WEB_MODEL", OPENAI_MODEL)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").strip().lower()


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        starts = [x for x in (text.find("{"), text.find("[")) if x >= 0]
        if not starts:
            raise ValueError("AI 응답에서 JSON을 찾을 수 없습니다.")
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end <= start:
            raise ValueError("AI JSON 응답이 불완전합니다.")
        return json.loads(text[start:end + 1])


def active_provider() -> str:
    if AI_PROVIDER in {"gemini", "openai"}:
        return AI_PROVIDER
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "none"


def _gemini_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")
    from google import genai
    return genai.Client(api_key=key)


def _openai_client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    from openai import OpenAI
    return OpenAI(api_key=key)


def _gemini_json(prompt: str, *, use_search: bool = False) -> tuple[dict, list[dict]]:
    from google.genai import types

    client = _gemini_client()
    config_kwargs = {
        "response_mime_type": "application/json",
        "temperature": 0.2,
    }
    if use_search:
        config_kwargs["tools"] = [
            types.Tool(google_search=types.GoogleSearch())
        ]

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    data = _parse_json(response.text or "")
    sources: list[dict] = []

    try:
        candidate = response.candidates[0]
        gm = candidate.grounding_metadata
        for chunk in (gm.grounding_chunks or []):
            web = getattr(chunk, "web", None)
            if web and getattr(web, "uri", None):
                sources.append({
                    "title": getattr(web, "title", None) or web.uri,
                    "url": web.uri,
                })
    except Exception:
        pass

    # 중복 제거
    seen = set()
    unique = []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            unique.append(s)
    return data, unique[:20]


def _openai_json(prompt: str, *, model: str | None = None, use_search: bool = False) -> tuple[dict, list[dict]]:
    client = _openai_client()
    kwargs = {
        "model": model or OPENAI_MODEL,
        "input": prompt,
    }
    if use_search:
        kwargs["tools"] = [{"type": "web_search", "search_context_size": "high"}]

    response = client.responses.create(**kwargs)
    data = _parse_json(response.output_text)
    sources: list[dict] = []

    if use_search:
        try:
            raw = response.model_dump()
        except Exception:
            raw = {}

        found: dict[str, dict] = {}

        def walk(obj: Any):
            if isinstance(obj, dict):
                url = obj.get("url")
                typ = str(obj.get("type", ""))
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    title = obj.get("title") or obj.get("name") or url
                    if ("citation" in typ) or typ == "url" or "source" in typ or "web" in typ:
                        found[url] = {"title": str(title), "url": url}
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for x in obj:
                    walk(x)

        walk(raw)
        sources = list(found.values())[:20]

    return data, sources


def _json_ai(prompt: str, *, use_search: bool = False) -> tuple[dict, list[dict]]:
    provider = active_provider()
    if provider == "gemini":
        return _gemini_json(prompt, use_search=use_search)
    if provider == "openai":
        return _openai_json(
            prompt,
            model=OPENAI_WEB_MODEL if use_search else OPENAI_MODEL,
            use_search=use_search,
        )
    raise RuntimeError("사용 가능한 AI API 키가 없습니다. GEMINI_API_KEY 또는 OPENAI_API_KEY를 설정하세요.")


def analyze_material(path: Path, mime_type: str) -> dict:
    prompt = """
너는 한국 중·고등학생용 학습자료 분석기다.
첨부된 학습지/교과서 이미지 또는 PDF를 읽고 요약 노트를 만들어라.

반드시 JSON 하나만 출력한다.

{
  "title": "자료 제목",
  "subject": "과목",
  "chapter": "단원/주제",
  "summary": "핵심 요약",
  "key_points": ["핵심 개념"],
  "formulas": [{"name":"공식/법칙 이름","expression":"식","meaning":"의미"}],
  "terms": [{"term":"용어","definition":"정의"}],
  "study_tips": ["시험에서 주의할 점"],
  "concepts": ["숙련도 추적용 짧은 개념명"]
}

규칙:
- 첨부 자료가 최우선 근거다.
- 자료에 없는 내용을 함부로 추가하지 않는다.
- 판독이 불확실하면 추측하지 말고 '판독 불확실'이라고 표시한다.
- 고등학생이 복습하기 쉬운 길이로 정리한다.
"""

    provider = active_provider()

    if provider == "gemini":
        from google.genai import types
        client = _gemini_client()
        part = types.Part.from_bytes(
            data=path.read_bytes(),
            mime_type=mime_type,
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt, part],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return _parse_json(response.text or "")

    if provider == "openai":
        client = _openai_client()

        if mime_type == "application/pdf":
            uploaded = None
            try:
                with path.open("rb") as f:
                    uploaded = client.files.create(file=f, purpose="user_data")
                response = client.responses.create(
                    model=OPENAI_MODEL,
                    input=[{
                        "role": "user",
                        "content": [
                            {"type": "input_file", "file_id": uploaded.id},
                            {"type": "input_text", "text": prompt},
                        ],
                    }],
                )
            finally:
                if uploaded is not None:
                    try:
                        client.files.delete(uploaded.id)
                    except Exception:
                        pass
        else:
            raw = base64.b64encode(path.read_bytes()).decode("ascii")
            data_url = f"data:{mime_type};base64,{raw}"
            response = client.responses.create(
                model=OPENAI_MODEL,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": data_url, "detail": "auto"},
                        {"type": "input_text", "text": prompt},
                    ],
                }],
            )

        return _parse_json(response.output_text)

    raise RuntimeError("사용 가능한 AI API 키가 없습니다.")


def research_exam_scope(grade: str, subject: str, scope: str) -> dict:
    prompt = f"""
대한민국 중·고등학생 시험 대비 자료 조사를 수행한다.

학년: {grade}
과목: {subject}
시험 범위:
{scope}

웹 검색을 활용해 다음을 조사한다.
1. 정부/교육청/평가원/EBS/학교 등에서 공개한 기출 또는 모의고사 자료
2. 공개적으로 열람 가능한 교육 자료에서 확인되는 자주 나오는 개념과 출제 유형
3. 이 시험 범위에서 중요도가 높은 개념
4. 난이도 분포와 자주 나오는 함정

저작권 규칙:
- 상업용 문제집/교재 문제를 원문 그대로 복사하거나 대량 재현하지 않는다.
- 상업 자료는 출제 유형 파악용으로만 참고한다.
- 최종 문제는 새로 만든 문제 또는 기출 유형을 변형한 문제로 만든다.

반드시 JSON 하나만 출력한다.

{{
  "summary": "시험범위 및 웹 조사 요약",
  "important_concepts": [
    {{"concept":"개념명","importance":1,"reason":"중요한 이유"}}
  ],
  "patterns": [
    {{
      "name":"출제 유형 이름",
      "concept":"관련 개념",
      "difficulty":1,
      "description":"문제 유형 설명",
      "recommended_weight":20
    }}
  ],
  "pitfalls": ["자주 틀리는 포인트"],
  "search_notes": ["검색에서 확인한 특징"],
  "copyright_note": "원문 복제 대신 유형 변형을 사용한다는 설명"
}}
"""
    result, sources = _json_ai(prompt, use_search=True)
    result["sources"] = sources
    return result


def generate_quiz(
    *,
    note: dict | None,
    research: dict | None,
    count: int,
    mcq_percent: int,
    difficulty: str,
    weak_concepts: list[dict] | None = None,
) -> dict:
    weak_concepts = weak_concepts or []

    prompt = f"""
너는 한국 중·고등학교 시험 문제 출제기다.

아래 정보를 바탕으로 정확히 {count}문제를 만들어라.

객관식 비율: 약 {mcq_percent}%
서술형 비율: 약 {100 - mcq_percent}%
난이도: {difficulty}

업로드 학습자료 요약:
{json.dumps(note, ensure_ascii=False) if note else "없음"}

웹 기반 시험범위 조사:
{json.dumps(research, ensure_ascii=False) if research else "없음"}

사용자의 취약 개념:
{json.dumps(weak_concepts, ensure_ascii=False)}

출제 원칙:
- 업로드 자료가 있으면 그 범위를 벗어나지 않는다.
- 웹 조사 자료가 있으면 자주 나오는 유형과 중요 개념을 반영한다.
- 웹에서 본 문제를 그대로 복사하지 않는다.
- 취약 개념이 있으면 일부 문제를 해당 개념 복습용으로 배정한다.
- 객관식 보기는 4개다.
- 객관식 answer는 0~3 정수다.
- 서술형 choices는 []이고 answer는 모범답안 문자열이다.
- difficulty는 1~3 정수다.

origin 값:
"업로드 자료", "공개 기출 유형 변형", "AI 신규", "취약 개념 복습"

반드시 JSON 하나만 출력:
{{
  "title":"시험 제목",
  "questions":[
    {{
      "id":"q1",
      "type":"multiple_choice",
      "concept":"개념",
      "difficulty":2,
      "origin":"AI 신규",
      "source_hint":"출제 근거를 짧게 설명",
      "question":"문제",
      "choices":["보기1","보기2","보기3","보기4"],
      "answer":0,
      "explanation":"해설"
    }}
  ]
}}
"""
    result, _ = _json_ai(prompt)
    questions = result.get("questions", [])[:count]
    for i, q in enumerate(questions, 1):
        q["id"] = f"q{i}"
    result["questions"] = questions
    return result


def grade_subjective(items: list[dict]) -> dict:
    if not items:
        return {"results": []}

    prompt = f"""
한국 중·고등학생 서술형 답안을 채점한다.
핵심 의미가 맞으면 표현이 달라도 인정한다.
각 score는 0.0~1.0.

오답 유형:
개념 이해 부족, 공식 기억 오류, 계산 실수, 조건 해석 오류,
문제 독해 오류, 개념 혼동, 풀이 과정 누락, 단순 실수

입력:
{json.dumps(items, ensure_ascii=False)}

반드시 JSON 하나만 출력:
{{
  "results":[
    {{
      "id":"q1",
      "score":0.8,
      "correct":false,
      "feedback":"짧고 구체적인 피드백",
      "error_type":"풀이 과정 누락"
    }}
  ]
}}
"""
    result, _ = _json_ai(prompt)
    return result
