import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import PageHeader from '../components/PageHeader.jsx'

const STAGES = [
  { key: 'chunked', label: 'Chunk parent/child', detail: 'Tạo cấu trúc parent và child chunk.' },
  { key: 'chunked', label: 'Lưu PostgreSQL', detail: 'Ghi document_chunks; PostgreSQL là nguồn dữ liệu chuẩn.' },
  { key: 'embedded', label: 'Tạo embedding', detail: 'Tạo vector cho các child chunk.' },
  { key: 'indexed', label: 'Upsert Qdrant', detail: 'Ghi vector và payload phục vụ tìm kiếm.' },
  { key: 'published', label: 'Publish riêng', detail: 'Chỉ publish sau khi kiểm tra index thành công.' },
]

const RAG_ORDER = ['not_indexed', 'chunked', 'embedded', 'indexed', 'published']

export default function IngestStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const metadata = upload?.metadata
  const ingest = pipeline.ingest
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!upload) {
    return (
      <>
        <PageHeader eyebrow="Ingestion / 04" title="Index document" />
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
      const res = await api.indexDocumentVersion(upload.document_version_id)
      setJob(res)
      update('ingest', res)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!job?.ingestion_job_id || !['pending', 'processing'].includes(job.job_status)) return undefined
    let cancelled = false
    const poll = async () => {
      try {
        const next = await api.getIndexingJob(job.ingestion_job_id)
        if (cancelled) return
        setJob(next)
        if (!['pending', 'processing'].includes(next.job_status)) update('ingest', next)
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    }
    const timer = setInterval(poll, 1000)
    void poll()
    return () => { cancelled = true; clearInterval(timer) }
  }, [job?.ingestion_job_id, job?.job_status, update])

  const progress = job || ingest
  const ragStatus = progress?.rag_status || metadata.rag_status || 'not_indexed'
  const indexing = progress?.job_status === 'processing'
  const alreadyIndexed = ['indexed', 'published'].includes(ragStatus)
  const canIngest = metadata?.ocr_status === 'done'
    && metadata?.review_status === 'approved'
    && pipeline.chunkApproved
    && ['not_indexed', 'failed', 'chunked', 'embedded'].includes(ragStatus)

  return (
    <>
      <PageHeader
        eyebrow="Ingestion / 04"
        title="Index document"
        description="Chunk → PostgreSQL → embedding → Qdrant. Publish là bước riêng sau validation."
      />

      {error && <p className="banner warn" role="alert">{error}</p>}

      {alreadyIndexed && (
        <p className="banner" role="status">
          Tài liệu đã index thành công. Không cần chạy lại nếu nội dung không thay đổi.
        </p>
      )}

      <aside className={canIngest ? 'banner' : 'banner warn'}>
        Index yêu cầu <span className="mono">ocr_status = done</span> và{' '}
        <span className="mono">review_status = approved</span>, đồng thời chunk preview đã được duyệt.
        {!pipeline.chunkApproved && (
          <p><button type="button" className="btn small" onClick={() => goTo('chunks')}>Review chunks</button></p>
        )}
      </aside>

      <section className="card" aria-labelledby="ingest-ready-heading">
        <h2 id="ingest-ready-heading">Document version</h2>
        <dl className="kv">
          <dt>document_version_id</dt><dd className="mono">{upload.document_version_id}</dd>
          <dt>ingestion_job_id</dt><dd className="mono">{upload.ingestion_job_id}</dd>
          <dt>version_key</dt><dd className="mono">{metadata.version_key}</dd>
          <dt>Tiêu đề</dt><dd>{metadata.title}</dd>
          <dt>Phòng ban phụ trách</dt><dd>{metadata.responsible_department?.join(', ') || '—'}</dd>
          <dt>ocr_status</dt><dd><StatusBadge status={metadata.ocr_status || 'not_started'} /></dd>
          <dt>review_status</dt><dd><StatusBadge status={metadata.review_status || 'not_reviewed'} /></dd>
          <dt>rag_status</dt><dd><StatusBadge status={ragStatus} /></dd>
        </dl>
        <button type="button" className="btn" disabled={busy || indexing || !canIngest} onClick={onRun}>
          {busy
            ? 'Đang tạo job…'
            : indexing
              ? 'Đang index…'
            : alreadyIndexed
              ? 'Đã index — không cần chạy lại'
              : ragStatus === 'failed'
                ? 'Thử lại index'
                : ragStatus === 'not_indexed'
                  ? 'Bắt đầu index'
                  : 'Tiếp tục index'}
        </button>
      </section>

      {progress?.ingestion_job_id && (
        <section className="card" aria-labelledby="embedding-progress-heading">
          <h2 id="embedding-progress-heading">Tiến độ embedding</h2>
          <dl className="kv">
            <dt>job.status</dt><dd><StatusBadge status={progress.job_status} /></dd>
            <dt>current_step</dt><dd className="mono">{progress.current_step}</dd>
            <dt>Child chunks</dt><dd>{progress.processed_chunks} / {progress.total_chunks}</dd>
            <dt>Còn lại</dt><dd>{progress.remaining_chunks} chunks</dd>
          </dl>
          <progress value={progress.processed_chunks} max={progress.total_chunks || 1}>
            {progress.processed_chunks} / {progress.total_chunks}
          </progress>
          {progress.error_message && <p className="banner warn" role="alert">{progress.error_message}</p>}
        </section>
      )}

      <section className="card" aria-labelledby="pipeline-heading">
        <h2 id="pipeline-heading">Tiến trình indexing</h2>
        <ol className="pipeline-list">
          {STAGES.map((stage, index) => {
            const reached = RAG_ORDER.indexOf(ragStatus) >= RAG_ORDER.indexOf(stage.key)
            return (
              <li key={`${stage.key}-${index}`} className={reached ? 'pipeline-stage done' : 'pipeline-stage'}>
                <span className="stage-index" aria-hidden="true">{reached ? '✓' : index + 1}</span>
                <section aria-labelledby={`stage-${index}`}>
                  <h3 id={`stage-${index}`}>{stage.label}</h3>
                  <p>{stage.detail}</p>
                </section>
              </li>
            )
          })}
        </ol>
      </section>

      {busy && <p className="banner" role="status" aria-live="polite">Backend đang chạy workflow indexing…</p>}

      {ingest && (
        <section className="card" aria-labelledby="ingest-result-heading">
          <h2 id="ingest-result-heading">Kết quả indexing</h2>
          <dl className="kv">
            <dt>parent_chunks</dt><dd>{ingest.parent_chunks ?? '—'}</dd>
            <dt>child_chunks</dt><dd>{ingest.child_chunks ?? '—'}</dd>
            <dt>total_chunks</dt><dd>{ingest.total_chunks ?? '—'}</dd>
            <dt>qdrant_points</dt><dd>{ingest.qdrant_points ?? '—'}</dd>
            <dt>job.status</dt><dd><StatusBadge status={ingest.job?.status || ingest.job_status} /></dd>
            <dt>current_step</dt><dd className="mono">{ingest.job?.current_step || ingest.current_step || '—'}</dd>
            <dt>rag_status</dt><dd><StatusBadge status={ingest.rag_status} /></dd>
            {(ingest.job?.error_message || ingest.error_message) && <><dt>Lỗi</dt><dd>{ingest.job?.error_message || ingest.error_message}</dd></>}
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
