import { useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  BookOpen,
  Bot,
  Bookmark,
  Clock3,
  FileText,
  Grid2X2,
  LogOut,
  Search,
  Settings,
  Sparkles,
  Trash2,
  Upload,
  User,
  ExternalLink,
} from "lucide-react";
import {
  createNote,
  deletePaper,
  deleteNote,
  generateLiteratureReview,
  getNotes,
  getPaperInsights,
  getPapers,
  getRecommendations,
  getResearchGap,
  sendChat,
  summarizePaper,
  updatePaperStatus,
  uploadPaper,
} from "./api";

const navItems = [
  ["Dashboard", Grid2X2],
  ["Search Papers", Search],
  ["My Papers", FileText],
  ["AI Assistant", Bot],
  ["Recommendations", Sparkles],
  ["Literature Review", FileText],
  ["Settings", Settings],
];

const statusFilters = ["All", "Reading", "Completed", "To Read"];

function formatCitations(count) {
  return `${Number(count || 0).toLocaleString()} citations`;
}

function statusClass(status) {
  return status.toLowerCase().replace(/\s+/g, "-");
}

function PaperCard({ paper, compact = false, showSave = false, onDelete, onStatus, onSummary, onView }) {
  return (
    <article className={`paper-card ${compact ? "compact" : ""}`}>
      {["Completed", "Reading", "To Read"].includes(paper.status) && (
        <span className={`status-pill ${statusClass(paper.status)}`}>{paper.status}</span>
      )}
      <h3>{paper.title}</h3>
      <p className="meta">
        {paper.authors} - {paper.year || "n.d."}
      </p>
      <p className="abstract">{paper.abstract}</p>
      <div className="tags">
        {paper.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      {paper.status === "Recommended" && (
        <div className="why">Why recommended: {paper.recommendation_reason || "Based on your reading history and research interests."}</div>
      )}
      <div className="card-actions">
        <button className="btn muted" onClick={() => onView?.(paper)}>
          <ExternalLink size={16} /> View
        </button>
        {showSave && (
          <button className="btn muted" onClick={() => onStatus?.(paper.id, "To Read")}>
            <Bookmark size={16} /> Save
          </button>
        )}
        {onSummary && (
          <button className="btn muted" onClick={() => onSummary(paper)}>
            <Sparkles size={16} /> Summary
          </button>
        )}
        {onDelete && (
          <button className="btn danger" onClick={() => onDelete(paper.id)}>
            <Trash2 size={16} /> Delete
          </button>
        )}
        <span className="citations">{formatCitations(paper.citations)}</span>
      </div>
    </article>
  );
}

function Sidebar({ activePage, setActivePage }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <BookOpen size={21} />
        </div>
        <span>ResearchAI</span>
      </div>
      <nav>
        {navItems.map(([label, Icon]) => (
          <button
            key={label}
            className={`nav-item ${activePage === label ? "active" : ""}`}
            onClick={() => setActivePage(label)}
          >
            <Icon size={19} />
            {label}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function Shell({ activePage, setActivePage, children }) {
  return (
    <div className="app">
      <Sidebar activePage={activePage} setActivePage={setActivePage} />
      <main className="main">
        <header className="topbar">
          <button className="icon-button">
            <Grid2X2 size={18} />
          </button>
        </header>
        {children}
      </main>
    </div>
  );
}

function Dashboard({ papers, onUploadClick, onView }) {
  const completed = papers.filter((paper) => paper.status === "Completed").length;
  const reading = papers.filter((paper) => paper.status === "Reading").length;
  const totalCitations = papers.reduce((sum, paper) => sum + paper.citations, 0);
  const recent = papers.filter((paper) => ["Completed", "Reading", "To Read"].includes(paper.status)).slice(0, 4);

  return (
    <section className="page dashboard-page">
      <div className="page-heading row-heading">
        <div>
          <h1>Welcome back</h1>
          <p>Here's an overview of your research activity.</p>
        </div>
        <button className="btn primary" onClick={onUploadClick}>
          <Upload size={17} /> Upload Paper
        </button>
      </div>
      <div className="stats-grid">
        <div className="stat-card">
          <p>Total Papers</p>
          <strong>{papers.length}</strong>
          <span>+5 this week</span>
          <FileText />
        </div>
        <div className="stat-card">
          <p>Papers Read</p>
          <strong>{completed}</strong>
          <span>+2 this week</span>
          <BookOpen />
        </div>
        <div className="stat-card">
          <p>In Progress</p>
          <strong>{reading}</strong>
          <Clock3 />
        </div>
        <div className="stat-card">
          <p>Citations Tracked</p>
          <strong>{(totalCitations / 1000).toFixed(1)}K</strong>
          <BarChart3 />
        </div>
      </div>
      <div className="activity-card">
        <h2>Recent Activity</h2>
        <p>Finished reading "Attention Is All You Need" <span>2 hours ago</span></p>
        <p>Saved "Chain-of-Thought Prompting" to library <span>5 hours ago</span></p>
        <p>Added notes to "BERT" paper <span>1 day ago</span></p>
      </div>
      <h2 className="section-title">Recent Papers</h2>
      <div className="grid-list">
        {recent.map((paper) => (
          <PaperCard key={paper.id} paper={paper} compact onView={onView} />
        ))}
      </div>
    </section>
  );
}

function SearchPapers({ papers, onSearch, query, setQuery, onStatus, onView }) {
  return (
    <section className="page search-page narrow">
      <div className="page-heading centered">
        <h1>Search Papers</h1>
        <p>Find research papers across millions of publications</p>
        <div className="search-box">
          <Search size={24} />
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              onSearch(event.target.value);
            }}
            placeholder="Search by title, author, keyword, or tag..."
          />
        </div>
      </div>
      <h2 className="section-title hot">Trending Papers</h2>
      <div className="stack-list">
        {papers.map((paper) => (
          <PaperCard key={paper.id} paper={paper} showSave onStatus={onStatus} onView={onView} />
        ))}
      </div>
    </section>
  );
}

function MyPapers({ papers, filter, setFilter, onDelete, onSummary, onView }) {
  const visible = useMemo(() => {
    const library = papers.filter((paper) => ["To Read", "Reading", "Completed"].includes(paper.status));
    return filter === "All" ? library : library.filter((paper) => paper.status === filter);
  }, [papers, filter]);

  return (
    <section className="page library-page narrow">
      <div className="page-heading">
        <h1>My Papers</h1>
        <p>{papers.filter((paper) => ["To Read", "Reading", "Completed"].includes(paper.status)).length} papers in your library</p>
      </div>
      <div className="filters">
        {statusFilters.map((status) => (
          <button key={status} className={filter === status ? "active" : ""} onClick={() => setFilter(status)}>
            {status}
          </button>
        ))}
      </div>
      <div className="stack-list">
        {visible.map((paper) => (
          <PaperCard key={paper.id} paper={paper} onDelete={onDelete} onSummary={onSummary} onView={onView} />
        ))}
      </div>
    </section>
  );
}

function Assistant() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm your AI research assistant. I can help you understand papers, find related work, summarize findings, and answer questions about your research. How can I help you today?",
    },
  ]);
  const [input, setInput] = useState("");

  async function submit(message = input) {
    const clean = message.trim();
    if (!clean) return;
    setInput("");
    setMessages((current) => [...current, { role: "user", content: clean }]);
    try {
      const response = await sendChat(clean);
      setMessages((current) => [...current, { role: "assistant", content: response.answer }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", content: error.message }]);
    }
  }

  const suggestions = [
    "Summarize my saved papers",
    "Find related work",
    "Explain in simple terms",
    "Compare papers",
    "Key takeaways from recent reads",
    "Suggest next papers to read",
  ];

  return (
    <section className="assistant-page">
      <div className="assistant-header">
        <div className="round-icon">
          <Bot size={19} />
        </div>
        <div>
          <h1>AI Research Assistant</h1>
          <p>Powered by AI - Ask anything about your research</p>
        </div>
      </div>
      <div className="suggestions">
        <span>SUGGESTED</span>
        <div>
          {suggestions.map((suggestion) => (
            <button key={suggestion} onClick={() => submit(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
      </div>
      <div className="chat-area">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`message ${message.role}`}>
            {message.role === "assistant" && (
              <div className="round-icon small">
                <Bot size={15} />
              </div>
            )}
            <p>{message.content}</p>
          </div>
        ))}
      </div>
      <form
        className="chat-input"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about your research..." />
        <button className="btn primary">Send</button>
      </form>
    </section>
  );
}

function Recommendations({ recommendations, onStatus, onView }) {
  return (
    <section className="page recommendations-page narrow">
      <div className="page-heading">
        <h1>Recommendations</h1>
        <p>papers curated based on your reading history and interests.</p>
      </div>
      <div className="stack-list">
        {recommendations.map((paper, index) => (
          <div className="recommendation-wrap" key={paper.id}>
            <span className="match">{paper.recommendation_score || (index === 0 ? 95 : 88)}% match</span>
            <PaperCard paper={paper} showSave onStatus={onStatus} onView={onView} />
          </div>
        ))}
      </div>
    </section>
  );
}

function LiteratureReview({ papers }) {
  const [review, setReview] = useState(null);
  const [busy, setBusy] = useState(false);
  const libraryPapers = papers.filter((paper) => ["To Read", "Reading", "Completed"].includes(paper.status));
  const [selectedIds, setSelectedIds] = useState([]);

  useEffect(() => {
    setSelectedIds((current) => current.filter((id) => libraryPapers.some((paper) => paper.id === id)));
  }, [papers]);

  function togglePaper(id) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((paperId) => paperId !== id) : [...current, id]
    );
  }

  async function createReview() {
    if (selectedIds.length < 2) {
      setReview({
        title: "Select More Papers",
        review: "Please select at least 2 papers to generate a meaningful literature review.",
        papers_used: [],
      });
      return;
    }
    setBusy(true);
    try {
      setReview(await generateLiteratureReview(selectedIds));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page narrow">
      <div className="page-heading">
        <h1>Literature Review</h1>
        <p>Generate a structured review from papers saved in your library.</p>
      </div>
      <div className="feature-panel">
        <h2>Selected Paper Set</h2>
        <p>Choose exactly the papers you want to include. Select at least 2 papers for a better review.</p>
        <div className="selectable-paper-list">
          {libraryPapers.map((paper) => (
            <label className={`selectable-paper ${selectedIds.includes(paper.id) ? "selected" : ""}`} key={paper.id}>
              <input
                type="checkbox"
                checked={selectedIds.includes(paper.id)}
                onChange={() => togglePaper(paper.id)}
              />
              <span>
                <strong>{paper.title}</strong>
                <small>{paper.authors} - {paper.year || "n.d."}</small>
              </span>
            </label>
          ))}
        </div>
        <p className="selection-count">{selectedIds.length} paper{selectedIds.length === 1 ? "" : "s"} selected</p>
        <button className="btn primary" onClick={createReview} disabled={busy}>
          <Sparkles size={16} /> {busy ? "Generating..." : "Generate Literature Review"}
        </button>
      </div>
      {review && (
        <div className="feature-panel">
          <h2>{review.title}</h2>
          <p className="detail-text">{review.review}</p>
          <p className="detail-label">Papers Used</p>
          <div className="tags">
            {review.papers_used.map((title) => (
              <span key={title}>{title}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function SettingsPage() {
  return (
    <section className="page settings-page narrow">
      <div className="page-heading">
        <h1>Settings</h1>
      </div>
      <div className="profile-card">
        <h2>Profile</h2>
        <div className="profile-row">
          <div className="avatar">
            <User />
          </div>
          <div>
            <h3>Researcher</h3>
            <p>researcher@university.edu</p>
          </div>
        </div>
        <label>
          Display Name
          <input value="Researcher" readOnly />
        </label>
        <label>
          Email
          <input value="researcher@university.edu" readOnly />
        </label>
      </div>
      <button className="btn logout">
        <LogOut size={17} /> Logout
      </button>
    </section>
  );
}

function PaperDetailModal({
  paper,
  summary,
  insights,
  gap,
  busy,
  insightsBusy,
  gapBusy,
  notes,
  noteText,
  setNoteText,
  chatQuestion,
  setChatQuestion,
  paperChat,
  chatBusy,
  onClose,
  onSummary,
  onInsights,
  onGap,
  onStatus,
  onAddNote,
  onDeleteNote,
  onAskPaper,
}) {
  return (
    <div className="modal-backdrop">
      <div className="modal paper-detail-modal">
        <div className="modal-header">
          <div>
            <h2>{paper.title}</h2>
            <p>{paper.authors} - {paper.year || "n.d."}</p>
          </div>
          <button className="btn muted" onClick={onClose}>Close</button>
        </div>
        <div className="detail-toolbar">
          <label>
            Reading Status
            <select value={paper.status} onChange={(event) => onStatus(paper.id, event.target.value)}>
              <option>To Read</option>
              <option>Reading</option>
              <option>Completed</option>
            </select>
          </label>
          <span>{formatCitations(paper.citations)}</span>
        </div>
        <p className="detail-label">Abstract</p>
        <p className="detail-text">{paper.abstract}</p>
        <div className="tags">
          {paper.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <button className="btn primary" onClick={() => onSummary(paper.id)} disabled={busy}>
          <Sparkles size={16} /> {busy ? "Generating..." : "Generate Summary"}
        </button>
        <div className="smart-actions">
          <button className="btn muted" onClick={() => onInsights(paper.id)} disabled={insightsBusy}>
            {insightsBusy ? "Analyzing..." : "Paper Insight Panel"}
          </button>
          <button className="btn muted" onClick={() => onGap(paper.id)} disabled={gapBusy}>
            {gapBusy ? "Finding..." : "Find Research Gap"}
          </button>
        </div>
        {summary && (
          <>
            <p className="detail-label">AI Summary</p>
            <p className="detail-text summary-box">{summary}</p>
          </>
        )}
        {insights && (
          <>
            <p className="detail-label">Paper Insight Panel</p>
            <div className="insight-cards">
              <div className="insight-card"><strong>Objective</strong><span>{insights.objective}</span></div>
              <div className="insight-card"><strong>Methodology</strong><span>{insights.methodology}</span></div>
              <div className="insight-card"><strong>Dataset</strong><span>{insights.dataset}</span></div>
              <div className="insight-card"><strong>Key Findings</strong><span>{insights.key_findings}</span></div>
              <div className="insight-card"><strong>Limitations</strong><span>{insights.limitations}</span></div>
              <div className="insight-card"><strong>Future Scope</strong><span>{insights.future_scope}</span></div>
            </div>
          </>
        )}
        {gap && (
          <>
            <p className="detail-label">Research Gap Detection</p>
            <div className="gap-box">
              <p><strong>Gap:</strong> {gap.gap}</p>
              <p><strong>Opportunity:</strong> {gap.opportunity}</p>
              <p><strong>Possible Future Work Title:</strong> {gap.possible_title}</p>
            </div>
          </>
        )}
        <div className="detail-grid">
          <section>
            <p className="detail-label">Notes</p>
            <form className="mini-form" onSubmit={onAddNote}>
              <textarea
                value={noteText}
                onChange={(event) => setNoteText(event.target.value)}
                placeholder="Add a note for this paper..."
              />
              <button className="btn muted">Save Note</button>
            </form>
            <div className="note-list">
              {notes.length === 0 && <p className="empty-text">No notes yet.</p>}
              {notes.map((note) => (
                <div className="note-item" key={note.id}>
                  <p>{note.content}</p>
                  <button onClick={() => onDeleteNote(note.id)}>Delete</button>
                </div>
              ))}
            </div>
          </section>
          <section>
            <p className="detail-label">Chat With Paper</p>
            <form className="mini-form" onSubmit={onAskPaper}>
              <textarea
                value={chatQuestion}
                onChange={(event) => setChatQuestion(event.target.value)}
                placeholder="Ask a question about this paper..."
              />
              <button className="btn muted" disabled={chatBusy}>{chatBusy ? "Thinking..." : "Ask"}</button>
            </form>
            {paperChat && <p className="detail-text summary-box">{paperChat}</p>}
          </section>
        </div>
      </div>
    </div>
  );
}

function UploadModal({ onClose, onUploaded }) {
  const fileInput = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const paper = await uploadPaper(file);
      onUploaded(paper);
      onClose();
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h2>Upload Paper</h2>
        <p>Select a PDF paper to add it to your library.</p>
        <button className="upload-drop" onClick={() => fileInput.current?.click()} disabled={busy}>
          <Upload size={28} />
          {busy ? "Uploading..." : "Choose PDF"}
        </button>
        <input ref={fileInput} type="file" accept="application/pdf" onChange={handleUpload} hidden />
        {error && <p className="error">{error}</p>}
        <button className="btn muted" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [papers, setPapers] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [summaryText, setSummaryText] = useState("");
  const [summaryBusy, setSummaryBusy] = useState(false);
  const [insights, setInsights] = useState(null);
  const [gap, setGap] = useState(null);
  const [insightsBusy, setInsightsBusy] = useState(false);
  const [gapBusy, setGapBusy] = useState(false);
  const [notes, setNotes] = useState([]);
  const [noteText, setNoteText] = useState("");
  const [chatQuestion, setChatQuestion] = useState("");
  const [paperChat, setPaperChat] = useState("");
  const [chatBusy, setChatBusy] = useState(false);

  useEffect(() => {
    const modalOpen = showUpload || selectedPaper;
    document.body.classList.toggle("modal-open", Boolean(modalOpen));
    return () => document.body.classList.remove("modal-open");
  }, [showUpload, selectedPaper]);

  async function refresh() {
    const [paperData, recommendationData] = await Promise.all([getPapers(), getRecommendations()]);
    setPapers(paperData);
    setRecommendations(recommendationData);
  }

  useEffect(() => {
    refresh().catch(console.error);
  }, []);

  async function searchPapers(value) {
    const data = await getPapers({ q: value });
    setPapers(data);
  }

  async function handleStatus(id, status) {
    const updated = await updatePaperStatus(id, status);
    if (selectedPaper?.id === id) {
      setSelectedPaper(updated);
    }
    refresh();
  }

  async function handleDelete(id) {
    await deletePaper(id);
    refresh();
  }

  async function handleSummary(paperOrId) {
    const id = typeof paperOrId === "object" ? paperOrId.id : paperOrId;
    if (typeof paperOrId === "object") {
      setSelectedPaper(paperOrId);
      setSummaryText(paperOrId.summary || "");
    }
    setSummaryBusy(true);
    try {
      const result = await summarizePaper(id);
      setSummaryText(result.summary);
    } finally {
      setSummaryBusy(false);
    }
  }

  function handleView(paper) {
    setSelectedPaper(paper);
    setSummaryText(paper.summary || "");
    setInsights(null);
    setGap(null);
    setNoteText("");
    setChatQuestion("");
    setPaperChat("");
    getNotes(paper.id).then(setNotes).catch(console.error);
  }

  async function handleInsights(id) {
    setInsightsBusy(true);
    try {
      setInsights(await getPaperInsights(id));
    } finally {
      setInsightsBusy(false);
    }
  }

  async function handleGap(id) {
    setGapBusy(true);
    try {
      setGap(await getResearchGap(id));
    } finally {
      setGapBusy(false);
    }
  }

  async function handleAddNote(event) {
    event.preventDefault();
    if (!selectedPaper || !noteText.trim()) return;
    await createNote(selectedPaper.id, noteText);
    setNoteText("");
    setNotes(await getNotes(selectedPaper.id));
  }

  async function handleDeleteNote(id) {
    if (!selectedPaper) return;
    await deleteNote(id);
    setNotes(await getNotes(selectedPaper.id));
  }

  async function handleAskPaper(event) {
    event.preventDefault();
    if (!selectedPaper || !chatQuestion.trim()) return;
    setChatBusy(true);
    try {
      const response = await sendChat(chatQuestion, selectedPaper.id);
      setPaperChat(response.answer);
    } finally {
      setChatBusy(false);
    }
  }

  const pages = {
    Dashboard: <Dashboard papers={papers} onUploadClick={() => setShowUpload(true)} onView={handleView} />,
    "Search Papers": <SearchPapers papers={papers} query={query} setQuery={setQuery} onSearch={searchPapers} onStatus={handleStatus} onView={handleView} />,
    "My Papers": <MyPapers papers={papers} filter={filter} setFilter={setFilter} onDelete={handleDelete} onSummary={handleSummary} onView={handleView} />,
    "AI Assistant": <Assistant />,
    Recommendations: <Recommendations recommendations={recommendations} onStatus={handleStatus} onView={handleView} />,
    "Literature Review": <LiteratureReview papers={papers} />,
    Settings: <SettingsPage />,
  };

  return (
    <Shell activePage={activePage} setActivePage={setActivePage}>
      {pages[activePage]}
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onUploaded={refresh} />}
      {selectedPaper && (
        <PaperDetailModal
          paper={selectedPaper}
          summary={summaryText}
          insights={insights}
          gap={gap}
          busy={summaryBusy}
          insightsBusy={insightsBusy}
          gapBusy={gapBusy}
          notes={notes}
          noteText={noteText}
          setNoteText={setNoteText}
          chatQuestion={chatQuestion}
          setChatQuestion={setChatQuestion}
          paperChat={paperChat}
          chatBusy={chatBusy}
          onClose={() => setSelectedPaper(null)}
          onSummary={handleSummary}
          onInsights={handleInsights}
          onGap={handleGap}
          onStatus={handleStatus}
          onAddNote={handleAddNote}
          onDeleteNote={handleDeleteNote}
          onAskPaper={handleAskPaper}
        />
      )}
    </Shell>
  );
}
