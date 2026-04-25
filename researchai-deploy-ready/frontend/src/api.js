const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}

export function getPapers(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.set(key, value);
  });
  const suffix = search.toString() ? `?${search}` : "";
  return request(`/papers${suffix}`);
}

export function getRecommendations() {
  return request("/recommendations");
}

export function uploadPaper(file) {
  const body = new FormData();
  body.append("file", file);
  return request("/papers/upload", {
    method: "POST",
    body,
  });
}

export function updatePaperStatus(id, status) {
  return request(`/papers/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export function deletePaper(id) {
  return request(`/papers/${id}`, { method: "DELETE" });
}

export function summarizePaper(id) {
  return request(`/papers/${id}/summary`, { method: "POST" });
}

export function getPaperInsights(id) {
  return request(`/papers/${id}/insights`);
}

export function getResearchGap(id) {
  return request(`/papers/${id}/research-gap`);
}

export function generateLiteratureReview(paperIds = []) {
  return request("/literature-review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paper_ids: paperIds }),
  });
}

export function getNotes(paperId) {
  return request(`/papers/${paperId}/notes`);
}

export function createNote(paperId, content) {
  return request(`/papers/${paperId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function deleteNote(id) {
  return request(`/notes/${id}`, { method: "DELETE" });
}

export function sendChat(message, paperId = null) {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, paper_id: paperId }),
  });
}
