import base64, json, os, re
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def _client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")
    return genai.Client(api_key=key)

def _parse_json(text: str):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        s = min([x for x in [text.find("{"), text.find("[")] if x >= 0])
        e = max(text.rfind("}"), text.rfind("]"))
        return json.loads(text[s:e+1])

def analyze_material(path: Path, mime_type: str):
    client = _client()
    data = base64.b64encode(path.read_bytes()).decode()
    prompt = """첨부 학습자료를 읽고 한국어 요약노트를 만들어라.
반드시 JSON 하나만 출력:
{
 "title":"제목","subject":"과목","chapter":"단원",
 "summary":"핵심 요약","key_points":["핵심 개념"],
 "formulas":[{"name":"이름","expression":"식","meaning":"의미"}],
 "terms":[{"term":"용어","definition":"정의"}],
 "study_tips":["주의점"],"concepts":["개념명"]
}
자료 밖의 내용을 함부로 추가하지 말 것. 불확실한 글자는 판독 불확실이라고 표시.
필기체/손글씨체를 절대 제안하지 말 것."""
    if mime_type == "application/pdf":
        inp = [{"type":"document","data":data,"mime_type":mime_type},{"type":"text","text":prompt}]
    else:
        inp = [{"type":"image","data":data,"mime_type":mime_type},{"type":"text","text":prompt}]
    r = client.interactions.create(model=MODEL, input=inp)
    return _parse_json(r.output_text)

def generate_quiz(note, count, mcq_percent, difficulty):
    client = _client()
    prompt = f"""다음 학습노트에서 정확히 {count}문제를 만들어라.
객관식 비율 약 {mcq_percent}%, 난이도 {difficulty}.
JSON:
{{
 "title":"퀴즈 제목",
 "questions":[
  {{
   "id":"q1","type":"multiple_choice 또는 short_answer",
   "concept":"개념","difficulty":1,"question":"문제",
   "choices":["보기1","보기2","보기3","보기4"],
   "answer":0,
   "explanation":"해설"
  }}
 ]
}}
객관식 answer는 0~3 정수, 서술형 choices는 []이며 answer는 문자열.
학습노트:
{json.dumps(note, ensure_ascii=False)}"""
    r = client.interactions.create(model=MODEL, input=prompt)
    out = _parse_json(r.output_text)
    out["questions"] = out.get("questions", [])[:count]
    for i, q in enumerate(out["questions"], 1):
        q["id"] = f"q{i}"
    return out

def grade_subjective(items):
    if not items: return {"results":[]}
    client = _client()
    prompt = f"""다음 서술형을 채점하라. score는 0~1.
오답 유형은 개념 이해 부족, 공식 기억 오류, 계산 실수, 조건 해석 오류, 문제 독해 오류, 개념 혼동, 풀이 과정 누락, 단순 실수 중 하나.
JSON:
{{"results":[{{"id":"q1","score":1,"correct":true,"feedback":"피드백","error_type":null}}]}}
입력:
{json.dumps(items, ensure_ascii=False)}"""
    r = client.interactions.create(model=MODEL, input=prompt)
    return _parse_json(r.output_text)
