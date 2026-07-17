async function request(path, options) {
  const response = await fetch(path, options)
  const text = await response.text()
  const data = text && response.headers.get('content-type')?.includes('application/json')
    ? JSON.parse(text)
    : text

  if (!response.ok) {
    throw new Error(data?.detail || data || `HTTP ${response.status}`)
  }
  return data
}

export const api = {
  uploadCanonicalMarkdown(file) {
    const body = new FormData()
    body.append('file', file)
    return request('/api/v1/admin/canonical-markdown', { method: 'POST', body })
  },

  runIngest(versionId) {
    return request(`/api/v1/versions/${versionId}/ingest`, { method: 'POST' })
  },

  reviewCanonicalMarkdown(versionId, canonicalMarkdown) {
    return request(`/api/v1/versions/${versionId}/review`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ canonical_markdown: canonicalMarkdown }),
    })
  },

  listDocuments(filters = {}) {
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => value !== '' && value != null),
    )
    return request(`/api/v1/versions?${query}`)
  },

  getDocument(versionId) {
    return request(`/api/v1/versions/${versionId}`)
  },

  updateDocument(versionId, payload) {
    return request(`/api/v1/versions/${versionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
}
