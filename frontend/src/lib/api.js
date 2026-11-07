export async function checkHealth() {
  const response = await fetch("http://localhost:8000/health");
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("http://localhost:8000/api/documents", {
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
