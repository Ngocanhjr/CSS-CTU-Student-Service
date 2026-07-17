import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
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
  const [result, setResult] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.getDocument(documentId).then((d) => {
      if (cancelled) return
      setDoc(d)
      setForm(d ? toForm(d) : null)
      setMarkdown(d ? d.canonical_markdown : '')
      setLoading(false)
    }).catch(() => {
      if (!cancelled) {
        setDoc(null)
        setLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [documentId])

  if (loading) {
    return (
      <>
        <header className="page-head"><h1>Sửa tài liệu</h1></header>
        <p className="hint" role="status">Đang tải…</p>
      </>
    )
  }

  if (!doc) {
    return (
      <>
        <header className="page-head"><h1>Sửa tài liệu</h1></header>
        <aside className="banner warn">
          Không tìm thấy tài liệu.
          <p><button type="button" className="btn small" onClick={onBack}>← Quay lại danh sách</button></p>
        </aside>
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

  async function onSave() {
    setBusy(true)
    setResult(null)
    try {
      const res = await api.updateDocument(
        documentId,
        { metadata: form, canonical_markdown: markdown },
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
      <header className="page-head">
        <h1>Sửa tài liệu</h1>
        <p className="mono muted">{doc.document_key} — {doc.version_key}</p>
      </header>

      <form onSubmit={(event) => { event.preventDefault(); onSave() }}>
      <section className="card" aria-labelledby="current-status-heading">
        <h2 id="current-status-heading">Trạng thái hiện tại</h2>
        <dl className="kv">
          <dt>OCR</dt><dd><StatusBadge status={doc.ocr_status} /></dd>
          <dt>Hiệu lực</dt>
          <dd>
            <select aria-label="Tình trạng hiệu lực" value={form.validity_status} onChange={(e) => set('validity_status', e.target.value)}>
              {VALIDITY_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </dd>
          <dt>Duyệt nội dung</dt>
          <dd>
            <select aria-label="Trạng thái duyệt nội dung" value={form.review_status} onChange={(e) => set('review_status', e.target.value)}>
              {reviewStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </dd>
          <dt>RAG</dt><dd><StatusBadge status={doc.rag_status} /></dd>
        </dl>
        <p className="hint">OCR và RAG là kết quả của pipeline tự động, không sửa trực tiếp ở đây.</p>
      </section>

      <section className="card" aria-labelledby="document-information-heading">
        <h2 id="document-information-heading">Thông tin tài liệu</h2>
        <fieldset className="form-grid">
          <legend className="sr-only">Thông tin phân loại tài liệu</legend>
            <label className="field">
              <span>Tiêu đề *</span>
              <input value={form.title} onChange={(e) => set('title', e.target.value)} />
            </label>
            <label className="field">
              <span>Loại tài liệu *</span>
              <select value={form.document_type_id} onChange={(e) => set('document_type_id', Number(e.target.value))}>
                {documentTypes.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.code})</option>)}
              </select>
            </label>
        </fieldset>
        <fieldset className="form-grid">
          <legend className="sr-only">Đơn vị và lĩnh vực tài liệu</legend>
            <label className="field">
              <span>Phòng ban</span>
              <select value={form.department_id} onChange={(e) => set('department_id', Number(e.target.value))}>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.code})</option>)}
              </select>
            </label>
            <label className="field">
              <span>Domain</span>
              <select value={form.domain} onChange={(e) => set('domain', e.target.value)}>
                <option value="">— chọn —</option>
                {domainOptions.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
        </fieldset>
        <fieldset className="audience-fieldset">
          <legend>Audience (JSONB)</legend>
          <menu className="pill-row">
            {audienceOptions.map((a) => (
              <li key={a}>
                <button
                  type="button"
                  className="tag"
                  aria-pressed={form.audience.includes(a)}
                  onClick={() => toggleAudience(a)}
                >
                  {form.audience.includes(a) ? '✓ ' : ''}{a}
                </button>
              </li>
            ))}
          </menu>
        </fieldset>
      </section>

      <section className="card" aria-labelledby="version-information-heading">
        <h2 id="version-information-heading">Thông tin version</h2>
        <fieldset className="form-grid">
          <legend className="sr-only">Số hiệu và nhãn phiên bản</legend>
            <label className="field">
              <span>Số hiệu (code)</span>
              <input value={form.code || ''} onChange={(e) => set('code', e.target.value)} />
            </label>
            <label className="field">
              <span>Nhãn version</span>
              <input value={form.version_label || ''} onChange={(e) => set('version_label', e.target.value)} />
            </label>
        </fieldset>
        <fieldset className="form-grid three-columns">
          <legend className="sr-only">Mốc thời gian phiên bản</legend>
            <label className="field">
              <span>Ngày ban hành</span>
              <input type="date" value={form.issued_date || ''} onChange={(e) => set('issued_date', e.target.value)} />
            </label>
            <label className="field">
              <span>Ngày hiệu lực</span>
              <input type="date" value={form.effective_date || ''} onChange={(e) => set('effective_date', e.target.value)} />
            </label>
            <label className="field">
              <span>Ngày hết hiệu lực</span>
              <input type="date" value={form.expiry_date || ''} onChange={(e) => set('expiry_date', e.target.value)} />
            </label>
        </fieldset>
      </section>

      <section className="card" aria-labelledby="canonical-markdown-heading">
        <h2 id="canonical-markdown-heading">Nội dung canonical Markdown</h2>
        <label className="field" htmlFor="document-markdown">Canonical Markdown và YAML frontmatter</label>
        <textarea
          id="document-markdown"
          className="markdown-editor"
          value={markdown}
          onChange={(e) => setMarkdown(e.target.value)}
        />
        <p className="hint">Sửa nội dung sẽ kích hoạt chunk lại, embed lại và cập nhật Qdrant khi lưu.</p>
      </section>

      {result && !result.updated && (
        <p className="banner" role="status">Không có thay đổi nào để lưu.</p>
      )}
      {result?.updated && (
        <p className="banner" role="status">
          Đã lưu và đồng bộ thành công. Cập nhật lúc {new Date(result.document.updated_at).toLocaleString('vi-VN')}.
        </p>
      )}

      <footer className="foot-nav">
        <button type="button" className="btn ghost" onClick={onBack}>← Quay lại danh sách</button>
        <button type="submit" className="btn" disabled={!valid || busy}>
          {busy ? 'Đang lưu…' : 'Lưu & đồng bộ'}
        </button>
      </footer>
      </form>
    </>
  )
}
