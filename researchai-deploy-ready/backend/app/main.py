import os
import json
import re
import sqlite3
import urllib.request
import urllib.error
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


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_local_env()

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
cors_origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"https://.*\.vercel\.app",
).strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_db()


def row_to_paper(row) -> Paper:
    title = row["title"]
    authors = row["authors"]
    year = row["year"]
    abstract = row["abstract"]
    tags = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]

    if row["source"] == "Local Upload" and row["extracted_text"]:
        parsed = parse_uploaded_paper_metadata(row["extracted_text"], title)
        title = parsed["title"] or title
        authors = parsed["authors"] or authors
        year = parsed["year"] or year
        abstract = parsed["abstract"] or abstract
        tags = parsed["tags"] or tags

    return Paper(
        id=row["id"],
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        tags=tags,
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


def normalize_pdf_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = text.replace("-\n", "")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    for line in lines:
        if not line:
            cleaned.append("")
            continue
        cleaned.append(" ".join(line.split()))
    return "\n".join(cleaned)


def extract_section(text: str, start_markers: list[str], end_markers: list[str]) -> str:
    upper = text.upper()
    start_index = -1
    for marker in start_markers:
        idx = upper.find(marker.upper())
        if idx != -1 and (start_index == -1 or idx < start_index):
            start_index = idx + len(marker)
    if start_index == -1:
        return ""

    end_index = len(text)
    search_region = upper[start_index:]
    for marker in end_markers:
        idx = search_region.find(marker.upper())
        if idx != -1:
            end_index = min(end_index, start_index + idx)
    return text[start_index:end_index].strip(" \n:-")


def split_sentences(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    cleaned = cleaned.replace("aka.", "aka").replace("i.e.", "ie").replace("e.g.", "eg")
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", cleaned) if part.strip()]
    return parts


def looks_like_author_name(line: str) -> bool:
    if "@" in line or "UNIVERSITY" in line.upper() or len(line.split()) < 2 or len(line.split()) > 4:
        return False
    return all(token[:1].isupper() for token in line.replace("-", " ").split() if token)


def infer_tags_from_text(title: str, abstract: str, keywords: list[str]) -> list[str]:
    if keywords:
        return keywords[:5]
    haystack = f"{title} {abstract}".lower()
    tags = []
    mapping = [
        ("Graph Neural Network", ["graph neural", "gnn"]),
        ("Collaborative Filtering", ["collaborative filtering", "cf"]),
        ("Recommendation", ["recommend", "recommender"]),
        ("Embeddings", ["embedding"]),
        ("Transformers", ["transformer"]),
        ("NLP", ["language", "nlp"]),
    ]
    for tag, keywords_for_tag in mapping:
        if any(keyword in haystack for keyword in keywords_for_tag):
            tags.append(tag)
    return tags[:5] or ["Uploaded", "Research Paper"]


def parse_uploaded_paper_metadata(extracted_text: str, fallback_title: str) -> dict[str, object]:
    text = normalize_pdf_text(extracted_text)
    lines = [line for line in text.splitlines() if line.strip()]
    title = fallback_title
    if lines:
        candidate_title = lines[0].strip(" *")
        if 5 <= len(candidate_title) <= 180:
            title = candidate_title

    author_lines = []
    for line in lines[1:12]:
        if line.upper() == "ABSTRACT":
            break
        if looks_like_author_name(line):
            author_lines.append(line)
    authors = ", ".join(dict.fromkeys(author_lines)) if author_lines else "Uploaded PDF"

    abstract = extract_section(
        text,
        ["ABSTRACT"],
        ["CCS CONCEPTS", "KEYWORDS", "ACM REFERENCE FORMAT", "1 INTRODUCTION", "INTRODUCTION"],
    )
    abstract = " ".join(abstract.split())

    keywords_text = extract_section(
        text,
        ["KEYWORDS"],
        ["ACM REFERENCE FORMAT", "1 INTRODUCTION", "INTRODUCTION"],
    )
    keywords = [part.strip(" .") for part in keywords_text.replace("\n", " ").split(",") if part.strip()]

    year = None
    for token in text.split():
        if token.isdigit() and len(token) == 4 and token.startswith(("19", "20")):
            year = int(token)
            break

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract or preview_text(text, "Uploaded PDF ready for processing."),
        "tags": infer_tags_from_text(title, abstract, keywords),
        "text": text,
    }


def preview_text(text: str, fallback: str) -> str:
    clean = " ".join(text.split())
    if not clean:
        return fallback
    if len(clean) <= 360:
        return clean
    return f"{clean[:357]}..."


def split_query_terms(query: str) -> list[str]:
    terms = []
    for token in re.findall(r"[A-Za-z0-9]+", query.lower()):
        if len(token) >= 3 and token not in terms:
            terms.append(token)
    return terms


def build_summary(title: str, abstract: str, extracted_text: str | None) -> str:
    if extracted_text:
        parsed = parse_uploaded_paper_metadata(extracted_text, title)
        abstract = str(parsed["abstract"] or abstract)
    sentences = split_sentences(abstract)
    cleaned_abstract = " ".join(abstract.split())
    first = sentences[0] if sentences else cleaned_abstract

    problem_sentence = next(
        (
            s
            for s in sentences
            if any(
                phrase in s.lower()
                for phrase in [
                    "existing",
                    "challenge",
                    "problem",
                    "task",
                    "language representation",
                    "sequence",
                ]
            )
        ),
        first,
    )
    method_sentence = next(
        (
            s
            for s in sentences
            if any(
                phrase in s.lower()
                for phrase in [
                    "we introduce",
                    "we propose",
                    "we present",
                    "model",
                    "architecture",
                    "framework",
                    "pre-train",
                ]
            )
        ),
        first,
    )
    impact_sentence = next(
        (
            s
            for s in sentences
            if any(
                phrase in s.lower()
                for phrase in [
                    "improves",
                    "outperforms",
                    "results",
                    "performance",
                    "demonstrate",
                    "state-of-the-art",
                    "effective",
                ]
            )
        ),
        "",
    )

    if not cleaned_abstract:
        return f"{title} explores an academic problem, proposes a method, and reports its main contribution in the paper."

    summary_parts = [
        f"{title} addresses the problem that {problem_sentence[0].lower() + problem_sentence[1:] if len(problem_sentence) > 1 else problem_sentence.lower()}",
        f"The core idea is that {method_sentence[0].lower() + method_sentence[1:] if len(method_sentence) > 1 else method_sentence.lower()}",
    ]
    if impact_sentence and impact_sentence not in {problem_sentence, method_sentence}:
        summary_parts.append(
            f"The paper reports that {impact_sentence[0].lower() + impact_sentence[1:] if len(impact_sentence) > 1 else impact_sentence.lower()}"
        )
    else:
        summary_parts.append(
            "Overall, the contribution is important because it provides a stronger foundation for future work in this area."
        )

    return " ".join(part.rstrip(".") + "." for part in summary_parts)


def call_openai_assistant(message: str, paper_context: str | None = None) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    system_prompt = (
        "You are ResearchAI, a helpful academic research assistant. "
        "Answer clearly, accurately, and simply. "
        "If the user asks about AI concepts such as RAG, tokenization, transformers, or generative AI, explain them like a smart tutor. "
        "If paper context is provided, ground the answer in that paper."
    )
    if paper_context:
        user_input = f"Paper context:\n{paper_context}\n\nUser question:\n{message}"
    else:
        user_input = message

    payload = json.dumps(
        {
            "model": model,
            "instructions": system_prompt,
            "input": user_input,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("output_text"):
            return body["output_text"].strip()
        for item in body.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text = content.get("text", "").strip()
                        if text:
                            return text
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None
    return None


def call_gemini_assistant(message: str, paper_context: str | None = None) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    system_prompt = (
        "You are ResearchAI, a helpful academic research assistant. "
        "Answer clearly, accurately, and simply. "
        "If the user asks about AI concepts such as RAG, tokenization, transformers, or generative AI, explain them like a smart tutor. "
        "If paper context is provided, ground the answer in that paper."
    )
    if paper_context:
        user_input = f"Paper context:\n{paper_context}\n\nUser question:\n{message}"
    else:
        user_input = message

    payload = json.dumps(
        {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [
                        {"text": user_input}
                    ]
                }
            ]
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        for candidate in body.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                text = part.get("text", "").strip()
                if text:
                    return text
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None
    return None


def source_for_paper(row) -> str:
    return " ".join((row["extracted_text"] or row["abstract"] or "").split())


def first_sentence(text: str, fallback: str) -> str:
    clean = " ".join(text.split())
    if not clean:
        return fallback
    sentence = clean.split(".")[0].strip()
    return sentence or fallback


def explain_general_concept(message: str) -> str | None:
    lower_message = message.lower()

    if "attention is all you need" in lower_message:
        return (
            "'Attention Is All You Need' is the 2017 paper that introduced the Transformer architecture. "
            "Its main idea is that sequence modeling can rely entirely on attention mechanisms instead of recurrence or convolution. "
            "That made training more parallelizable and became the foundation for modern large language models."
        )
    if "attention" in lower_message:
        return (
            "Attention is a mechanism that lets a model decide which words or tokens matter most while processing a sentence. "
            "Instead of reading strictly one step at a time, the model can weigh relationships between all tokens and focus on the most relevant ones. "
            "In Transformers, this is what helps the model capture long-range context efficiently."
        )
    if "transformer" in lower_message or "transformers" in lower_message:
        return (
            "A Transformer is a neural network architecture built around attention. "
            "It processes tokens in parallel, learns relationships between them, and scales well to large datasets, which is why it became the base architecture for models like BERT and GPT."
        )
    if "bert" in lower_message:
        return (
            "BERT is a bidirectional Transformer model for language understanding. "
            "Its key idea is to pre-train on large text corpora and learn context from both the left and right side of a word, which makes it strong at tasks like classification, question answering, and sentence understanding."
        )
    if "gpt" in lower_message or "language model" in lower_message or "llm" in lower_message:
        return (
            "A large language model is a neural network trained to predict the next token in text. "
            "By learning from massive datasets, it can generate text, summarize information, answer questions, and perform many language tasks."
        )
    if "rag" in lower_message or "retrieval-augmented generation" in lower_message:
        return (
            "RAG stands for Retrieval-Augmented Generation. Instead of answering only from a model's internal memory, "
            "it retrieves relevant text from documents first and then generates an answer grounded in that retrieved context."
        )
    if "tokenization" in lower_message or "tokenization" in lower_message:
        return (
            "Tokenization is the step where text is split into smaller units called tokens. "
            "Models read and generate tokens rather than full sentences all at once."
        )
    if "generative ai" in lower_message or "gen ai" in lower_message:
        return (
            "Generative AI refers to systems that create new content such as text, code, images, or audio based on patterns learned from data. "
            "Large language models are one example because they generate new text responses from prompts."
        )
    return None


def explain_from_paper_context(message: str, paper_title: str, abstract: str, extracted_text: str | None) -> str | None:
    lower_message = message.lower()
    source_text = extracted_text or abstract or ""
    concept_answer = explain_general_concept(message)

    if "what is attention" in lower_message or "explain attention" in lower_message:
        return (
            f"In the context of '{paper_title}', attention is the core mechanism that lets the model focus on the most relevant parts of an input sequence when processing each token. "
            "The paper's contribution is showing that attention alone can replace recurrence and convolution for sequence transduction. "
            + (concept_answer or "")
        ).strip()

    if "what is this paper about" in lower_message or "paper about" in lower_message or "main idea" in lower_message:
        return (
            f"'{paper_title}' is mainly about this idea: {first_sentence(abstract, abstract)} "
            "In short, the paper introduces the core approach, explains why it is useful, and reports why it improves on earlier methods."
        )

    if "summary" in lower_message or "summarize" in lower_message:
        return build_summary(paper_title, abstract, extracted_text)

    if ("explain" in lower_message or "what is" in lower_message) and concept_answer:
        return (
            f"Using '{paper_title}' as context: {concept_answer} "
            f"The most relevant line from the paper is: {first_sentence(source_text, abstract)}"
        )

    return None


def match_library_paper(message: str, library_rows) -> sqlite3.Row | None:
    lower_message = message.lower()
    for row in library_rows:
        title = row["title"].lower()
        if title in lower_message:
            return row
        title_tokens = [token for token in re.findall(r"[a-z0-9]+", title) if len(token) >= 4]
        if title_tokens and all(token in lower_message for token in title_tokens[:2]):
            return row
    return None


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
        terms = split_query_terms(q) or [q.strip().lower()]
        clauses = []
        for term in terms:
            needle = f"%{term}%"
            clauses.append("(LOWER(title) LIKE ? OR LOWER(authors) LIKE ? OR LOWER(abstract) LIKE ? OR LOWER(tags) LIKE ?)")
            params.extend([needle, needle, needle, needle])
        query += f" AND ({' OR '.join(clauses)})"
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
    parsed = parse_uploaded_paper_metadata(
        extracted_text,
        Path(file.filename).stem.replace("_", " ").replace("-", " ").title(),
    )
    title = str(parsed["title"])
    authors = str(parsed["authors"])
    year = parsed["year"]
    abstract = str(parsed["abstract"])
    tags = ",".join(parsed["tags"])
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO papers (title, authors, year, abstract, tags, status, source, file_path, extracted_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                authors,
                year,
                abstract,
                tags,
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
    parsed = parse_uploaded_paper_metadata(row["extracted_text"], row["title"]) if row["extracted_text"] else None
    title = str(parsed["title"]) if parsed else row["title"]
    abstract = str(parsed["abstract"]) if parsed else row["abstract"]
    tags = list(parsed["tags"]) if parsed else [tag.strip() for tag in row["tags"].split(",") if tag.strip()]
    topic = tags[0] if tags else title
    sentences = split_sentences(abstract)
    objective_sentence = next((s for s in sentences if "we propose" in s.lower() or "we develop" in s.lower() or "we aim" in s.lower()), first_sentence(abstract, row["abstract"]))
    methodology_sentence = next((s for s in sentences if "graph structure" in s.lower() or "propagat" in s.lower() or "embedding" in s.lower()), first_sentence(abstract, row["abstract"]))
    findings_sentence = next((s for s in sentences if "experiments" in s.lower() or "improvement" in s.lower() or "demonstrat" in s.lower()), first_sentence(abstract, row["abstract"]))
    dataset_sentence = next((s for s in sentences if "benchmark" in s.lower() or "dataset" in s.lower()), "The abstract does not name specific datasets in the extracted section.")
    return PaperInsights(
        paper_id=paper_id,
        objective=f"This paper targets {topic.lower()} in recommendation systems. Core objective: {objective_sentence}",
        methodology=f"Method in brief: {methodology_sentence}",
        dataset=f"Experimental setup clue: {dataset_sentence}",
        key_findings=f"Key finding: {findings_sentence}",
        limitations="From the extracted abstract alone, likely limitations to verify in the full paper are scalability, robustness across datasets, and comparison against newer graph recommendation models.",
        future_scope=f"Future work can extend {title} by testing stronger graph architectures, larger benchmarks, and better explainability for recommendation decisions.",
    )


@app.get("/papers/{paper_id}/research-gap", response_model=ResearchGapResponse)
def research_gap(paper_id: int) -> ResearchGapResponse:
    row = get_paper_or_404(paper_id)
    parsed = parse_uploaded_paper_metadata(row["extracted_text"], row["title"]) if row["extracted_text"] else None
    title = str(parsed["title"]) if parsed else row["title"]
    tags = list(parsed["tags"]) if parsed else [tag.strip() for tag in row["tags"].split(",") if tag.strip()]
    topic = tags[0] if tags else title
    secondary = tags[1] if len(tags) > 1 else "real-world evaluation"
    return ResearchGapResponse(
        paper_id=paper_id,
        gap=f"{title} shows strong results, but there is still room to study how this approach behaves under larger-scale, noisier, or more dynamic recommendation settings beyond the reported benchmarks.",
        opportunity=f"A strong extension would compare this {topic.lower()} approach with newer graph-based recommenders and study scalability, cold-start behavior, and explainability.",
        possible_title=f"Extending {title} with {secondary} Analysis and Scalable Evaluation",
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
    answer = ""
    if payload.paper_id:
        with get_connection() as conn:
            paper = conn.execute("SELECT * FROM papers WHERE id = ?", (payload.paper_id,)).fetchone()
        if paper:
            source = paper["extracted_text"] or paper["abstract"]
            snippet = preview_text(source, paper["abstract"])
            llm_answer = call_gemini_assistant(message, paper_context=source[:8000]) or call_openai_assistant(message, paper_context=source[:8000])
            if llm_answer:
                answer = llm_answer
            else:
                guided_answer = explain_from_paper_context(
                    message,
                    paper["title"],
                    paper["abstract"],
                    paper["extracted_text"],
                )
                if guided_answer:
                    answer = guided_answer
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
            if "summary" in lower_message or "summarize" in lower_message:
                answer = build_summary(paper["title"], paper["abstract"], paper["extracted_text"])
            elif not llm_answer and ("simple" in lower_message and "what is" not in lower_message):
                answer = (
                    f"In simple terms, '{paper['title']}' is about this idea: {paper['abstract']} "
                    "It matters because it helps researchers understand the method, result, or direction more quickly."
                )
            elif not llm_answer and not answer:
                answer = (
                    f"Based on '{paper['title']}', the most relevant content I found is: {snippet} "
                    "For the demo, this answer is generated from the stored paper abstract or extracted PDF text."
                )
        else:
            answer = "I could not find that paper yet."
    else:
        llm_answer = call_gemini_assistant(message) or call_openai_assistant(message)
        if llm_answer:
            answer = llm_answer
        with get_connection() as conn:
            library = conn.execute(
                "SELECT title, status, tags, abstract FROM papers WHERE status IN ('To Read', 'Reading', 'Completed') ORDER BY id LIMIT 5"
            ).fetchall()
            recommended = conn.execute(
                "SELECT title FROM papers WHERE status = 'Recommended' ORDER BY citations DESC LIMIT 3"
            ).fetchall()
        matched_paper = match_library_paper(message, library)
        concept_answer = explain_general_concept(message)
        if not llm_answer and matched_paper:
            answer = (
                f"'{matched_paper['title']}' is one of the key papers in your library. "
                f"Main idea: {first_sentence(matched_paper['abstract'], matched_paper['abstract'])} "
                "Open that paper from My Papers if you want a more grounded, paper-specific chat."
            )
        elif not llm_answer and concept_answer:
            answer = concept_answer
        if not llm_answer and ("rag" in lower_message or "retrieval-augmented generation" in lower_message):
            answer = (
                "RAG stands for Retrieval-Augmented Generation. Instead of answering only from a model's internal memory, "
                "it first retrieves relevant text chunks from documents, then uses those chunks to generate a grounded answer. "
                "In your project, the pipeline is: upload paper -> extract text -> store useful sections -> match the user's question to relevant sections -> generate an answer from that retrieved context."
            )
        elif not llm_answer and ("generative ai" in lower_message or "gen ai" in lower_message):
            answer = (
                "Generative AI is a type of artificial intelligence that creates new content such as text, images, audio, or code based on patterns learned from data. "
                "Large language models are a form of generative AI because they generate human-like text in response to prompts."
            )
        elif not llm_answer and "tokenization" in lower_message:
            answer = (
                "Tokenization is the process of breaking text into smaller units called tokens. "
                "A token can be a word, part of a word, or punctuation depending on the tokenizer. "
                "Language models read and generate tokens, not full sentences all at once."
            )
        elif not llm_answer and ("transformer" in lower_message or "transformers" in lower_message):
            answer = (
                "A Transformer is a neural network architecture that uses attention mechanisms to understand relationships between words or tokens in a sequence. "
                "It became the foundation for modern language models because it handles context well and scales effectively."
            )
        elif not llm_answer and "pipeline" in lower_message:
            answer = (
                "Your current ResearchAI pipeline is: collect or upload papers, save metadata and extracted text, generate summaries and insight panels, allow paper-specific chat, and recommend related papers based on topic overlap. "
                "If you want a cleaner explanation in demo terms: input papers, process content, generate understanding, then support discovery."
            )
        elif not llm_answer and "compare" in lower_message:
            if len(library) >= 2:
                first, second = library[0], library[1]
                answer = (
                    f"A simple comparison is between '{first['title']}' and '{second['title']}'. "
                    f"The first focuses on {first['abstract'].lower()} while the second focuses on {second['abstract'].lower()} "
                    "A good comparison framework is: objective, method, strengths, limitations, and future work."
                )
            else:
                answer = "Save at least two papers in My Papers and I can help compare their objectives, methods, and findings."
        elif not llm_answer and ("literature review" in lower_message or "review" in lower_message):
            titles = ", ".join(row["title"] for row in library[:3])
            answer = (
                f"A literature review connects multiple papers into one academic narrative. In your app, you can select papers such as {titles} "
                "and generate a review that explains the common theme, progression of methods, and open research gap."
            )
        elif not llm_answer and ("research gap" in lower_message or "gap" in lower_message):
            answer = (
                "A research gap is the part of a topic that existing papers have not fully explored yet. "
                "In your project, the Research Gap feature looks at the paper topic, methods, and limitations, then suggests a future direction or possible title for new work."
            )
        elif not llm_answer and ("suggest" in lower_message or "next" in lower_message or "related" in lower_message):
            titles = ", ".join(row["title"] for row in recommended)
            answer = f"Based on your library, good next reads are: {titles}."
        elif not llm_answer and ("summarize" in lower_message or "saved" in lower_message):
            titles = ", ".join(f"{row['title']} ({row['status']})" for row in library)
            answer = f"Your saved paper set includes: {titles}. Open a specific paper and click Summary for a paper-level summary."
        elif not llm_answer and ("methodology" in lower_message or "method" in lower_message):
            answer = (
                "When explaining methodology, focus on what approach the paper uses, what data or setup it applies, and why that method was chosen. "
                "Your Paper Insight Panel already organizes this into objective, methodology, findings, limitations, and future scope."
            )
        elif not llm_answer:
            answer = (
                "I can explain RAG, compare papers, summarize saved papers, suggest related work, describe research gaps, and help you understand methodology. "
                "For grounded answers about a specific paper, open it from My Papers and ask inside the paper chat."
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
