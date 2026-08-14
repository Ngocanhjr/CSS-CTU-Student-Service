const DEFAULT_PRODUCTION_API_URL =
  "https://css-ctu-student-service-api.onrender.com";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? DEFAULT_PRODUCTION_API_URL : "")
).replace(/\/$/, "");

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
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

  uploadCanonicalMarkdown(file, sourceFile, sourceDepartmentCode, metadata) {
    const body = new FormData();
    body.append("file", file);
    body.append("source_department_code", sourceDepartmentCode);
    body.append("metadata_json", JSON.stringify(metadata));
    if (sourceFile) body.append("source_file", sourceFile);
    return request("/api/v1/admin/canonical-markdown", {
      method: "POST",
      body,
    });
  },

  previewMarkdownMetadata(file) {
    const body = new FormData();
    body.append("file", file);
    return request("/api/v1/admin/canonical-markdown/metadata-preview", {
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

  reviewCanonicalMarkdown(versionId, markdownBody, metadata, assets) {
    return request(`/api/v1/admin/canonical-markdown/${versionId}/review`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown_body: markdownBody, metadata, assets }),
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

  getDocumentPreviewUrl(versionKey, fileType = "canonical_markdown") {
    const query = new URLSearchParams({ file_type: fileType });
    return request(
      `/api/v1/versions/preview-url/${encodeURIComponent(versionKey)}?${query}`,
    );
  },

  updateDocument(versionId, payload) {
    return request(`/api/v1/versions/${versionId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  updateDocumentAssets(versionId, assets) {
    return request(`/api/v1/versions/${versionId}/assets`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assets }),
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
