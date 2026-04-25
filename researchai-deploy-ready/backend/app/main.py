import os
from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

from .database import UPLOAD_DIR, get_connection, init_db, reset_demo_data, seed_db
from .schemas import (
    ChatRequest,
    ChatResponse,
    LiteratureReviewRequest,
    LiteratureReviewResponse,
    Note,
    NoteCreate,
    Paper,
    PaperCreate,
    PaperInsights,
    ResearchGapResponse,
    StatusUpdate,
    SummaryResponse,
)

app = FastAPI(title="ResearchAI API")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_db()


def row_to_paper(row) -> Paper:
    return Paper(
        id=row["id"],
        title=row["title"],
        authors=row["authors"],
        year=row["year"],
        abstract=row["abstract"],
        tags=[tag.strip() for tag in row["tags"].split(",") if tag.strip()],
        citations=row["citations"],
        status=row["status"],
        source=row["source"],
        summary=row["summary"],
    )


def row_to_recommended_paper(row, index: int) -> Paper:
    paper = row_to_paper(row)
    tags = ", ".join(paper.tags[:3]) or "research topic"
    scores = [95, 88, 82, 79]
    reasons = [
        f"Similar because it connects with your saved work on {tags}.",
        f"Recommended due to overlapping methods and keywords: {tags}.",
        f"Useful follow-up reading based on your current research direction in {tags}.",
        f"Related to recent papers in your workspace through shared concepts: {tags}.",
    ]
    return paper.model_copy(
        update={
            "recommendation_score": scores[index % len(scores)],
            "recommendation_reason": reasons[index % len(reasons)],
        }
    )


def row_to_note(row) -> Note:
    return Note(
        id=row["id"],
        paper_id=row["paper_id"],
        content=row["content"],
        created_at=row["created_at"],
    )


def extract_pdf_text(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages[:8]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()
    except Exception:
        return ""


def preview_text(text: str, fallback: str) -> str:
    clean = " ".join(text.split())
    if not clean:
        return fallback
    if len(clean) <= 360:
        return clean
    return f"{clean[:357]}..."


def build_summary(title: str, abstract: str, extracted_text: str | None) -> str:
    source = " ".join((extracted_text or abstract).split())
    if not source:
        source = abstract
    sentences = [part.strip() for part in source.replace("\n", " ").split(".") if part.strip()]
    highlights = sentences[:3] or [abstract]
    bullets = " ".join(f"{index + 1}. {sentence}." for index, sentence in enumerate(highlights))
    return (
        f"Summary for {title}: {bullets} "
        "For the demo, this backend uses extracted paper text when available and produces a concise local summary."
    )


def source_for_paper(row) -> str:
    return " ".join((row["extracted_text"] or row["abstract"] or "").split())


def first_sentence(text: str, fallback: str) -> str:
    clean = " ".join(text.split())
    if not clean:
        return fallback
    sentence = clean.split(".")[0].strip()
    return sentence or fallback


def get_paper_or_404(paper_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return row


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/demo/reset")
def reset_demo() -> dict[str, str]:
    reset_demo_data()
    return {"status": "demo data reset"}


@app.get("/papers", response_model=list[Paper])
def list_papers(status: str | None = None, q: str | None = None) -> list[Paper]:
    query = "SELECT * FROM papers WHERE 1=1"
    params: list[str] = []
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    if q:
        query += " AND (title LIKE ? OR authors LIKE ? OR abstract LIKE ? OR tags LIKE ?)"
        needle = f"%{q}%"
        params.extend([needle, needle, needle, needle])
    query += " ORDER BY id ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_paper(row) for row in rows]


@app.post("/papers", response_model=Paper)
def create_paper(payload: PaperCreate) -> Paper:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO papers (title, authors, year, abstract, tags, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.title,
                payload.authors,
                payload.year,
                payload.abstract,
                ",".join(payload.tags),
                payload.status,
            ),
        )
        paper_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    return row_to_paper(row)


@app.post("/papers/upload", response_model=Paper)
def upload_paper(file: UploadFile = File(...)) -> Paper:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    safe_name = f"{uuid4().hex}_{Path(file.filename).name}"
    destination = UPLOAD_DIR / safe_name
    with destination.open("wb") as output:
        copyfileobj(file.file, output)

    extracted_text = extract_pdf_text(destination)
    title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()
    abstract = preview_text(
        extracted_text,
        "This uploaded paper is stored locally. Text extraction did not find readable text, but the paper is ready for summary and chat demo flows.",
    )
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO papers (title, authors, year, abstract, tags, status, source, file_path, extracted_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                "Uploaded PDF",
                None,
                abstract,
                "Uploaded,PDF",
                "To Read",
                "Local Upload",
                str(destination),
                extracted_text,
            ),
        )
        paper_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    return row_to_paper(row)


@app.patch("/papers/{paper_id}/status", response_model=Paper)
def update_status(paper_id: int, payload: StatusUpdate) -> Paper:
    allowed = {"To Read", "Reading", "Completed"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid paper status.")

    with get_connection() as conn:
        conn.execute("UPDATE papers SET status = ? WHERE id = ?", (payload.status, paper_id))
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return row_to_paper(row)


@app.delete("/papers/{paper_id}")
def delete_paper(paper_id: int) -> dict[str, str]:
    with get_connection() as conn:
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
    return {"status": "deleted"}


@app.get("/papers/{paper_id}/notes", response_model=list[Note])
def list_notes(paper_id: int) -> list[Note]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE paper_id = ? ORDER BY id DESC",
            (paper_id,),
        ).fetchall()
    return [row_to_note(row) for row in rows]


@app.post("/papers/{paper_id}/notes", response_model=Note)
def create_note(paper_id: int, payload: NoteCreate) -> Note:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Note cannot be empty.")

    with get_connection() as conn:
        paper = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found.")
        cursor = conn.execute(
            "INSERT INTO notes (paper_id, content) VALUES (?, ?)",
            (paper_id, content),
        )
        note_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return row_to_note(row)


@app.delete("/notes/{note_id}")
def delete_note(note_id: int) -> dict[str, str]:
    with get_connection() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return {"status": "deleted"}


@app.get("/recommendations", response_model=list[Paper])
def recommendations() -> list[Paper]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM papers WHERE status = 'Recommended' ORDER BY citations DESC"
        ).fetchall()
    return [row_to_recommended_paper(row, index) for index, row in enumerate(rows)]


@app.post("/papers/{paper_id}/summary", response_model=SummaryResponse)
def summarize_paper(paper_id: int) -> SummaryResponse:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Paper not found.")
        summary = build_summary(row["title"], row["abstract"], row["extracted_text"])
        conn.execute("UPDATE papers SET summary = ? WHERE id = ?", (summary, paper_id))
    return SummaryResponse(paper_id=paper_id, summary=summary)


@app.get("/papers/{paper_id}/insights", response_model=PaperInsights)
def paper_insights(paper_id: int) -> PaperInsights:
    row = get_paper_or_404(paper_id)
    tags = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]
    topic = tags[0] if tags else "the selected research problem"
    source = source_for_paper(row)
    core_sentence = first_sentence(source, row["abstract"])
    return PaperInsights(
        paper_id=paper_id,
        objective=f"Understand and improve research around {topic}. The paper begins from this central idea: {core_sentence}.",
        methodology=f"The work uses concepts related to {', '.join(tags[:3]) or 'paper analysis'} and studies how the proposed approach addresses the research problem.",
        dataset="The available metadata does not specify a dataset clearly; for demo purposes, the system flags this as something to verify while reading the full paper.",
        key_findings=f"The paper's main contribution is that it advances {topic} and provides a useful baseline for related work.",
        limitations="The demo analysis suggests checking for evaluation scope, dataset diversity, reproducibility details, and comparison against recent methods.",
        future_scope=f"Future work can extend this direction by applying the method to broader domains, improving evaluation, and comparing it with newer {topic} techniques.",
    )


@app.get("/papers/{paper_id}/research-gap", response_model=ResearchGapResponse)
def research_gap(paper_id: int) -> ResearchGapResponse:
    row = get_paper_or_404(paper_id)
    tags = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]
    topic = tags[0] if tags else "this topic"
    secondary = tags[1] if len(tags) > 1 else "real-world evaluation"
    return ResearchGapResponse(
        paper_id=paper_id,
        gap=f"The paper discusses {topic}, but there is room to explore how well the approach works across diverse datasets, low-resource settings, and practical deployment constraints.",
        opportunity=f"A strong project extension would compare {topic} methods with newer approaches and measure performance, explainability, and user usefulness.",
        possible_title=f"Improving {topic} Research Through {secondary} and Explainable Evaluation",
    )


@app.post("/literature-review", response_model=LiteratureReviewResponse)
def literature_review(payload: LiteratureReviewRequest) -> LiteratureReviewResponse:
    with get_connection() as conn:
        if payload.paper_ids:
            placeholders = ",".join("?" for _ in payload.paper_ids)
            rows = conn.execute(
                f"SELECT * FROM papers WHERE id IN ({placeholders}) ORDER BY year",
                payload.paper_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM papers WHERE status IN ('Completed', 'Reading', 'To Read') ORDER BY year LIMIT 5"
            ).fetchall()

    papers = [row_to_paper(row) for row in rows]
    if not papers:
        raise HTTPException(status_code=400, detail="No papers available for literature review.")

    themes = sorted({tag for paper in papers for tag in paper.tags})[:6]
    paper_lines = " ".join(
        f"{paper.title} ({paper.year or 'n.d.'}) contributes by discussing {paper.abstract.lower()}"
        for paper in papers
    )
    review = (
        f"This literature review covers {len(papers)} papers related to {', '.join(themes) or 'the selected topic'}. "
        f"{paper_lines} Together, these works show how the area has moved from foundational methods toward more capable and scalable research systems. "
        "A clear gap for future work is the need for stronger comparison, explainable evaluation, and practical tools that help researchers apply these ideas efficiently."
    )
    return LiteratureReviewResponse(
        title="Generated Literature Review",
        review=review,
        papers_used=[paper.title for paper in papers],
    )


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    lower_message = message.lower()
    if payload.paper_id:
        with get_connection() as conn:
            paper = conn.execute("SELECT * FROM papers WHERE id = ?", (payload.paper_id,)).fetchone()
        if paper:
            source = paper["extracted_text"] or paper["abstract"]
            snippet = preview_text(source, paper["abstract"])
            if "summary" in lower_message or "summarize" in lower_message:
                answer = build_summary(paper["title"], paper["abstract"], paper["extracted_text"])
            elif "simple" in lower_message or "explain" in lower_message:
                answer = (
                    f"In simple terms, '{paper['title']}' is about this idea: {paper['abstract']} "
                    "It matters because it helps researchers understand the method, result, or direction more quickly."
                )
            else:
                answer = (
                    f"Based on '{paper['title']}', the most relevant content I found is: {snippet} "
                    "For the demo, this answer is generated from the stored paper abstract or extracted PDF text."
                )
        else:
            answer = "I could not find that paper yet."
    else:
        with get_connection() as conn:
            library = conn.execute(
                "SELECT title, status FROM papers WHERE status IN ('To Read', 'Reading', 'Completed') ORDER BY id LIMIT 5"
            ).fetchall()
            recommended = conn.execute(
                "SELECT title FROM papers WHERE status = 'Recommended' ORDER BY citations DESC LIMIT 3"
            ).fetchall()
        if "suggest" in lower_message or "next" in lower_message or "related" in lower_message:
            titles = ", ".join(row["title"] for row in recommended)
            answer = f"Based on your library, good next reads are: {titles}."
        elif "summarize" in lower_message or "saved" in lower_message:
            titles = ", ".join(f"{row['title']} ({row['status']})" for row in library)
            answer = f"Your saved paper set includes: {titles}. Open a specific paper and click Summary for a paper-level summary."
        else:
            answer = (
                "I can summarize saved papers, find related work, compare papers, and suggest what to read next. "
                "For grounded answers, open a paper from My Papers and ask about that paper."
            )

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (paper_id, role, content) VALUES (?, ?, ?)",
            (payload.paper_id, "user", message),
        )
        conn.execute(
            "INSERT INTO chat_messages (paper_id, role, content) VALUES (?, ?, ?)",
            (payload.paper_id, "assistant", answer),
        )
    return ChatResponse(answer=answer)
