const CONFIGURED_BASE = (import.meta.env.VITE_API_URL || "").trim().replace(/\/$/, "");
const DEV_BASE = "http://localhost:8000";

// A deployed build must never silently talk to localhost.
export const API_BASE = CONFIGURED_BASE || (import.meta.env.DEV ? DEV_BASE : "");

function apiUrl(path) {
  if (!API_BASE) {
    throw new Error(
      "The backend URL is not configured. Set VITE_API_URL for this deployment."
    );
  }
  return `${API_BASE}${path}`;
}

export function fileUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function readError(response, fallback) {
  try {
    const data = await response.json();
    const detail = data?.detail ?? data?.message;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      return detail.message || JSON.stringify(detail);
    }
    return fallback;
  } catch {
    return fallback;
  }
}

export async function checkHealth() {
  const response = await fetch(apiUrl("/health"));
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function listProjects() {
  const response = await fetch(apiUrl("/api/projects"));
  if (!response.ok) {
    throw new Error(await readError(response, "Could not load the archive"));
  }
  const data = await response.json();
  return data.projects || [];
}

export async function getProject(projectId) {
  const response = await fetch(apiUrl(`/api/projects/${projectId}`));
  if (!response.ok) {
    throw new Error(await readError(response, "Could not load this chronicle"));
  }
  return response.json();
}

export async function uploadDocument(file, { projectId, wallet } = {}) {
  const formData = new FormData();
  formData.append("file", file);
  if (projectId) formData.append("project_id", projectId);
  if (wallet) formData.append("wallet", wallet);

  const response = await fetch(apiUrl("/api/documents"), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readError(response, `Upload failed with status ${response.status}`));
  }

  return response.json();
}

export async function getDocument(documentId) {
  const response = await fetch(apiUrl(`/api/documents/${documentId}`));
  if (!response.ok) {
    throw new Error(await readError(response, "Could not load the clipping"));
  }
  return response.json();
}

export async function getCanonicalRecord(recordId) {
  const response = await fetch(apiUrl(`/api/records/${recordId}`));
  if (!response.ok) {
    throw new Error(await readError(response, `Failed to fetch record ${recordId}`));
  }
  return response.json();
}

export async function submitAttestation({
  documentId,
  version = 1,
  transactionSignature,
  wallet,
  network = "devnet",
}) {
  const response = await fetch(apiUrl("/api/attestations"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_id: documentId,
      version,
      transaction_signature: transactionSignature,
      wallet,
      network,
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "Attestation failed"));
  }

  return response.json();
}
