import { useState } from 'react'
import { mockApi } from '../api/mockClient.js'
import StatusBadge from '../components/StatusBadge.jsx'
import StepProgress from '../components/StepProgress.jsx'

const INGEST_STEPS = [
  { key: 'chunking', label: 'Chunking (MarkdownHeaderTextSplitter)' },
  { key: 'child_split', label: 'Cắt child chunks (Recursive splitter)' },
  { key: 'embedding', label: 'Embedding BGE-M3 (1024d)' },
  { key: 'pg_insert', label: 'Insert PostgreSQL (css.document_chunks)' },
  { key: 'qdrant_upsert', label: 'Upsert Qdrant' },
]

export default function IngestStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const ocr = pipeline.ocr
  const metadata = pipeline.metadata
  const ingest = pipeline.ingest
  const [busy, setBusy] = useState(false)
  const [steps, setSteps] = useState(
    INGEST_STEPS.map((s) => ({ ...s, state: 'pending' })),
  )

  if (!metadata) {
    return (
      <>
        <div className="page-head"><h1>4 — Đưa vào CSDL</h1></div>
        <div className="banner warn">
          Chưa có metadata. Hãy hoàn tất bước 3 trước.
          <div style={{ marginTop: 10 }}>
            <button className="btn small" onClick={() => goTo('metadata')}>← Về bước metadata</button>
          </div>
        </div>
      </>
    )
  }

  async function onRun() {
    setBusy(true)
    setSteps(INGEST_STEPS.map((s) => ({ ...s, state: 'pending' })))
    try {
      const res = await mockApi.runIngest(
        { markdown: ocr.markdown, versionKey: upload.version_key },
        (step) => {
          setSteps((prev) =>
            prev.map((s) =>
              s.key === step.key ? { ...s, state: step.state, sub: step.sub || s.sub } : s,
            ),
          )
        },
      )
      update('ingest', res)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>4 — Đưa vào CSDL</h1>
        <p>Chunk → embed (BGE-M3) → insert PostgreSQL → upsert Qdrant.</p>
      </div>

      <div className="banner">
        Điều kiện publish: <span className="mono">ocr_status = done</span> và{' '}
        <span className="mono">review_status = approved</span>. Prototype mô phỏng review đã duyệt.
      </div>

      <div className="card">
        <h2>Sẵn sàng ingest</h2>
        <dl className="kv">
          <dt>version_key</dt><dd className="mono">{upload.version_key}</dd>
          <dt>Tiêu đề</dt><dd>{metadata.title}</dd>
          <dt>Phòng ban tiếp nhận</dt><dd>{metadata.recipients.length} phòng ban</dd>
          <dt>rag_status</dt><dd><StatusBadge status={ingest ? ingest.rag_status : 'not_indexed'} /></dd>
        </dl>
        <button className="btn" disabled={busy} onClick={onRun}>
          {busy ? 'Đang ingest…' : ingest ? 'Chạy lại ingest' : 'Bắt đầu ingest'}
        </button>
      </div>

      {(busy || ingest) && (
        <div className="card">
          <h2>Tiến trình pipeline</h2>
          <StepProgress steps={steps} />
        </div>
      )}

      {ingest && (
        <div className="card">
          <h2>Kết quả ingest</h2>
          <dl className="kv">
            <dt>parent_chunks</dt><dd>{ingest.parent_chunks}</dd>
            <dt>child_chunks</dt><dd>{ingest.child_chunks}</dd>
            <dt>total_chunks</dt><dd>{ingest.total_chunks}</dd>
            <dt>qdrant_points</dt><dd>{ingest.qdrant_points}</dd>
            <dt>rag_status</dt><dd><StatusBadge status={ingest.rag_status} /></dd>
          </dl>
          <div className="foot-nav">
            <button className="btn ghost" onClick={() => goTo('metadata')}>← Quay lại</button>
            <button className="btn" onClick={() => goTo('output')}>Xem kết quả (output) →</button>
          </div>
        </div>
      )}
    </>
  )
}
