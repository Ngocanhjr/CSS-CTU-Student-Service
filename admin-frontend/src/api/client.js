async function request(path, options) {
  const response = await fetch(path, options);
  const text = await response.text();
  const data =
    text && response.headers.get("content-type")?.includes("application/json")
      ? JSON.parse(text)
      : text;

  if (!response.ok) {
    const detail = data?.detail ?? data;
    if (detail && typeof detail === "object") {
      const rawFields = detail.fields || (Array.isArray(detail) ? detail : []);
      const fields = rawFields
        .map(
          (field) =>
            `${field.field || field.loc?.join(".")}: ${field.message || field.msg}`,
        )
        .join("; ");
      throw new Error([detail.message, fields].filter(Boolean).join(" — "));
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return data;
}

export const api = {
  getDatabaseHealth() {
    return request("/api/v1/health/database");
  },

  uploadCanonicalMarkdown(file) {
    const body = new FormData();
    body.append("file", file);
    return request("/api/v1/admin/canonical-markdown", {
      method: "POST",
      body,
    });
  },

  indexDocumentVersion(versionId) {
    return request(`/api/v1/admin/document-versions/${versionId}/index`, {
      method: "POST",
    });
  },

  getIndexingJob(jobId) {
    return request(`/api/v1/admin/ingestion-jobs/${jobId}`);
  },

  reviewCanonicalMarkdown(versionId, canonicalMarkdown) {
    return request(`/api/v1/admin/canonical-markdown/${versionId}/review`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ canonical_markdown: canonicalMarkdown }),
    });
  },

  previewChunks(versionId) {
    return request(
      `/api/v1/admin/document-versions/${versionId}/chunk-preview`,
      { method: "POST" },
    );
  },

  listDocuments(filters = {}) {
    const query = new URLSearchParams(
      Object.entries(filters).filter(
        ([, value]) => value !== "" && value != null,
      ),
    );
    return request(`/api/v1/versions?${query}`);
  },

  getDocument(versionId) {
    return request(`/api/v1/versions/${versionId}`);
  },

  updateDocument(versionId, payload) {
    return request(`/api/v1/versions/${versionId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  deleteDocument(versionId) {
    return request(`/api/v1/versions/${versionId}`, { method: "DELETE" });
  },

  publishDocument(versionId) {
    return request(`/api/v1/versions/${versionId}/publish`, { method: "POST" });
  },

  unpublishDocument(versionId) {
    return request(`/api/v1/versions/${versionId}/unpublish`, {
      method: "POST",
    });
  },

  deindexDocument(versionId) {
    return request(`/api/v1/versions/${versionId}/deindex`, { method: "POST" });
  },

  getDocumentTypes() {
    return request("/api/v1/reference/document-types");
  },

  getDepartments() {
    return request("/api/v1/reference/departments");
  },
  
  getEnumOptions() {
    return request("/api/v1/reference/enums");
  },
};
