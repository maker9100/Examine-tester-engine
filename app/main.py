import json
import mimetypes
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .ai import analyze_material, research_exam_scope, generate_quiz, grade_subjective
from .db import connect, init_db, now_iso

BASE = Path(__file__).resolve().parent.parent
UPLOADS = BASE / "uploads"
MAX_FILE = 15 * 1024 * 1024
ALLOWED = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
}

app = FastAPI(title="EDU AI 0.9.2")

# GitHub Pages(프론트) -> Render(FastAPI) 요청 허용.
# 추가 도메인은 FRONTEND_ORIGINS 환경변수에 쉼표로 넣을 수 있다.
import os

def _allowed_origins():
    defaults = [
        "https://maker9100.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ]
    extra = [x.strip().rstrip("/") for x in os.getenv("FRONTEND_ORIGINS", "").split(",") if x.strip()]
    return list(dict.fromkeys(defaults + extra))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class ResearchReq(BaseModel):
    grade: str = Field(min_length=1, max_length=40)
    subject: str = Field(min_length=1, max_length=100)
    scope: str = Field(min_length=1, max_length=8000)

class QuizReq(BaseModel):
    material_id: int | None = None
    research_id: int | None = None
    count: int = Field(10, ge=1, le=30)
    mcq_percent: int = Field(70, ge=0, le=100)
    difficulty: str = "mixed"

class GradeReq(BaseModel):
    quiz_id: int
    answers: dict

@app.on_event("startup")
def startup():
    UPLOADS.mkdir(exist_ok=True)
    init_db()

@app.get("/")
def index():
    return FileResponse(BASE / "index.html")

@app.get("/api/health")
def health():
    return {"ok": True, "app": "EDU AI", "version": "0.9.2", "ai": "OpenAI GPT"}

@app.post("/api/materials")
async def upload_material(file: UploadFile = File(...)):
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if mime not in ALLOWED:
        raise HTTPException(400, "PDF/PNG/JPG/WEBP/HEIC만 지원합니다.")

    data = await file.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise HTTPException(413, "파일은 15MB 이하만 지원합니다.")

    stored = f"{uuid.uuid4().hex}{Path(file.filename or '').suffix.lower()}"
    (UPLOADS / stored).write_bytes(data)

    with connect() as c:
        cur = c.execute(
            """INSERT INTO materials
            (filename, stored_name, mime_type, size, status, created_at)
            VALUES (?, ?, ?, ?, 'uploaded', ?)""",
            (file.filename or "material", stored, mime, len(data), now_iso()),
        )
        mid = cur.lastrowid

    return {"id": mid, "filename": file.filename, "status": "uploaded"}

@app.get("/api/materials")
def materials():
    with connect() as c:
        rows = c.execute(
            """SELECT id, filename, mime_type, size, status, title, subject, chapter, created_at
               FROM materials ORDER BY id DESC"""
        ).fetchall()
    return [dict(x) for x in rows]

@app.get("/api/materials/{mid}")
def material(mid: int):
    with connect() as c:
        row = c.execute("SELECT * FROM materials WHERE id=?", (mid,)).fetchone()
    if not row:
        raise HTTPException(404, "자료를 찾을 수 없습니다.")
    d = dict(row)
    d["summary"] = json.loads(d["summary_json"]) if d.get("summary_json") else None
    return d

@app.get("/api/materials/{mid}/file")
def material_file(mid: int):
    with connect() as c:
        row = c.execute("SELECT * FROM materials WHERE id=?", (mid,)).fetchone()
    if not row:
        raise HTTPException(404, "자료를 찾을 수 없습니다.")
    path = UPLOADS / row["stored_name"]
    if not path.exists():
        raise HTTPException(404, "원본 파일이 없습니다.")
    return FileResponse(path, media_type=row["mime_type"], filename=row["filename"])

@app.post("/api/materials/{mid}/analyze")
def material_analyze(mid: int):
    with connect() as c:
        row = c.execute("SELECT * FROM materials WHERE id=?", (mid,)).fetchone()
    if not row:
        raise HTTPException(404, "자료를 찾을 수 없습니다.")

    try:
        note = analyze_material(UPLOADS / row["stored_name"], row["mime_type"])
        with connect() as c:
            c.execute(
                """UPDATE materials
                   SET status='ready', title=?, subject=?, chapter=?, summary_json=?
                   WHERE id=?""",
                (
                    note.get("title") or row["filename"],
                    note.get("subject", ""),
                    note.get("chapter", ""),
                    json.dumps(note, ensure_ascii=False),
                    mid,
                ),
            )
        return note
    except Exception as e:
        raise HTTPException(500, f"GPT 자료 분석 실패: {e}")

@app.post("/api/research")
def research(req: ResearchReq):
    try:
        result = research_exam_scope(req.grade, req.subject, req.scope)
    except Exception as e:
        raise HTTPException(500, f"웹 시험범위 분석 실패: {e}")

    with connect() as c:
        cur = c.execute(
            """INSERT INTO researches (grade, subject, scope, research_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                req.grade,
                req.subject,
                req.scope,
                json.dumps(result, ensure_ascii=False),
                now_iso(),
            ),
        )
        rid = cur.lastrowid

    return {"research_id": rid, **result}

@app.post("/api/quizzes")
def make_quiz(req: QuizReq):
    if not req.material_id and not req.research_id:
        raise HTTPException(400, "학습자료 또는 시험범위 웹 분석 결과가 필요합니다.")

    note = None
    research = None

    with connect() as c:
        if req.material_id:
            row = c.execute(
                "SELECT summary_json FROM materials WHERE id=?",
                (req.material_id,),
            ).fetchone()
            if row and row["summary_json"]:
                note = json.loads(row["summary_json"])

        if req.research_id:
            row = c.execute(
                "SELECT research_json FROM researches WHERE id=?",
                (req.research_id,),
            ).fetchone()
            if row:
                research = json.loads(row["research_json"])

        weak_rows = c.execute(
            """SELECT concept, score, attempts
               FROM mastery
               ORDER BY score ASC, attempts DESC
               LIMIT 5"""
        ).fetchall()

    if req.material_id and note is None and not research:
        raise HTTPException(400, "선택한 자료를 먼저 GPT 분석하세요.")

    weak = [dict(x) for x in weak_rows]

    try:
        quiz = generate_quiz(
            note=note,
            research=research,
            count=req.count,
            mcq_percent=req.mcq_percent,
            difficulty=req.difficulty,
            weak_concepts=weak,
        )
    except Exception as e:
        raise HTTPException(500, f"GPT 문제 생성 실패: {e}")

    questions = quiz.get("questions", [])

    with connect() as c:
        cur = c.execute(
            """INSERT INTO quizzes
               (material_id, research_id, title, questions_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                req.material_id,
                req.research_id,
                quiz.get("title", "EDU AI 문제"),
                json.dumps(questions, ensure_ascii=False),
                now_iso(),
            ),
        )
        qid = cur.lastrowid

    public = [{
        "id": q.get("id"),
        "type": q.get("type"),
        "concept": q.get("concept"),
        "difficulty": q.get("difficulty"),
        "origin": q.get("origin", "AI 신규"),
        "source_hint": q.get("source_hint", ""),
        "question": q.get("question"),
        "choices": q.get("choices", []),
    } for q in questions]

    return {
        "quiz_id": qid,
        "title": quiz.get("title", "EDU AI 문제"),
        "questions": public,
    }

@app.post("/api/quizzes/grade")
def grade(req: GradeReq):
    with connect() as c:
        row = c.execute("SELECT * FROM quizzes WHERE id=?", (req.quiz_id,)).fetchone()

    if not row:
        raise HTTPException(404, "퀴즈를 찾을 수 없습니다.")

    questions = json.loads(row["questions_json"])
    results = []
    subjective = []

    for q in questions:
        qid = q.get("id")
        ua = req.answers.get(qid)

        if q.get("type") == "multiple_choice":
            correct = str(ua) == str(q.get("answer"))
            results.append({
                "id": qid,
                "concept": q.get("concept", "기타"),
                "origin": q.get("origin", ""),
                "correct": correct,
                "score": 1.0 if correct else 0.0,
                "feedback": "",
                "explanation": q.get("explanation", ""),
                "error_type": None if correct else "정답 선택 오류",
            })
        else:
            subjective.append({
                "id": qid,
                "concept": q.get("concept", "기타"),
                "question": q.get("question", ""),
                "model_answer": q.get("answer", ""),
                "user_answer": str(ua or "")[:4000],
                "explanation": q.get("explanation", ""),
            })

    if subjective:
        try:
            graded = grade_subjective(subjective)
        except Exception as e:
            raise HTTPException(500, f"GPT 서술형 채점 실패: {e}")

        gm = {x.get("id"): x for x in graded.get("results", [])}

        for item in subjective:
            g = gm.get(item["id"], {})
            score = max(0.0, min(1.0, float(g.get("score", 0))))
            correct = bool(g.get("correct", score >= 0.95))
            results.append({
                "id": item["id"],
                "concept": item["concept"],
                "correct": correct,
                "score": score,
                "feedback": g.get("feedback", ""),
                "explanation": item["explanation"],
                "error_type": None if correct else g.get("error_type", "개념 이해 부족"),
            })

    order = {q.get("id"): i for i, q in enumerate(questions)}
    results.sort(key=lambda x: order.get(x["id"], 9999))

    percent = round(
        sum(float(x["score"]) for x in results) / max(len(results), 1) * 100
    )

    with connect() as c:
        c.execute(
            """INSERT INTO attempts (quiz_id, score_percent, results_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (req.quiz_id, percent, json.dumps(results, ensure_ascii=False), now_iso()),
        )

        grouped = {}
        for r in results:
            grouped.setdefault((r.get("concept") or "기타")[:100], []).append(float(r["score"]))

        for concept, scores in grouped.items():
            accuracy = sum(scores) / len(scores)
            old = c.execute("SELECT * FROM mastery WHERE concept=?", (concept,)).fetchone()
            old_score = float(old["score"]) if old else 0.5
            old_attempts = int(old["attempts"]) if old else 0
            new_score = round(old_score * 0.65 + accuracy * 0.35, 4)

            c.execute(
                """INSERT INTO mastery
                   (concept, score, attempts, last_accuracy, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(concept) DO UPDATE SET
                     score=excluded.score,
                     attempts=excluded.attempts,
                     last_accuracy=excluded.last_accuracy,
                     updated_at=excluded.updated_at""",
                (concept, new_score, old_attempts + len(scores), accuracy, now_iso()),
            )

    return {"percentage": percent, "results": results}

@app.get("/api/mastery")
def mastery():
    with connect() as c:
        rows = c.execute(
            """SELECT concept, score, attempts, last_accuracy, updated_at
               FROM mastery
               ORDER BY score ASC, attempts DESC"""
        ).fetchall()
    return [dict(x) for x in rows]
