import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import PageHeader from '../components/PageHeader.jsx'
import { documentTypes, departments, ragStatuses, reviewStatuses } from '../api/referenceData.js'

export default function DocumentsListPage({ onEdit }) {
  const [query, setQuery] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [documentTypeId, setDocumentTypeId] = useState('')
  const [ragStatus, setRagStatus] = useState('')
  const [reviewStatus, setReviewStatus] = useState('')
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [searched, setSearched] = useState(false)

  useEffect(() => {
    let cancelled = false
    setBusy(true)
    api.listDocuments().then((rows) => {
      if (!cancelled) {
        setResults(rows.items || rows)
        setSearched(true)
      }
    }).finally(() => {
      if (!cancelled) setBusy(false)
    })
    return () => { cancelled = true }
  }, [])

  async function search() {
    setBusy(true)
    try {
      const rows = await api.listDocuments({
        query,
        department_id: departmentId,
        document_type_id: documentTypeId,
        rag_status: ragStatus,
        review_status: reviewStatus,
      })
      setResults(rows.items || rows)
      setSearched(true)
    } finally {
      setBusy(false)
    }
  }

  const deptName = (id) => departments.find((d) => d.id === id)?.name || id
  const typeName = (id) => documentTypes.find((t) => t.id === id)?.name || id

  return (
    <>
      <PageHeader
        eyebrow="Documents"
        title="Quản lý tài liệu"
        description="Tìm kiếm tài liệu đã tải lên và sửa metadata/canonical Markdown. Chunk và Qdrant được xử lý ở workflow Index."
      />

      <form className="card" onSubmit={(event) => { event.preventDefault(); search() }}>
        <fieldset className="filter-grid">
          <legend>Tìm kiếm tài liệu</legend>
          <label className="field">
            <span>Từ khoá</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tiêu đề, document_key, số hiệu…" />
          </label>
          <label className="field">
            <span>Phòng ban</span>
            <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="">— Tất cả —</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Loại tài liệu</span>
            <select value={documentTypeId} onChange={(e) => setDocumentTypeId(e.target.value)}>
              <option value="">— Tất cả —</option>
              {documentTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Trạng thái duyệt</span>
            <select value={reviewStatus} onChange={(e) => setReviewStatus(e.target.value)}>
              <option value="">— Tất cả —</option>
              {reviewStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Trạng thái RAG</span>
            <select value={ragStatus} onChange={(e) => setRagStatus(e.target.value)}>
              <option value="">— Tất cả —</option>
              {ragStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <button type="submit" className="btn filter-submit" disabled={busy}>
            {busy ? 'Đang tìm…' : 'Tìm kiếm'}
          </button>
        </fieldset>
      </form>

      <section className="card" aria-labelledby="document-results-heading">
        <h2 id="document-results-heading">Kết quả {results ? `(${results.length})` : ''}</h2>
        {results && results.length > 0 ? (
          <div className="table-scroll">
          <table>
            <caption>Danh sách phiên bản tài liệu phù hợp bộ lọc</caption>
            <thead>
              <tr>
                <th scope="col">Tiêu đề</th>
                <th scope="col">Loại</th>
                <th scope="col">Phòng ban</th>
                <th scope="col">Version / Hiệu lực</th>
                <th scope="col">OCR</th>
                <th scope="col">Duyệt</th>
                <th scope="col">RAG</th>
                <th scope="col">Cập nhật lúc</th>
                <th scope="col"><span className="sr-only">Thao tác</span></th>
              </tr>
            </thead>
            <tbody>
              {results.map((d) => (
                <tr key={d.id}>
                  <td>
                    <strong>{d.title}</strong>
                    <small className="document-key mono muted">{d.document_key}</small>
                  </td>
                  <td>{typeName(d.document_type_id)}</td>
                  <td>{deptName(d.department_id)}</td>
                  <td>
                    <span className="document-version mono">{d.version_label || '—'}</span>
                    <StatusBadge status={d.validity_status} />
                  </td>
                  <td><StatusBadge status={d.ocr_status} /></td>
                  <td><StatusBadge status={d.review_status} /></td>
                  <td><StatusBadge status={d.rag_status} /></td>
                  <td className="mono">
                    <time dateTime={d.updated_at}>{new Date(d.updated_at).toLocaleString('vi-VN')}</time>
                  </td>
                  <td className="table-action">
                    <button type="button" className="btn ghost small" onClick={() => onEdit(d.id)}>Sửa</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        ) : (
          <p className="hint">{busy ? 'Đang tìm kiếm…' : 'Không có tài liệu phù hợp.'}</p>
        )}
      </section>
    </>
  )
}
