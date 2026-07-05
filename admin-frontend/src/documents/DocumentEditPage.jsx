import { useEffect, useState } from 'react'
import { documentsMockApi } from '../api/documentsMockApi.js'
import StatusBadge from '../components/StatusBadge.jsx'
import StepProgress from '../components/StepProgress.jsx'
import {
  documentTypes,
  departments,
  audienceOptions,
  domainOptions,
  reviewStatuses,
} from '../api/referenceData.js'

const VALIDITY_STATUSES = ['unchecked', 'valid', 'expired', 'replaced', 'unknown']

function toForm(doc) {
  return {
    title: doc.title,
    document_type_id: doc.document_type_id,
    department_id: doc.department_id,
    domain: doc.domain,
    audience: [...doc.audience],
    code: doc.code,
    version_label: doc.version_label,
    issued_date: doc.issued_date,
    effective_date: doc.effective_date,
    expiry_date: doc.expiry_date,
    review_status: doc.review_status,
    validity_status: doc.validity_status,
  }
}

export default function DocumentEditPage({ documentId, onBack }) {
  const [doc, setDoc] = useState(null)
  const [form, setForm] = useState(null)
  const [markdown, setMarkdown] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [steps, setSteps] = useState([])
  const [result, setResult] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    documentsMockApi.getDocument(documentId).then((d) => {
      if (cancelled) return
      setDoc(d)
      setForm(d ? toForm(d) : null)
      setMarkdown(d ? d.canonical_markdown : '')
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [documentId])

  if (loading) {
    return (
      <>
        <div className="page-head"><h1>Sửa tài liệu</h1></div>
        <p className="hint">Đang tải…</p>
      </>
    )
  }

  if (!doc) {
    return (
      <>
        <div className="page-head"><h1>Sửa tài liệu</h1></div>
        <div className="banner warn">
          Không tìm thấy tài liệu.
          <div style={{ marginTop: 10 }}>
            <button className="btn small" onClick={onBack}>← Quay lại danh sách</button>
          </div>
        </div>
      </>
    )
  }

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function toggleAudience(a) {
    setForm((f) => ({
      ...f,
      audience: f.audience.includes(a) ? f.audience.filter((x) => x !== a) : [...f.audience, a],
    }))
  }

  function onStep(step) {
    setSteps((prev) => {
      const exists = prev.some((s) => s.key === step.key)
      if (!exists) return [...prev, step]
      return prev.map((s) => (s.key === step.key ? { ...s, ...step } : s))
    })
  }

  async function onSave() {
    setBusy(true)
    setSteps([])
    setResult(null)
    try {
      const res = await documentsMockApi.updateDocument(
        documentId,
        { metadata: form, canonical_markdown: markdown },
        onStep,
      )
      setDoc(res.document)
      setForm(toForm(res.document))
      setMarkdown(res.document.canonical_markdown)
      setResult(res)
    } finally {
      setBusy(false)
    }
  }

  const valid = form.title.trim() && form.document_type_id

  return (
    <>
      <div className="page-head">
        <h1>Sửa tài liệu</h1>
        <p className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>{doc.document_key} — {doc.version_key}</p>
      </div>

      <div className="card">
        <h2>Trạng thái hiện tại</h2>
        <dl className="kv">
          <dt>OCR</dt><dd><StatusBadge status={doc.ocr_status} /></dd>
          <dt>Hiệu lực</dt>
          <dd>
            <select value={form.validity_status} onChange={(e) => set('validity_status', e.target.value)}>
              {VALIDITY_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </dd>
          <dt>Duyệt nội dung</dt>
          <dd>
            <select value={form.review_status} onChange={(e) => set('review_status', e.target.value)}>
              {reviewStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </dd>
          <dt>RAG</dt><dd><StatusBadge status={doc.rag_status} /></dd>
        </dl>
        <p className="hint">OCR và RAG là kết quả của pipeline tự động, không sửa trực tiếp ở đây.</p>
      </div>

      <div className="card">
        <h2>Thông tin tài liệu</h2>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Tiêu đề *</span>
              <input value={form.title} onChange={(e) => set('title', e.target.value)} />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Loại tài liệu *</span>
              <select value={form.document_type_id} onChange={(e) => set('document_type_id', Number(e.target.value))}>
                {documentTypes.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.code})</option>)}
              </select>
            </label>
          </div>
        </div>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Phòng ban</span>
              <select value={form.department_id} onChange={(e) => set('department_id', Number(e.target.value))}>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.code})</option>)}
              </select>
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Domain</span>
              <select value={form.domain} onChange={(e) => set('domain', e.target.value)}>
                <option value="">— chọn —</option>
                {domainOptions.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
          </div>
        </div>
        <label className="field">
          <span>Audience (JSONB)</span>
          <div className="pill-row">
            {audienceOptions.map((a) => (
              <button
                key={a}
                type="button"
                className="tag"
                style={{ borderColor: form.audience.includes(a) ? 'var(--accent)' : 'var(--border)' }}
                onClick={() => toggleAudience(a)}
              >
                {form.audience.includes(a) ? '✓ ' : ''}{a}
              </button>
            ))}
          </div>
        </label>
      </div>

      <div className="card">
        <h2>Thông tin version</h2>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Số hiệu (code)</span>
              <input value={form.code || ''} onChange={(e) => set('code', e.target.value)} />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Nhãn version</span>
              <input value={form.version_label || ''} onChange={(e) => set('version_label', e.target.value)} />
            </label>
          </div>
        </div>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Ngày ban hành</span>
              <input type="date" value={form.issued_date || ''} onChange={(e) => set('issued_date', e.target.value)} />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Ngày hiệu lực</span>
              <input type="date" value={form.effective_date || ''} onChange={(e) => set('effective_date', e.target.value)} />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Ngày hết hiệu lực</span>
              <input type="date" value={form.expiry_date || ''} onChange={(e) => set('expiry_date', e.target.value)} />
            </label>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Nội dung canonical markdown</h2>
        <textarea
          style={{ minHeight: 260 }}
          value={markdown}
          onChange={(e) => setMarkdown(e.target.value)}
        />
        <p className="hint">Sửa nội dung sẽ kích hoạt chunk lại, embed lại và cập nhật Qdrant khi lưu.</p>
      </div>

      {(busy || steps.length > 0) && (
        <div className="card">
          <h2>Đồng bộ dữ liệu</h2>
          <StepProgress steps={steps} />
        </div>
      )}

      {result && !result.updated && (
        <div className="banner">Không có thay đổi nào để lưu.</div>
      )}
      {result?.updated && (
        <div className="banner">
          Đã lưu và đồng bộ thành công. Cập nhật lúc {new Date(result.document.updated_at).toLocaleString('vi-VN')}.
        </div>
      )}

      <div className="foot-nav">
        <button className="btn ghost" onClick={onBack}>← Quay lại danh sách</button>
        <button className="btn" disabled={!valid || busy} onClick={onSave}>
          {busy ? 'Đang lưu…' : 'Lưu & đồng bộ'}
        </button>
      </div>
    </>
  )
}
