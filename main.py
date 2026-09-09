import json
import mimetypes
import os
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import connect, init_db, now_iso
from .ai import analyze_material, generate_quiz, grade_subjective

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"

MAX_FILE_SIZE = 15 * 1024 * 1024
ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
}

app = FastAPI(title="Study AI V0.1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class QuizRequest(BaseModel):
    material_id: int
    count: int = Field(default=10, ge=1, le=30)
    mcq_percent: int = Field(default=70, ge=0, le=100)
    difficulty: str = "mixed"

class GradeRequest(BaseModel):
    quiz_id: int
    answers: dict[str, str | int | float | None]

@app.on_event("startup")
def startup():
    UPLOAD_DIR.mkdir(exist_ok=True)
    init_db()

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/health")
def health():
    return {"ok": True}

@app.post("/api/materials")
async def upload_material(file: UploadFile = File(...)):
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if mime not in ALLOWED_MIME:
        raise HTTPException(400, "PDF, PNG, JPG, WEBP, HEIC만 지원합니다.")

    data = await file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "파일은 최대 15MB까지 업로드할 수 있습니다.")

    ext = Path(file.filename or "").suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / stored_name
    path.write_bytes(data)

    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO materials
            (filename, stored_name, mime_type, size, status, created_at)
            VALUES (?, ?, ?, ?, 'uploaded', ?)""",
            (file.filename or "material", stored_name, mime, len(data), now_iso())
        )
        material_id = cur.lastrowid

    return {"id": material_id, "filename": file.filename, "status": "uploaded"}

@app.get("/api/materials")
def list_materials():
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, filename, mime_type, size, status, title, subject, chapter, created_at
               FROM materials ORDER BY id DESC"""
        ).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/materials/{material_id}")
def get_material(material_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    if not row:
        raise HTTPException(404, "자료를 찾을 수 없습니다.")
    data = dict(row)
    data["summary"] = json.loads(data.pop("summary_json")) if data.get("summary_json") else None
    return data

@app.get("/api/materials/{material_id}/file")
def material_file(material_id: int):
    with connect() as conn:
        row = conn.execute(
            "SELECT stored_name, filename, mime_type FROM materials WHERE id=?",
            (material_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "자료를 찾을 수 없습니다.")
    path = UPLOAD_DIR / row["stored_name"]
    if not path.exists():
        raise HTTPException(404, "원본 파일이 없습니다.")
    return FileResponse(path, media_type=row["mime_type"], filename=row["filename"])

@app.post("/api/materials/{material_id}/analyze")
def analyze(material_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    if not row:
        raise HTTPException(404, "자료를 찾을 수 없습니다.")

    path = UPLOAD_DIR / row["stored_name"]
    try:
        with connect() as conn:
            conn.execute("UPDATE materials SET status='analyzing' WHERE id=?", (material_id,))
        note = analyze_material(path, row["mime_type"])
        with connect() as conn:
            conn.execute(
                """UPDATE materials
                   SET status='ready', title=?, subject=?, chapter=?, summary_json=?
                   WHERE id=?""",
                (
                    note.get("title") or row["filename"],
                    note.get("subject", ""),
                    note.get("chapter", ""),
                    json.dumps(note, ensure_ascii=False),
                    material_id,
                ),
            )
        return note
    except Exception as e:
        with connect() as conn:
            conn.execute("UPDATE materials SET status='error' WHERE id=?", (material_id,))
        raise HTTPException(500, f"AI 분석 실패: {e}")

@app.post("/api/quizzes")
def make_quiz(req: QuizRequest):
    if req.difficulty not in {"easy", "normal", "hard", "mixed"}:
        raise HTTPException(400, "난이도 값이 올바르지 않습니다.")

    with connect() as conn:
        row = conn.execute(
            "SELECT summary_json FROM materials WHERE id=?",
            (req.material_id,)
        ).fetchone()

    if not row or not row["summary_json"]:
        raise HTTPException(400, "먼저 자료를 AI 분석하세요.")

    note = json.loads(row["summary_json"])
    try:
        quiz = generate_quiz(note, req.count, req.mcq_percent, req.difficulty)
    except Exception as e:
        raise HTTPException(500, f"문제 생성 실패: {e}")

    questions = quiz.get("questions", [])
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO quizzes (material_id, title, questions_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (
                req.material_id,
                quiz.get("title", "AI 생성 문제"),
                json.dumps(questions, ensure_ascii=False),
                now_iso(),
            ),
        )
        quiz_id = cur.lastrowid

    public_questions = []
    for q in questions:
        public_questions.append({
            "id": q.get("id"),
            "type": q.get("type"),
            "concept": q.get("concept"),
            "difficulty": q.get("difficulty"),
            "question": q.get("question"),
            "choices": q.get("choices", []),
        })

    return {"quiz_id": quiz_id, "title": quiz.get("title", "AI 생성 문제"), "questions": public_questions}

@app.post("/api/quizzes/grade")
def grade(req: GradeRequest):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM quizzes WHERE id=?",
            (req.quiz_id,)
        ).fetchone()
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
                "type": "multiple_choice",
                "concept": q.get("concept", "기타"),
                "score": 1.0 if correct else 0.0,
                "correct": correct,
                "user_answer": ua,
                "correct_answer": q.get("answer"),
                "explanation": q.get("explanation", ""),
                "feedback": "",
                "error_type": None if correct else "정답 선택 오류",
            })
        else:
            subjective.append({
                "id": qid,
                "concept": q.get("concept", "기타"),
                "question": q.get("question", ""),
                "model_answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
                "user_answer": str(ua or "")[:4000],
            })

    if subjective:
        try:
            graded = grade_subjective(subjective)
        except Exception as e:
            raise HTTPException(500, f"서술형 채점 실패: {e}")

        by_id = {x.get("id"): x for x in graded.get("results", [])}
        for item in subjective:
            g = by_id.get(item["id"], {})
            score = max(0.0, min(1.0, float(g.get("score", 0.0))))
            correct = bool(g.get("correct", score >= 0.95))
            results.append({
                "id": item["id"],
                "type": "short_answer",
                "concept": item["concept"],
                "score": score,
                "correct": correct,
                "user_answer": item["user_answer"],
                "correct_answer": item["model_answer"],
                "explanation": item["explanation"],
                "feedback": g.get("feedback", ""),
                "error_type": None if correct else g.get("error_type", "개념 이해 부족"),
            })

    order = {q.get("id"): i for i, q in enumerate(questions)}
    results.sort(key=lambda x: order.get(x["id"], 9999))

    total = sum(float(r["score"]) for r in results)
    percent = round(total / len(results) * 100) if results else 0

    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO attempts (quiz_id, score_percent, results_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (req.quiz_id, percent, json.dumps(results, ensure_ascii=False), now_iso())
        )
        attempt_id = cur.lastrowid

        grouped = {}
        for r in results:
            concept = (r.get("concept") or "기타").strip()[:100]
            grouped.setdefault(concept, []).append(float(r["score"]))

        for concept, scores in grouped.items():
            accuracy = sum(scores) / len(scores)
            old = conn.execute(
                "SELECT score, attempts FROM mastery WHERE concept=?",
                (concept,)
            ).fetchone()

            old_score = float(old["score"]) if old else 0.5
            old_attempts = int(old["attempts"]) if old else 0
            new_score = round(old_score * 0.65 + accuracy * 0.35, 4)

            conn.execute(
                """INSERT INTO mastery (concept, score, attempts, last_accuracy, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(concept) DO UPDATE SET
                     score=excluded.score,
                     attempts=excluded.attempts,
                     last_accuracy=excluded.last_accuracy,
                     updated_at=excluded.updated_at""",
                (concept, new_score, old_attempts + len(scores), accuracy, now_iso())
            )

    return {"attempt_id": attempt_id, "percentage": percent, "results": results}

@app.get("/api/mastery")
def mastery():
    with connect() as conn:
        rows = conn.execute(
            """SELECT concept, score, attempts, last_accuracy, updated_at
               FROM mastery ORDER BY score ASC, attempts DESC"""
        ).fetchall()
    return [dict(r) for r in rows]
