import { useState } from 'react'
import { documentsMockApi } from '../api/documentsMockApi.js'
import StatusBadge from '../components/StatusBadge.jsx'
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

  async function search() {
    setBusy(true)
    try {
      const rows = await documentsMockApi.listDocuments({
        query,
        department_id: departmentId,
        document_type_id: documentTypeId,
        rag_status: ragStatus,
        review_status: reviewStatus,
      })
      setResults(rows)
      setSearched(true)
    } finally {
      setBusy(false)
    }
  }

  if (!searched && results === null && !busy) {
    search()
  }

  const deptName = (id) => departments.find((d) => d.id === id)?.name || id
  const typeName = (id) => documentTypes.find((t) => t.id === id)?.name || id

  return (
    <>
      <div className="page-head">
        <h1>Quản lý tài liệu</h1>
        <p>Tìm kiếm tài liệu đã tải lên và sửa thông tin. Thay đổi sẽ được đồng bộ vào PostgreSQL và Qdrant.</p>
      </div>

      <div className="card">
        <h2>Tìm kiếm</h2>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Từ khoá</span>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && search()}
                placeholder="Tiêu đề, document_key, số hiệu…"
              />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Phòng ban</span>
              <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                <option value="">— Tất cả —</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Loại tài liệu</span>
              <select value={documentTypeId} onChange={(e) => setDocumentTypeId(e.target.value)}>
                <option value="">— Tất cả —</option>
                {documentTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
          </div>
        </div>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Trạng thái duyệt</span>
              <select value={reviewStatus} onChange={(e) => setReviewStatus(e.target.value)}>
                <option value="">— Tất cả —</option>
                {reviewStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Trạng thái RAG</span>
              <select value={ragStatus} onChange={(e) => setRagStatus(e.target.value)}>
                <option value="">— Tất cả —</option>
                {ragStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <div className="col" style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button className="btn" style={{ marginBottom: 12 }} disabled={busy} onClick={search}>
              {busy ? 'Đang tìm…' : 'Tìm kiếm'}
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Kết quả {results ? `(${results.length})` : ''}</h2>
        {results && results.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Tiêu đề</th>
                <th>Loại</th>
                <th>Phòng ban</th>
                <th>Version / Hiệu lực</th>
                <th>OCR</th>
                <th>Duyệt</th>
                <th>RAG</th>
                <th>Cập nhật lúc</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {results.map((d) => (
                <tr key={d.id}>
                  <td>
                    <div>{d.title}</div>
                    <div className="mono muted" style={{ fontSize: 11 }}>{d.document_key}</div>
                  </td>
                  <td>{typeName(d.document_type_id)}</td>
                  <td>{deptName(d.department_id)}</td>
                  <td>
                    <div className="mono">{d.version_label || '—'}</div>
                    <StatusBadge status={d.validity_status} />
                  </td>
                  <td><StatusBadge status={d.ocr_status} /></td>
                  <td><StatusBadge status={d.review_status} /></td>
                  <td><StatusBadge status={d.rag_status} /></td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {new Date(d.updated_at).toLocaleString('vi-VN')}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn ghost small" onClick={() => onEdit(d.id)}>Sửa</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="hint">{busy ? 'Đang tìm kiếm…' : 'Không có tài liệu phù hợp.'}</p>
        )}
      </div>
    </>
  )
}
