const API_BASE = "http://localhost:8000";

export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/documents`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errorDetail = `Upload failed with status ${response.status}`;
    try {
      const data = await response.json();
      if (data && (data.detail || data.message)) {
        errorDetail = data.detail || data.message;
      }
    } catch {
      // response is not JSON
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getCanonicalRecord(recordId) {
  const response = await fetch(`${API_BASE}/api/records/${recordId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch record ${recordId}`);
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
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      document_id: documentId,
      version,
      transaction_signature: transactionSignature,
      wallet,
      network,
    }),
  });

  if (!response.ok) {
    let errMessage = "Attestation failed";
    try {
      const errData = await response.json();
      errMessage = errData.detail || errData.message || errMessage;
    } catch {
      // fallback
    }
    throw new Error(errMessage);
  }

  return response.json();
}
