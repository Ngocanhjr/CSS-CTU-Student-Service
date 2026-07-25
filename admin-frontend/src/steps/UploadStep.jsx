import { useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import PageHeader from '../components/PageHeader.jsx'

export default function UploadStep({ pipeline, update, goTo }) {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const result = pipeline.upload

  function pick(f) {
    if (!f) return
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
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Ingestion / 01"
        title="Tải canonical Markdown"
        description="Tải Markdown đã OCR, gồm YAML frontmatter và page markers. PostgreSQL phải hoạt động ở bước này."
      />

      <form className="card" aria-labelledby="upload-file-heading" onSubmit={(event) => { event.preventDefault(); onUpload() }}>
        <h2 id="upload-file-heading">Chọn file</h2>
        <label
          className={`dropzone ${drag ? 'drag' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDrag(false)
            pick(e.dataTransfer.files?.[0])
          }}
        >
          {file ? (
            <span className="selected-file">
              <strong>{file.name}</strong>
              <small className="hint">{(file.size / 1024).toFixed(1)} KB — bấm để chọn file khác</small>
            </span>
          ) : (
            <span>Kéo thả file vào đây, hoặc bấm để chọn</span>
          )}
          <input
            type="file"
            hidden
            accept=".md,text/markdown"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </label>

        <button type="submit" className="btn upload-button" disabled={!file || busy}>
          {busy ? 'Đang tải lên…' : 'Tải lên'}
        </button>
      </form>

      {error && <p className="banner warn" role="alert">{error}</p>}

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
