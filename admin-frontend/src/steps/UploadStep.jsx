import { useRef, useState } from 'react'
import { api } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'

export default function UploadStep({ pipeline, update, goTo }) {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

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
      <header className="page-head">
        <h1>1 — Tải canonical Markdown</h1>
        <p>Tải Markdown đã OCR và review, gồm YAML frontmatter cùng page markers.</p>
      </header>

      <form className="card" aria-labelledby="upload-file-heading" onSubmit={(event) => { event.preventDefault(); onUpload() }}>
        <h2 id="upload-file-heading">Chọn file</h2>
        <label
          className={`dropzone ${drag ? 'drag' : ''}`}
          onClick={() => inputRef.current?.click()}
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
            ref={inputRef}
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
            <dt>document_key</dt><dd className="mono">{result.document_key}</dd>
            <dt>version_key</dt><dd className="mono">{result.version_key}</dd>
            <dt>source_path</dt><dd className="mono">{result.source_path}</dd>
            <dt>file_type</dt><dd className="mono">{result.file_type}</dd>
            <dt>checksum</dt><dd className="mono">{result.checksum}</dd>
            <dt>review_status</dt><dd><StatusBadge status={result.review_status} /></dd>
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
