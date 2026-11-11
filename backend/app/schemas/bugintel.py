from pydantic import BaseModel, Field


class BugFact(BaseModel):
    text: str = Field(description="Copied from a structured field of the cited source")
    citation: int = Field(description="Number of the source in `sources`")


class BugSection(BaseModel):
    status: str = Field(description="documented | insufficient")
    text: str | None = Field(
        None, description='AI explanation (grounded, cited) or "insufficient information"'
    )
    text_is_ai: bool
    citations: list[int]
    facts: list[BugFact]


class BugSections(BaseModel):
    cause: BugSection
    impact: BugSection
    affected_versions: BugSection
    fixes: BugSection


class BugSource(BaseModel):
    n: int
    kind: str = Field(description="issue | advisory | cve_record | bug_record | release_notes | fix")
    title: str
    url: str
    published_at: str | None = None


class BugSubject(BaseModel):
    kind: str
    id: str
    title: str
    article_id: str
    url: str


class BugIntelligenceOut(BaseModel):
    subject: BugSubject
    status: str = Field(
        description="ready (AI explanation included) | facts_only (no LLM or not generated yet)"
    )
    sections: BugSections
    sources: list[BugSource]
    unsupported_claims_removed: list[str]
    ai_generated: bool
    provider: str | None = None
    model: str | None = None
    generated_at: str
    llm_available: bool = False
