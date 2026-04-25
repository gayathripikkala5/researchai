import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = DATA_DIR / "researchai.db"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_dirs()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                authors TEXT NOT NULL,
                year INTEGER,
                abstract TEXT NOT NULL,
                tags TEXT NOT NULL,
                citations INTEGER DEFAULT 0,
                status TEXT DEFAULT 'To Read',
                source TEXT DEFAULT 'Manual',
                file_path TEXT,
                extracted_text TEXT,
                summary TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE SET NULL
            );
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(papers)").fetchall()
        }
        if "extracted_text" not in columns:
            conn.execute("ALTER TABLE papers ADD COLUMN extracted_text TEXT")


def reset_demo_data() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_messages")
        conn.execute("DELETE FROM notes")
        conn.execute("DELETE FROM papers")
    seed_db()


def seed_db() -> None:
    seed_papers = [
        (
            "Attention Is All You Need",
            "Vaswani, A., Shazeer, N., Parmar, N.",
            2017,
            "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
            "Transformers,NLP,Deep Learning",
            95000,
            "Completed",
            "arXiv",
        ),
        (
            "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
            "Devlin, J., Chang, M., Lee, K.",
            2019,
            "We introduce a new language representation model called BERT, designed to pre-train deep bidirectional representations.",
            "NLP,Pre-training,Transformers",
            72000,
            "Reading",
            "arXiv",
        ),
        (
            "Language Models are Few-Shot Learners",
            "Brown, T., Mann, B., Ryder, N.",
            2020,
            "We demonstrate that scaling up language models greatly improves task-agnostic, few-shot performance.",
            "LLM,Few-Shot,GPT",
            28000,
            "To Read",
            "OpenAI",
        ),
        (
            "Scaling Laws for Neural Language Models",
            "Kaplan, J., McCandlish, S., Henighan, T.",
            2020,
            "We study empirical scaling laws for language model performance on the cross-entropy loss.",
            "Scaling,LLM",
            4500,
            "To Read",
            "arXiv",
        ),
        (
            "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
            "Wei, J., Wang, X., Schuurmans, D.",
            2022,
            "We explore how generating a chain of thought significantly improves the ability of large language models to perform complex reasoning.",
            "Prompting,Reasoning,LLM",
            5200,
            "Recommended",
            "Google Research",
        ),
        (
            "Constitutional AI: Harmlessness from AI Feedback",
            "Bai, Y., Kadavath, S., Kundu, S.",
            2022,
            "We experiment with methods for training a harmless AI assistant through self-improvement without human labels identifying harmful outputs.",
            "AI Safety,RLHF,Alignment",
            1800,
            "Recommended",
            "Anthropic",
        ),
        (
            "GPT-4 Technical Report",
            "OpenAI",
            2023,
            "We report the development of GPT-4, a large-scale, multimodal model which can accept image and text inputs and produce text outputs.",
            "LLM,Multimodal,GPT",
            8500,
            "Search",
            "OpenAI",
        ),
        (
            "LLaMA: Open and Efficient Foundation Language Models",
            "Touvron, H., Lavril, T., Izacard, G.",
            2023,
            "We introduce LLaMA, a collection of foundation language models ranging from 7B to 65B parameters trained on trillions of tokens.",
            "Open Source,LLM,Foundation Models",
            6200,
            "Search",
            "Meta AI",
        ),
    ]

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        if count:
            return
        conn.executemany(
            """
            INSERT INTO papers
            (title, authors, year, abstract, tags, citations, status, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            seed_papers,
        )
