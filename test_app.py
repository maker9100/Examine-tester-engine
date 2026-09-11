import copy
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from app import ai, db, main
from app.validation import validate_quiz, validate_marks


def quiz():
    return {"title": "덧셈", "questions": [{"id": "q1", "type": "multiple_choice", "concept": "덧셈", "difficulty": 1, "question": "1+1은?", "choices": ["1", "2", "3", "4"], "answer": 1, "explanation": "1과 1의 합은 2다."}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(ai, "AI_PROVIDER", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(main.app) as c:
        yield c


def material(client, monkeypatch):
    r = client.post("/api/materials", files={"file": ("sheet.png", b"fixture", "image/png")})
    mid = r.json()["id"]
    monkeypatch.setattr(main, "analyze_material", lambda *args: {"title": "덧셈", "subject": "수학", "chapter": "수", "summary": "1+1=2", "concepts": ["덧셈"]})
    assert client.post(f"/api/materials/{mid}/analyze").status_code == 200
    return mid


def test_full_workflow_and_delete_preserves_quiz(client, monkeypatch):
    mid = material(client, monkeypatch)
    monkeypatch.setattr(main, "generate_quiz", lambda **kwargs: quiz())
    r = client.post("/api/quizzes", json={"material_id": mid, "count": 1, "mcq_percent": 100})
    assert r.status_code == 200
    q = r.json()
    assert "answer" not in q["questions"][0]
    assert "explanation" not in q["questions"][0]
    result = client.post("/api/quizzes/grade", json={"quiz_id": q["quiz_id"], "answers": {"q1": "0"}}).json()
    assert result["percentage"] == 0
    assert result["results"][0]["answer"] == 1
    assert client.get("/api/mastery").json()[0]["attempts"] == 1
    assert client.delete(f"/api/materials/{mid}").status_code == 200
    assert not list(main.UPLOADS.iterdir())
    assert client.get(f"/api/materials/{mid}").status_code == 404
    with db.connect() as conn:
        assert conn.execute("select material_id from quizzes").fetchone()[0] is None
        assert conn.execute("select count(*) from attempts").fetchone()[0] == 1


def test_no_key_diagnostic_and_home(client):
    assert "<html" in client.get("/").text
    assert client.get("/api/health").json()["connection_verified"] is False
    assert client.post("/api/ai/check").json() == {"ok": False, "results": []}


def test_missing_references_and_empty_upload(client):
    assert client.post("/api/quizzes", json={"research_id": 999}).status_code == 404
    assert client.post("/api/quizzes", json={"material_id": 999}).status_code == 404
    assert client.post("/api/materials", files={"file": ("a.png", b"", "image/png")}).status_code == 400


@pytest.mark.parametrize("answer", [4, -1, "1", True])
def test_invalid_mcq_answer(answer):
    q = quiz(); q["questions"][0]["answer"] = answer
    with pytest.raises(ValueError):
        validate_quiz(q, 1, 100)


def test_count_ratio_duplicate_guard():
    with pytest.raises(ValueError): validate_quiz(quiz(), 2, 100)
    with pytest.raises(ValueError): validate_quiz(quiz(), 1, 0)
    q = quiz(); q["questions"] *= 2
    with pytest.raises(ValueError): validate_quiz(q, 2, 100)


def test_grade_missing_or_nan_rejected():
    with pytest.raises(ValueError): validate_marks({"results": []}, [{"id": "q1"}])
    with pytest.raises(ValueError): validate_marks({"results": [{"id": "q1", "score": float("nan"), "feedback": ""}]}, [{"id": "q1"}])


def test_auto_fallback_reports_actual_model(monkeypatch):
    monkeypatch.setattr(ai, "AI_PROVIDER", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(ai, "_gemini_json", Mock(side_effect=RuntimeError("429 secret-value")))
    monkeypatch.setattr(ai, "_openai_json", lambda *a, **kw: (quiz(), []))
    result = ai.generate_quiz(note={}, research=None, count=1, mcq_percent=100, difficulty="easy")
    assert result["_ai"]["provider"] == "openai"


def test_explicit_provider_does_not_fallback(monkeypatch):
    monkeypatch.setattr(ai, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(ai, "_gemini_json", Mock(side_effect=RuntimeError("429 secret-value")))
    other = Mock(); monkeypatch.setattr(ai, "_openai_json", other)
    with pytest.raises(RuntimeError) as exc: ai._json_ai("test")
    assert "secret-value" not in str(exc.value)
    other.assert_not_called()


def test_review_calls_model_twice(monkeypatch):
    monkeypatch.setattr(ai, "AI_PROVIDER", "openai")
    fn = Mock(side_effect=lambda *a, **kw: (copy.deepcopy(quiz()), []))
    monkeypatch.setattr(ai, "_openai_json", fn)
    result = ai.generate_quiz(note={}, research=None, count=1, mcq_percent=100, difficulty="easy", review=True)
    assert fn.call_count == 2 and result["reviewed"]


def test_blank_subjective_does_not_call_model(client, monkeypatch):
    mid = material(client, monkeypatch)
    q = quiz(); q["questions"][0].update(type="subjective", choices=[], answer="2")
    monkeypatch.setattr(main, "generate_quiz", lambda **kwargs: q)
    grader = Mock(); monkeypatch.setattr(main, "grade_subjective", grader)
    qid = client.post("/api/quizzes", json={"material_id": mid, "count": 1, "mcq_percent": 0}).json()["quiz_id"]
    r = client.post("/api/quizzes/grade", json={"quiz_id": qid, "answers": {}})
    assert r.json()["percentage"] == 0
    grader.assert_not_called()


def test_output_parser_rejects_array():
    with pytest.raises(ValueError): ai._parse_json("[]")


def test_openai_payload(monkeypatch):
    fake = Mock(); fake.responses.create.return_value.output_text = '{"ok":true}'
    monkeypatch.setattr(ai, "_openai_client", lambda: fake)
    assert ai._openai_json("JSON test")[0]["ok"]
    payload = fake.responses.create.call_args.kwargs
    assert payload["text"]["format"]["type"] == "json_object"
    assert payload["store"] is False
    assert payload["model"] == ai.OPENAI_MODEL
