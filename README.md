# ResearchAI
researchai-frontend.vercel.app THIS IS LINK TO OPEN.
ResearchAI is a full-stack research paper tracking and recommendation tool designed to help students, researchers, and academic users manage papers more efficiently. The system allows users to search papers, upload PDFs, organize their reading workflow, generate summaries, chat with papers, discover related work, and produce short literature reviews from selected papers.

## Problem Statement

Researchers and students regularly face the same set of problems:

- too many papers to read and compare
- difficulty organizing papers across different reading stages
- time-consuming manual summarization
- difficulty understanding technical papers quickly
- lack of a simple workflow for discovering related work
- weak support for turning paper collections into structured reviews

Most users switch between multiple tools for search, note-taking, tracking, summarization, and recommendation. This makes the research process fragmented and inefficient.

## Proposed Solution

ResearchAI brings these tasks into one system. It provides:

- a searchable paper workspace
- a personal paper library
- reading status tracking
- PDF upload and extraction
- AI-generated summaries
- chat-based interaction with uploaded papers
- recommendation support
- literature review generation from selected papers

The goal is to reduce the effort required to understand, organize, and continue research work.

## Objectives

- simplify research paper management
- support faster understanding of academic content
- help users move from reading to analysis more efficiently
- provide an intelligent assistant for paper-based interaction
- improve discovery of related papers and research directions

## Key Features

### 1. Dashboard
- overview of total papers, papers read, papers in progress, and citations tracked
- recent activity section
- recent papers section

### 2. Search Papers
- search papers by title, author, keyword, or tag
- display trending/demo papers
- save discovered papers into the personal library

### 3. My Papers
- view saved papers
- filter by status: `All`, `Reading`, `Completed`, `To Read`
- open paper details
- delete papers from the library

### 4. Upload Paper
- upload research papers in PDF format
- extract text from the uploaded file
- parse title, abstract, authors, and keywords where possible

### 5. AI Summary
- generate a concise paper summary
- summarize the paper in a more readable academic format

### 6. Paper Insight Panel
- identify:
  - objective
  - methodology
  - dataset clue
  - key findings
  - limitations
  - future scope

### 7. Research Gap Detection
- identify a likely research gap
- suggest a possible opportunity
- propose a possible future work title

### 8. Chat With Paper
- ask questions about a specific paper
- generate paper-grounded responses using extracted abstract or PDF content

### 9. AI Research Assistant
- answer general project-related and AI-related questions
- explain concepts such as RAG, attention, Transformers, BERT, tokenization, and generative AI
- support paper-aware responses when titles or context are recognized

### 10. Literature Review Generator
- allow the user to select multiple papers
- generate a short structured literature review from the selected set

### 11. Recommendations
- recommend related papers
- show recommendation score and reason

### 12. Notes
- add notes for each paper
- store and delete notes inside the paper view

## System Architecture

ResearchAI follows a full-stack architecture:

```text
Frontend (React + Vite)
        |
        v
Backend API (FastAPI)
        |
        v
SQLite Database + Uploaded PDF Storage
```

### Frontend
- React
- Vite
- custom styling for dashboard, search, library, assistant, recommendations, and review pages

### Backend
- FastAPI
- REST API endpoints for papers, upload, summaries, chat, recommendations, notes, and literature review

### Database
- SQLite for lightweight local/demo storage

### File Processing
- `pypdf` for PDF text extraction

### Optional AI Integration
- Gemini API support
- OpenAI API support
- fallback logic for concept explanation and paper assistance when no external LLM is available

## Tech Stack

### Frontend
- React
- Vite
- JavaScript
- CSS

### Backend
- Python
- FastAPI
- SQLite
- pypdf

### Deployment
- Vercel for frontend
- Render for backend

## Project Structure

```text
backend/
  app/
    main.py
    database.py
    schemas.py
  data/
  uploads/
  requirements.txt

frontend/
  src/
    App.jsx
    api.js
    main.jsx
    styles.css
  package.json

start-backend.bat
start-frontend.bat
render.yaml
DEPLOYMENT.md
```

## Core Workflow

1. user searches or uploads papers
2. papers are stored in the library
3. user updates reading status
4. system generates summary and paper insights
5. user asks questions through chat
6. system suggests related papers
7. user selects papers for literature review generation

## API Modules

The backend includes endpoints for:

- health check
- list papers
- create paper
- upload PDF
- update paper status
- delete paper
- generate summary
- get paper insights
- detect research gap
- create literature review
- assistant chat
- paper notes
- recommendations

## Local Setup

## Prerequisites

- Node.js
- Python 3.12 or compatible Python runtime

## Run Backend

From the project root:

```powershell
.\start-backend.bat
```

If required manually:

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## Run Frontend

From the project root:

```powershell
.\start-frontend.bat
```

Or from the frontend folder:

```powershell
npm install
npm run dev
```

## Local Environment Variables

Frontend:

```text
VITE_API_URL=http://localhost:8000
```

Backend:

```text
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CORS_ORIGIN_REGEX=https://.*\.vercel\.app
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

## Deployment

### Frontend
- deployed on Vercel
- uses `VITE_API_URL` to connect to the backend

### Backend
- deployed on Render
- uses `CORS_ORIGINS` and `CORS_ORIGIN_REGEX` for frontend access control

For deployment details, see:
[DEPLOYMENT.md](C:/Users/haritha/Documents/Codex/2026-04-20-hii-i-am-doing-a-project/DEPLOYMENT.md)

## Testing Scope

The project was tested across the following functional areas:

- dashboard loading
- paper search
- library filters
- recommendations
- upload paper
- summary generation
- paper insight panel
- research gap detection
- AI assistant
- chat with paper
- literature review generation
- notes
- deployment connectivity

## Current Limitations

- PDF extraction quality depends on paper formatting
- advanced summaries are stronger when Gemini or OpenAI API access is configured
- chat quality for uploaded papers depends on extracted text quality
- SQLite is suitable for demo and academic submission use, but not ideal for large-scale production workloads
- authentication is not implemented as a production-grade user management system

## Future Enhancements

- better section-level parsing of papers
- stronger retrieval-based question answering over uploaded PDFs
- semantic similarity recommendations using embeddings
- citation graph visualization
- advanced literature review generation
- user authentication and multi-user workspaces
- cloud storage for persistent uploaded papers

## Academic Value

ResearchAI is useful for:

- students performing literature surveys
- researchers organizing and comparing papers
- academic teams exploring related work faster
- users who want a single workspace for paper tracking and AI-assisted understanding

It combines paper management with modern AI-assisted academic workflow support, which makes it a practical and relevant academic project.

## Conclusion

ResearchAI is a practical research support platform that combines search, tracking, summarization, paper interaction, and recommendation into one application. It addresses a real academic productivity problem and demonstrates how full-stack development and AI assistance can be applied to improve the research workflow.
