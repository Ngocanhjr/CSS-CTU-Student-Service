import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import PageHeader from '../components/PageHeader.jsx'

const MAX_SIZE_MB = 20
const ACCEPTED_EXTENSIONS = ['.md', '.markdown']
const NEXT_STEPS = [
  ['02', 'Review & Approve', 'Kiểm tra nội dung'],
  ['03', 'Review Chunks', 'Phân đoạn văn bản'],
  ['04', 'Index & Publish', 'Đưa vào hệ thống'],
]

function getUploadErrorMessage(err) {
  // Network timeout (AbortError from AbortController)
  if (err.name === 'AbortError') {
    return 'Kết nối quá thời gian. Vui lòng kiểm tra mạng và thử lại.'
  }

  // Network error (TypeError from fetch - connection refused, DNS failure, etc.)
  if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
    return 'Không thể kết nối server. Vui lòng thử lại sau.'
  }

  // Server error (5xx) - check if message contains HTTP 5xx pattern
  if (/HTTP\s*5\d{2}/i.test(err.message)) {
    return 'Lỗi server. Vui lòng thử lại sau.'
  }

  // File validation errors from server - these typically come with descriptive messages
  // Check for common validation error patterns
  if (err.message && (
    err.message.includes('file') ||
    err.message.includes('File') ||
    err.message.includes('invalid') ||
    err.message.includes('không hợp lệ') ||
    err.message.includes('frontmatter') ||
    err.message.includes('YAML')
  )) {
    return `File không hợp lệ: ${err.message}`
  }

  // Default: return original message or generic error
  return err.message || 'Đã xảy ra lỗi không xác định. Vui lòng thử lại.'
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 15v2.5A2.5 2.5 0 006.5 20h11a2.5 2.5 0 002.5-2.5V15"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function UploadStep({ pipeline, update, goTo }) {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [databaseStatus, setDatabaseStatus] = useState('checking')

  const result = pipeline.upload

  useEffect(() => {
    let active = true
    api.getDatabaseHealth()
      .then(({ status }) => active && setDatabaseStatus(status))
      .catch(() => active && setDatabaseStatus('unavailable'))
    return () => { active = false }
  }, [])

  function pick(f) {
    if (!f) return
    const name = f.name.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      setError(`Chỉ nhận tệp Markdown (${ACCEPTED_EXTENSIONS.join(', ')}).`)
      return
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Tệp vượt giới hạn ${MAX_SIZE_MB} MB.`)
      return
    }
    setFile(f)
    setError('')
  }

  async function onUpload() {
    if (!file) return
    setBusy(true)
    try {
      const res = await api.uploadCanonicalMarkdown(file)
      update('upload', res)
      update('review', null)
      update('chunkPreview', null)
      update('chunkApproved', false)
      update('ingest', null)
      goTo('review')
    } catch (err) {
      setError(getUploadErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Ingestion · Bước 01 / 04"
        title="Tải canonical Markdown"
        description="Tải file Markdown đã OCR, có YAML frontmatter và page markers. Hệ thống sẽ xác thực cấu trúc trước khi chuyển sang bước review."
      />

      <p className={`database-health ${databaseStatus}`} role="status" aria-live="polite">
        <span aria-hidden="true">●</span>
        {databaseStatus === 'checking' && 'Đang kiểm tra PostgreSQL…'}
        {databaseStatus === 'available' && 'PostgreSQL đang hoạt động'}
        {databaseStatus === 'unavailable' && 'Không thể kết nối PostgreSQL'}
      </p>

      <form className="card upload-form" aria-labelledby="upload-file-heading" onSubmit={(event) => { event.preventDefault(); onUpload() }}>
        <header className="upload-card-head">
          <h2 id="upload-file-heading">Chọn file</h2>
          <span className="file-types">.md&nbsp;&nbsp;·&nbsp;&nbsp;.markdown</span>
        </header>
        <label
          className={`dropzone ${drag ? 'drag' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
          onDragEnter={(e) => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDrag(false)
            pick(e.dataTransfer.files?.[0])
          }}
        >
          <span className="dropzone-icon" aria-hidden="true"><UploadIcon /></span>
          {file ? (
            <span className="selected-file">
              <strong>{file.name}</strong>
              <small className="hint">{(file.size / 1024).toFixed(1)} KB — bấm để chọn tệp khác</small>
            </span>
          ) : (
            <>
              <span className="dropzone-title">
                Kéo thả tệp vào đây, hoặc <em>bấm để chọn</em>
              </span>
              <small className="dropzone-meta">
                Chấp nhận {ACCEPTED_EXTENSIONS.join(', ')} · tối đa {MAX_SIZE_MB} MB · cần YAML frontmatter và page markers
              </small>
            </>
          )}
          <input
            type="file"
            className="sr-only"
            accept=".md,.markdown,text/markdown"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </label>

        <div className="upload-actions">
          <button type="submit" className="btn" disabled={!file || busy} aria-busy={busy}>
            {busy ? <Loader2 size={16} className="spin" /> : <UploadIcon />}
            {busy ? 'Đang tải lên...' : 'Tải lên'}
          </button>
          {file && !busy && (
            <button type="button" className="btn ghost" onClick={() => setFile(null)}>
              Bỏ chọn
            </button>
          )}
          {!file && <span className="hint">Chọn tệp Markdown để bật nút tải lên.</span>}
        </div>
      </form>

      {error && <p className="banner" role="alert">{error}</p>}

      <aside className="upload-tip">
        <span aria-hidden="true">◇</span>
        <p><strong>Mẹo:</strong> Đảm bảo file có YAML frontmatter hợp lệ để hệ thống xác thực chính xác.</p>
      </aside>

      <aside className="upload-notice">
        <span aria-hidden="true">!</span>
        <p>PostgreSQL phải hoạt động ở bước này để lưu bản ghi ingestion. Trạng thái kết nối đang hiển thị phía trên.</p>
      </aside>

      <section className="next-steps" aria-labelledby="next-steps-heading">
        <h2 id="next-steps-heading">Các bước tiếp theo</h2>
        <ol>
          {NEXT_STEPS.map(([number, title, description]) => (
            <li key={number}>
              <small><span aria-hidden="true">○</span> Bước {number}</small>
              <strong>{title}</strong>
              <span>{description}</span>
            </li>
          ))}
        </ol>
      </section>

      {result && (
        <section className="card" aria-labelledby="upload-result-heading">
          <h2 id="upload-result-heading">Đã tải lên</h2>
          <dl className="kv">
            <dt>document_id</dt><dd className="mono">{result.document_id}</dd>
            <dt>document_version_id</dt><dd className="mono">{result.document_version_id}</dd>
            <dt>ingestion_job_id</dt><dd className="mono">{result.ingestion_job_id}</dd>
            <dt>document_key</dt><dd className="mono">{result.metadata.document_key}</dd>
            <dt>version_key</dt><dd className="mono">{result.metadata.version_key}</dd>
            <dt>source_path</dt><dd className="mono">{result.metadata.source_path}</dd>
            <dt>file_type</dt><dd className="mono">{result.metadata.file_type}</dd>
            <dt>checksum</dt><dd className="mono">{result.metadata.checksum}</dd>
            <dt>ocr_status</dt><dd><StatusBadge status={result.metadata.ocr_status} /></dd>
            <dt>review_status</dt><dd><StatusBadge status={result.metadata.review_status} /></dd>
            <dt>rag_status</dt><dd><StatusBadge status={result.metadata.rag_status} /></dd>
            <dt>Bước kế tiếp</dt><dd className="mono">review</dd>
          </dl>
          {result.metadata && (
            <section aria-labelledby="metadata-preview-heading">
              <h3 id="metadata-preview-heading">Metadata YAML</h3>
              <pre className="json-out"><code>{JSON.stringify(result.metadata, null, 2)}</code></pre>
            </section>
          )}
          {result.markdown && (
            <section aria-labelledby="markdown-preview-heading">
              <h3 id="markdown-preview-heading">Canonical Markdown</h3>
              <label className="field" htmlFor="uploaded-markdown">Nội dung đã tải</label>
              <textarea id="uploaded-markdown" readOnly value={result.markdown} />
            </section>
          )}
          <nav className="foot-nav end" aria-label="Bước tiếp theo">
            <button type="button" className="btn" onClick={() => goTo('review')}>Review nội dung →</button>
          </nav>
        </section>
      )}
    </>
  )
}
