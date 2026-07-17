import { useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'

export default function ReviewStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const metadata = upload?.metadata
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
      update('chunkPreview', null)
      update('chunkApproved', false)
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
        <h1>2 — Review và approve</h1>
        <p>Chỉnh toàn bộ YAML và nội dung. Backend bảo vệ các trường provenance bất biến.</p>
      </header>

      {error && <p className="banner warn" role="alert">{error}</p>}

      <section className="card" aria-labelledby="review-status-heading">
        <h2 id="review-status-heading">Trạng thái</h2>
        <dl className="kv">
          <dt>document_version_id</dt><dd className="mono">{upload.document_version_id}</dd>
          <dt>document_key</dt><dd className="mono">{metadata.document_key}</dd>
          <dt>version_key</dt><dd className="mono">{metadata.version_key}</dd>
          <dt>checksum OCR</dt><dd className="mono">{metadata.checksum}</dd>
          <dt>ocr_status</dt><dd><StatusBadge status={metadata.ocr_status} /></dd>
          <dt>review_status</dt><dd><StatusBadge status={pipeline.review?.review_status || metadata.review_status} /></dd>
          <dt>rag_status</dt><dd><StatusBadge status={pipeline.review?.rag_status || metadata.rag_status} /></dd>
          <dt>Phòng ban phụ trách</dt><dd>{metadata.responsible_department?.join(', ') || '—'}</dd>
          {pipeline.review && <><dt>Bước kế tiếp</dt><dd className="mono">chunking</dd></>}
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
            {busy ? 'Đang approve…' : 'Lưu và approve'}
          </button>
        </nav>
      </section>

      {pipeline.review && (
        <nav className="foot-nav end" aria-label="Bước tiếp theo">
          <button type="button" className="btn" onClick={() => goTo('chunks')}>Review chunks →</button>
        </nav>
      )}
    </>
  )
}
