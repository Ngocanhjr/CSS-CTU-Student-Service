import { useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'

export default function IngestStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const metadata = upload?.metadata || upload
  const ingest = pipeline.ingest
  const canIngest = metadata?.ocr_status === 'done' && metadata?.review_status === 'approved'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!upload) {
    return (
      <>
        <header className="page-head"><h1>3 — Đưa vào CSDL</h1></header>
        <aside className="banner warn">
          Chưa có tài liệu. Hãy tải canonical Markdown trước.
          <p><button type="button" className="btn small" onClick={() => goTo('upload')}>← Về bước tải lên</button></p>
        </aside>
      </>
    )
  }

  async function onRun() {
    setBusy(true)
    setError('')
    try {
      const res = await api.runIngest(upload.document_version_id)
      update('ingest', res)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="page-head">
        <h1>3 — Đưa vào CSDL</h1>
        <p>Chunk → embed (BGE-M3) → insert PostgreSQL → upsert Qdrant.</p>
      </header>

      {error && <p className="banner warn" role="alert">{error}</p>}

      <aside className={canIngest ? 'banner' : 'banner warn'}>
        Ingest yêu cầu <span className="mono">ocr_status = done</span> và{' '}
        <span className="mono">review_status = approved</span>. Publish là bước riêng sau ingest.
      </aside>

      <section className="card" aria-labelledby="ingest-ready-heading">
        <h2 id="ingest-ready-heading">Sẵn sàng ingest</h2>
        <dl className="kv">
          <dt>version_key</dt><dd className="mono">{upload.version_key}</dd>
          <dt>Tiêu đề</dt><dd>{metadata.title}</dd>
          <dt>Phòng ban phụ trách</dt><dd>{metadata.responsible_department?.join(', ') || '—'}</dd>
          <dt>ocr_status</dt><dd><StatusBadge status={metadata.ocr_status || 'not_started'} /></dd>
          <dt>review_status</dt><dd><StatusBadge status={metadata.review_status || 'not_reviewed'} /></dd>
          <dt>rag_status</dt><dd><StatusBadge status={ingest ? ingest.rag_status : 'not_indexed'} /></dd>
        </dl>
        <button type="button" className="btn" disabled={busy || !canIngest} onClick={onRun}>
          {busy ? 'Đang ingest…' : ingest ? 'Chạy lại ingest' : 'Bắt đầu ingest'}
        </button>
      </section>

      {busy && <p className="banner" role="status" aria-live="polite">Backend đang chunk, lưu PostgreSQL, embed và upsert Qdrant…</p>}

      {ingest && (
        <section className="card" aria-labelledby="ingest-result-heading">
          <h2 id="ingest-result-heading">Kết quả ingest</h2>
          <dl className="kv">
            <dt>parent_chunks</dt><dd>{ingest.parent_chunks}</dd>
            <dt>child_chunks</dt><dd>{ingest.child_chunks}</dd>
            <dt>total_chunks</dt><dd>{ingest.total_chunks}</dd>
            <dt>qdrant_points</dt><dd>{ingest.qdrant_points}</dd>
            <dt>rag_status</dt><dd><StatusBadge status={ingest.rag_status} /></dd>
          </dl>
          <pre className="json-out"><code>{JSON.stringify(ingest, null, 2)}</code></pre>
          <footer className="foot-nav">
            <button type="button" className="btn ghost" onClick={() => goTo('upload')}>← Tải tài liệu khác</button>
          </footer>
        </section>
      )}
    </>
  )
}
