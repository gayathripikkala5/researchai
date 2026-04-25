from pydantic import BaseModel


class Paper(BaseModel):
    id: int
    title: str
    authors: str
    year: int | None = None
    abstract: str
    tags: list[str]
    citations: int
    status: str
    source: str
    summary: str | None = None
    recommendation_score: int | None = None
    recommendation_reason: str | None = None


class PaperCreate(BaseModel):
    title: str
    authors: str = "Unknown"
    year: int | None = None
    abstract: str = "Uploaded paper ready for processing."
    tags: list[str] = []
    status: str = "To Read"


class StatusUpdate(BaseModel):
    status: str


class Note(BaseModel):
    id: int
    paper_id: int
    content: str
    created_at: str


class NoteCreate(BaseModel):
    content: str


class ChatRequest(BaseModel):
    paper_id: int | None = None
    message: str


class ChatResponse(BaseModel):
    answer: str


class SummaryResponse(BaseModel):
    paper_id: int
    summary: str


class PaperInsights(BaseModel):
    paper_id: int
    objective: str
    methodology: str
    dataset: str
    key_findings: str
    limitations: str
    future_scope: str


class ResearchGapResponse(BaseModel):
    paper_id: int
    gap: str
    opportunity: str
    possible_title: str


class LiteratureReviewRequest(BaseModel):
    paper_ids: list[int] = []


class LiteratureReviewResponse(BaseModel):
    title: str
    review: str
    papers_used: list[str]

