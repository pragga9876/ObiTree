const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export { API_BASE };

export function fileUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function readError(response, fallback) {
  try {
    const data = await response.json();
    return data?.detail || data?.message || fallback;
  } catch {
    return fallback;
  }
}

export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function listProjects() {
  const response = await fetch(`${API_BASE}/api/projects`);
  if (!response.ok) {
    throw new Error(await readError(response, "Could not load the archive"));
  }
  const data = await response.json();
  return data.projects || [];
}

export async function getProject(projectId) {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}`);
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

  const response = await fetch(`${API_BASE}/api/documents`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readError(response, `Upload failed with status ${response.status}`));
  }

  return response.json();
}

export async function getDocument(documentId) {
  const response = await fetch(`${API_BASE}/api/documents/${documentId}`);
  if (!response.ok) {
    throw new Error(await readError(response, "Could not load the clipping"));
  }
  return response.json();
}

export async function getCanonicalRecord(recordId) {
  const response = await fetch(`${API_BASE}/api/records/${recordId}`);
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
  const response = await fetch(`${API_BASE}/api/attestations`, {
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
