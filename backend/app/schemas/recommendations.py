from pydantic import BaseModel, Field

from app.schemas.article import ArticleOut


class RecommendedItem(BaseModel):
    article: ArticleOut
    reasons: list[str] = Field(description='Why it is recommended, e.g. "Because you follow vLLM"')
    score: float = Field(description="Ranking score (personal signals + importance), for ordering only")


class RecommendedResource(BaseModel):
    title: str
    url: str = Field(description="Curated official documentation (app/ai/learning.py); never generated")
    reason: str


class Signals(BaseModel):
    followed: list[str]
    interests: list[str]
    read: int = Field(description="Items read in the last 90 days that were taken into account")
    bookmarked: int


class RecommendationsOut(BaseModel):
    items: list[RecommendedItem]
    resources: list[RecommendedResource]
    signals: Signals
    note: str | None = None
    method: str = (
        "Rule-based: followed technologies, read and bookmarked items (shared keywords) and interests. "
        "Only collected items and curated documentation are recommended."
    )


class LessonResource(BaseModel):
    title: str
    url: str
    source: str = Field(description='Always "curated": official documentation from AI Pulse\'s catalog')


class LessonSource(BaseModel):
    article_id: str
    title: str
    url: str
    source: str


class LessonOut(BaseModel):
    id: str
    position: int
    title: str
    explanation: str
    key_points: list[str]
    why_it_matters: str
    try_it: str | None
    topics: list[str]
    resources: list[LessonResource]
    source: LessonSource
    personal_reason: str | None
    unsupported_claims_removed: list[str]
    provider: str
    model: str
    created_at: str


class LessonsOut(BaseModel):
    lesson_date: str
    status: str = Field(description="ready | empty (none generated yet today) | disabled (no LLM configured)")
    lessons: list[LessonOut]
    ai_generated_notice: str = (
        "Lessons are AI-generated from the linked collected item and checked against it; links are curated "
        "official documentation. Verify before relying on them."
    )
