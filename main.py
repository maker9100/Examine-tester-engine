import json, mimetypes, uuid
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .db import connect, init_db, now_iso
from .ai import analyze_material, generate_quiz, grade_subjective

BASE = Path(__file__).resolve().parent.parent
UPLOADS = BASE / "uploads"
MAX_FILE = 15 * 1024 * 1024
ALLOWED = {"application/pdf","image/png","image/jpeg","image/webp","image/heic","image/heif"}

app = FastAPI(title="EDU AI V0.8")

class QuizReq(BaseModel):
    material_id:int
    count:int=Field(10, ge=1, le=30)
    mcq_percent:int=Field(70, ge=0, le=100)
    difficulty:str="mixed"

class GradeReq(BaseModel):
    quiz_id:int
    answers:dict

@app.on_event("startup")
def startup():
    UPLOADS.mkdir(exist_ok=True)
    init_db()

@app.get("/")
def index():
    return FileResponse(BASE / "index.html")

@app.get("/api/health")
def health():
    return {"ok":True}

@app.post("/api/materials")
async def upload_material(file: UploadFile = File(...)):
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if mime not in ALLOWED:
        raise HTTPException(400, "지원하지 않는 파일 형식입니다.")
    data = await file.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise HTTPException(413, "15MB 이하만 지원합니다.")
    ext = Path(file.filename or "").suffix.lower()
    stored = f"{uuid.uuid4().hex}{ext}"
    (UPLOADS/stored).write_bytes(data)
    with connect() as c:
        cur = c.execute("""INSERT INTO materials
        (filename,stored_name,mime_type,size,status,created_at)
        VALUES(?,?,?,?,?,?)""",(file.filename or "material",stored,mime,len(data),"uploaded",now_iso()))
        mid = cur.lastrowid
    return {"id":mid,"filename":file.filename,"status":"uploaded"}

@app.get("/api/materials")
def list_materials():
    with connect() as c:
        rows=c.execute("""SELECT id,filename,mime_type,size,status,title,subject,chapter,created_at
        FROM materials ORDER BY id DESC""").fetchall()
    return [dict(r) for r in rows]

@app.get("/api/materials/{mid}")
def get_material(mid:int):
    with connect() as c:
        r=c.execute("SELECT * FROM materials WHERE id=?",(mid,)).fetchone()
    if not r: raise HTTPException(404,"자료가 없습니다.")
    d=dict(r)
    d["summary"]=json.loads(d["summary_json"]) if d.get("summary_json") else None
    return d

@app.get("/api/materials/{mid}/file")
def get_file(mid:int):
    with connect() as c:
        r=c.execute("SELECT * FROM materials WHERE id=?",(mid,)).fetchone()
    if not r: raise HTTPException(404,"자료가 없습니다.")
    return FileResponse(UPLOADS/r["stored_name"], media_type=r["mime_type"], filename=r["filename"])

@app.post("/api/materials/{mid}/analyze")
def analyze(mid:int):
    with connect() as c:
        r=c.execute("SELECT * FROM materials WHERE id=?",(mid,)).fetchone()
    if not r: raise HTTPException(404,"자료가 없습니다.")
    try:
        note=analyze_material(UPLOADS/r["stored_name"],r["mime_type"])
        with connect() as c:
            c.execute("""UPDATE materials SET status='ready',title=?,subject=?,chapter=?,summary_json=? WHERE id=?""",
            (note.get("title") or r["filename"],note.get("subject",""),note.get("chapter",""),
             json.dumps(note,ensure_ascii=False),mid))
        return note
    except Exception as e:
        raise HTTPException(500,f"AI 분석 실패: {e}")

@app.post("/api/quizzes")
def make_quiz(req:QuizReq):
    with connect() as c:
        r=c.execute("SELECT summary_json FROM materials WHERE id=?",(req.material_id,)).fetchone()
    if not r or not r["summary_json"]:
        raise HTTPException(400,"먼저 자료를 분석하세요.")
    q=generate_quiz(json.loads(r["summary_json"]),req.count,req.mcq_percent,req.difficulty)
    questions=q.get("questions",[])
    with connect() as c:
        cur=c.execute("""INSERT INTO quizzes(material_id,title,questions_json,created_at) VALUES(?,?,?,?)""",
        (req.material_id,q.get("title","AI 문제"),json.dumps(questions,ensure_ascii=False),now_iso()))
        qid=cur.lastrowid
    pub=[{k:x.get(k) for k in ["id","type","concept","difficulty","question","choices"]} for x in questions]
    return {"quiz_id":qid,"title":q.get("title","AI 문제"),"questions":pub}

@app.post("/api/quizzes/grade")
def grade(req:GradeReq):
    with connect() as c:
        r=c.execute("SELECT * FROM quizzes WHERE id=?",(req.quiz_id,)).fetchone()
    if not r: raise HTTPException(404,"퀴즈가 없습니다.")
    qs=json.loads(r["questions_json"])
    results=[]; subj=[]
    for q in qs:
        ua=req.answers.get(q["id"])
        if q["type"]=="multiple_choice":
            correct=str(ua)==str(q.get("answer"))
            results.append({"id":q["id"],"concept":q.get("concept","기타"),"correct":correct,
            "score":1 if correct else 0,"feedback":"","explanation":q.get("explanation",""),
            "error_type":None if correct else "정답 선택 오류"})
        else:
            subj.append({"id":q["id"],"concept":q.get("concept","기타"),"question":q["question"],
            "model_answer":q.get("answer",""),"user_answer":str(ua or ""), "explanation":q.get("explanation","")})
    if subj:
        g=grade_subjective(subj)
        gm={x.get("id"):x for x in g.get("results",[])}
        for s in subj:
            x=gm.get(s["id"],{})
            score=max(0,min(1,float(x.get("score",0))))
            correct=bool(x.get("correct",score>=.95))
            results.append({"id":s["id"],"concept":s["concept"],"correct":correct,"score":score,
            "feedback":x.get("feedback",""),"explanation":s["explanation"],
            "error_type":None if correct else x.get("error_type","개념 이해 부족")})
    order={q["id"]:i for i,q in enumerate(qs)}
    results.sort(key=lambda x:order.get(x["id"],999))
    pct=round(sum(float(x["score"]) for x in results)/max(len(results),1)*100)
    with connect() as c:
        c.execute("""INSERT INTO attempts(quiz_id,score_percent,results_json,created_at) VALUES(?,?,?,?)""",
        (req.quiz_id,pct,json.dumps(results,ensure_ascii=False),now_iso()))
        grouped={}
        for x in results: grouped.setdefault(x["concept"],[]).append(float(x["score"]))
        for concept,scores in grouped.items():
            acc=sum(scores)/len(scores)
            old=c.execute("SELECT * FROM mastery WHERE concept=?",(concept,)).fetchone()
            old_score=float(old["score"]) if old else .5
            attempts=int(old["attempts"]) if old else 0
            new=round(old_score*.65+acc*.35,4)
            c.execute("""INSERT INTO mastery(concept,score,attempts,last_accuracy,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(concept) DO UPDATE SET score=excluded.score,
            attempts=excluded.attempts,last_accuracy=excluded.last_accuracy,updated_at=excluded.updated_at""",
            (concept,new,attempts+len(scores),acc,now_iso()))
    return {"percentage":pct,"results":results}

@app.get("/api/mastery")
def mastery():
    with connect() as c:
        rows=c.execute("SELECT * FROM mastery ORDER BY score ASC, attempts DESC").fetchall()
    return [dict(r) for r in rows]
