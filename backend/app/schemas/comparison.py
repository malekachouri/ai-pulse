from pydantic import BaseModel, Field


class SourcedFact(BaseModel):
    value: str
    source_url: str = Field(description="Where the value was read")
    date: str | None = Field(None, description="Date of the source (release date when known)")
    basis: str | None = Field(None, description="How it was read, e.g. 'release record' or the quoted text")


class BenchmarkCell(BaseModel):
    value: float
    quote: str = Field(description="The sentence of the source that states the score")
    version: str | None = None
    source_url: str
    source_title: str
    source: str
    date: str | None = None


class BenchmarkRow(BaseModel):
    name: str
    reported_by: int
    cells: dict[str, BenchmarkCell | None] = Field(description="model id -> cell; null = not reported")


class ComparedModel(BaseModel):
    id: str
    name: str
    provider: str
    family: str | None = None
    homepage_url: str | None = None
    is_open_weights: bool | None = None
    latest_release: SourcedFact | None = None
    context_window: SourcedFact | None = None
    license: SourcedFact | None = None
    releases_considered: int
    benchmarks_reported: int


class ComparisonOut(BaseModel):
    models: list[ComparedModel]
    benchmarks: list[BenchmarkRow]
    note: str | None = None
    method: str = (
        "Only scores quoted by each model's collected release sources, newest release first, with the quote, "
        "link and date. Sources may use different settings (shots, versions): compare with care. Nothing "
        "is estimated."
    )
