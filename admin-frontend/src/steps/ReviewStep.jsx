import { useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'

export default function ReviewStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const [markdown, setMarkdown] = useState(upload?.markdown || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!upload) {
    return (
      <>
        <header className="page-head"><h1>2 — Review nội dung</h1></header>
        <aside className="banner warn">
          Chưa có canonical Markdown.
          <p><button type="button" className="btn small" onClick={() => goTo('upload')}>← Tải Markdown</button></p>
        </aside>
      </>
    )
  }

  async function saveReview() {
    setBusy(true)
    setError('')
    try {
      const reviewed = await api.reviewCanonicalMarkdown(upload.document_version_id, markdown)
      update('upload', { ...upload, ...reviewed, markdown: reviewed.markdown || markdown })
      update('review', reviewed)
      update('ingest', null)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="page-head">
        <h1>2 — Review canonical Markdown</h1>
        <p>Chỉnh nội dung và YAML trước chunking. Lưu review sẽ validate lại trên backend.</p>
      </header>

      {error && <p className="banner warn" role="alert">{error}</p>}

      <section className="card" aria-labelledby="review-status-heading">
        <h2 id="review-status-heading">Trạng thái</h2>
        <dl className="kv">
          <dt>version_key</dt><dd className="mono">{upload.version_key}</dd>
          <dt>ocr_status</dt><dd><StatusBadge status={upload.ocr_status} /></dd>
          <dt>review_status</dt><dd><StatusBadge status={pipeline.review?.review_status || upload.review_status} /></dd>
        </dl>
      </section>

      <section className="card" aria-labelledby="review-content-heading">
        <h2 id="review-content-heading">Nội dung cần review</h2>
        <label className="field" htmlFor="canonical-markdown">
          <span>Canonical Markdown và YAML frontmatter</span>
          <textarea
            id="canonical-markdown"
            className="markdown-editor large"
            value={markdown}
            onChange={(event) => setMarkdown(event.target.value)}
          />
        </label>
        <nav className="foot-nav" aria-label="Điều hướng review">
          <button type="button" className="btn ghost" onClick={() => goTo('upload')}>← Tải lại file</button>
          <button type="button" className="btn" disabled={busy || !markdown.trim()} onClick={saveReview}>
            {busy ? 'Đang lưu review…' : 'Lưu review'}
          </button>
        </nav>
      </section>

      {pipeline.review && (
        <nav className="foot-nav end" aria-label="Bước tiếp theo">
          <button type="button" className="btn" onClick={() => goTo('ingest')}>Tiếp tục ingest →</button>
        </nav>
      )}
    </>
  )
}
