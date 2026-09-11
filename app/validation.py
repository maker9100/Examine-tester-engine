"""Validate AI output before storing it or using it for grading."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class Output(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Formula(Output):
    name: str
    expression: str
    meaning: str


class Term(Output):
    term: str
    definition: str


class Note(Output):
    title: str = Field(min_length=1)
    subject: str
    chapter: str
    summary: str = Field(min_length=1)
    key_points: list[str]
    formulas: list[Formula] = []
    terms: list[Term] = []
    study_tips: list[str] = []
    concepts: list[str]
    uncertainties: list[str] = []
    source_text: str = ""


class Question(Output):
    id: str
    type: Literal["multiple_choice", "subjective"]
    concept: str = Field(min_length=1)
    difficulty: StrictInt = Field(ge=1, le=3)
    origin: str = "AI 신규"
    source_hint: str = ""
    question: str = Field(min_length=1)
    choices: list[str]
    answer: StrictInt | str
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_answer(self):
        if self.type == "multiple_choice":
            if len(self.choices) != 4 or len(set(c.strip() for c in self.choices)) != 4:
                raise ValueError("객관식 보기는 서로 다른 4개여야 한다.")
            if any(not c.strip() for c in self.choices):
                raise ValueError("빈 보기는 허용하지 않는다.")
            if type(self.answer) is not int or not 0 <= self.answer <= 3:
                raise ValueError("객관식 정답은 0~3 정수여야 한다.")
        elif self.choices or not isinstance(self.answer, str) or not self.answer.strip():
            raise ValueError("서술형은 빈 보기와 문자열 모범답안이 필요하다.")
        return self


class Quiz(Output):
    title: str = Field(min_length=1)
    questions: list[Question] = Field(min_length=1)


def mcq_count(count: int, percent: int) -> int:
    return (count * percent + 50) // 100


def validate_quiz(data: dict, count: int, percent: int) -> dict:
    quiz = Quiz.model_validate(data)
    if len(quiz.questions) != count:
        raise ValueError("요청한 문제 수와 생성된 문제 수가 다르다.")
    if sum(q.type == "multiple_choice" for q in quiz.questions) != mcq_count(count, percent):
        raise ValueError("객관식/서술형 개수가 요청과 다르다.")
    if len({q.question.strip() for q in quiz.questions}) != count:
        raise ValueError("중복 문제가 있다.")
    for i, q in enumerate(quiz.questions, 1):
        q.id = f"q{i}"
    return quiz.model_dump()


class Mark(Output):
    id: str
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    feedback: str
    error_type: str | None = None


class Marks(Output):
    results: list[Mark]


def validate_marks(data: dict, items: list[dict]) -> dict:
    marks = Marks.model_validate(data).model_dump()
    expected = {x["id"] for x in items}
    actual = [x["id"] for x in marks["results"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("채점 결과의 문항 ID가 누락되거나 중복되었다.")
    for mark in marks["results"]:
        mark["correct"] = mark["score"] >= 0.95
    return marks


class Concept(Output):
    concept: str
    importance: int = Field(ge=1, le=5)
    reason: str


class Pattern(Output):
    name: str
    concept: str
    difficulty: int = Field(ge=1, le=3)
    description: str
    recommended_weight: int = Field(ge=0, le=100)


class Research(Output):
    summary: str = Field(min_length=1)
    important_concepts: list[Concept]
    patterns: list[Pattern]
    pitfalls: list[str] = []
    search_notes: list[str] = []
    copyright_note: str = ""
