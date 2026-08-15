import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-toastify'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import PageHeader from '../components/PageHeader.jsx'

const STAGES = [
  { key: 'chunked', label: 'Chunks đã duyệt', detail: 'Đọc Parent/Child chunks đã approve trong PostgreSQL.' },
  { key: 'embedded', label: 'Tạo embedding', detail: 'Tạo vector cho các child chunk.' },
  { key: 'indexed', label: 'Upsert Qdrant', detail: 'Ghi vector và payload phục vụ tìm kiếm.' },
  { key: 'published', label: 'Publish riêng', detail: 'Chỉ publish sau khi kiểm tra index thành công.' },
]

const RAG_ORDER = ['not_indexed', 'chunked', 'embedded', 'indexed', 'published']

const STEP_LABELS = {
  embedding: 'Đang tạo embedding',
  qdrant_upsert: 'Đang lưu vectors vào Qdrant',
  completed: 'Hoàn tất indexing',
  failed: 'Indexing thất bại',
}

export default function IngestStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const metadata = upload?.metadata
  const ingest = pipeline.ingest
  const [job, setJob] = useState(() => ingest)
  const [busy, setBusy] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const completedJobRef = useRef(null)

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
    try {
      const res = await api.indexDocumentVersion(upload.document_version_id)
      setJob(res)
      update('ingest', res)
      toast.info('Đã tạo job indexing.')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function onPublish() {
    setPublishing(true)
    try {
      const result = await api.publishDocument(upload.document_version_id)
      const next = { ...(job || ingest), rag_status: result.rag_status }
      setJob(next)
      update('ingest', next)
      toast.success('Đã xuất bản tài liệu. Chatbot có thể sử dụng tài liệu này.')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setPublishing(false)
    }
  }

  useEffect(() => {
    if (!job?.ingestion_job_id || !['pending', 'processing'].includes(job.job_status)) return undefined
    let cancelled = false
    let reportedPollError = false
    const poll = async () => {
      try {
        const next = await api.getIndexingJob(job.ingestion_job_id)
        if (cancelled) return
        setJob(next)
        if (!['pending', 'processing'].includes(next.job_status)) {
          update('ingest', next)
          if (next.job_status === 'completed' && completedJobRef.current !== next.ingestion_job_id) {
            completedJobRef.current = next.ingestion_job_id
            toast.success('Indexing hoàn tất. Hãy kiểm tra kết quả rồi xuất bản tài liệu.')
          }
        }
      } catch (err) {
        if (!cancelled && !reportedPollError) {
          reportedPollError = true
          toast.error(err.message)
        }
      }
    }
    const timer = setInterval(poll, 1000)
    void poll()
    return () => { cancelled = true; clearInterval(timer) }
  }, [job?.ingestion_job_id, job?.job_status, update])

  const progress = job || ingest
  const ragStatus = progress?.rag_status || metadata.rag_status || 'not_indexed'
  const indexing = progress?.job_status === 'processing'
  const totalChunks = progress?.total_chunks || 0
  const processedChunks = Math.min(progress?.processed_chunks || 0, totalChunks)
  const remainingChunks = Math.max(progress?.remaining_chunks ?? totalChunks - processedChunks, 0)
  const progressPercent = totalChunks ? Math.round((processedChunks / totalChunks) * 100) : 0
  const progressLabel = STEP_LABELS[progress?.current_step] || 'Đang chuẩn bị indexing'
  const embeddingComplete = totalChunks > 0 && processedChunks === totalChunks
  const chunkProgressLabel = progress?.job_status === 'completed'
    ? 'child chunks đã index'
    : 'child chunks đã embedding'
  const chunkProgressAriaLabel = progress?.job_status === 'completed'
    ? `Đã index ${processedChunks} trên ${totalChunks} child chunks`
    : `Đã tạo embedding cho ${processedChunks} trên ${totalChunks} child chunks`
  const alreadyIndexed = ['indexed', 'published'].includes(ragStatus)
  const canIngest = metadata?.ocr_status === 'done'
    && metadata?.review_status === 'approved'
    && pipeline.chunkApproved
    && ['not_indexed', 'failed'].includes(ragStatus)

  return (
    <>
      <PageHeader
        eyebrow="Ingestion / 04"
        title="Index document"
        description="Chunks đã duyệt trong PostgreSQL → embedding → Qdrant. Publish là bước riêng sau validation."
      />

      {alreadyIndexed && (
        <aside className="banner" role="status">
          {ragStatus === 'published'
            ? 'Tài liệu đã xuất bản và sẵn sàng cho chatbot.'
            : 'Tài liệu đã index thành công. Hãy kiểm tra kết quả trước khi xuất bản.'}
          {ragStatus === 'indexed' && (
            <p>
              <button type="button" className="btn small" disabled={publishing} onClick={onPublish}>
                {publishing ? 'Đang xuất bản…' : 'Xuất bản tài liệu'}
              </button>
            </p>
          )}
        </aside>
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
          <dt>Ghi chú</dt><dd>{metadata.notes || '—'}</dd>
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
        <section className="card index-progress-card" aria-labelledby="index-progress-heading" aria-live="polite">
          <header className="index-progress-header">
            <section>
              <h2 id="index-progress-heading">Tiến trình indexing</h2>
              <p className="index-progress-step">{progressLabel}</p>
            </section>
            <StatusBadge status={progress.job_status} />
          </header>
          <section className="index-progress-summary" aria-label={chunkProgressAriaLabel}>
            <strong>{processedChunks} / {totalChunks} {chunkProgressLabel}</strong>
            <strong className="index-progress-percent">Embedding {progressPercent}%</strong>
          </section>
          <progress className="index-progress-track" value={processedChunks} max={totalChunks || 1}>
            {progressPercent}%
          </progress>
          <p className="hint">
            {progress?.current_step === 'qdrant_upsert' && embeddingComplete
              ? 'Embedding hoàn tất — đang lưu vectors vào Qdrant.'
              : progress?.job_status === 'completed'
                ? 'Indexing hoàn tất.'
                : `Còn lại ${remainingChunks} chunks cần tạo embedding.`}
          </p>
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
        </section>
      )}
    </>
  )
}
