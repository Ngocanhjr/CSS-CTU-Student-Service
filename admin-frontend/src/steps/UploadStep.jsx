import { useRef, useState } from 'react'
import { mockApi } from '../api/mockClient.js'
import StatusBadge from '../components/StatusBadge.jsx'

export default function UploadStep({ pipeline, update, goTo }) {
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const inputRef = useRef(null)

  const result = pipeline.upload

  function pick(f) {
    if (!f) return
    setFile(f)
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''))
  }

  async function onUpload() {
    if (!file) return
    setBusy(true)
    try {
      const res = await mockApi.uploadDocument({ file, title: title || file.name })
      update('upload', { ...res, fileName: file.name })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>1 — Tải tài liệu</h1>
        <p>Tải file nguồn (PDF, DOCX, ảnh) để bắt đầu quy trình ingest.</p>
      </div>

      <div className="card">
        <h2>Chọn file</h2>
        <div
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
            <div>
              <strong>{file.name}</strong>
              <div className="hint">{(file.size / 1024).toFixed(1)} KB — bấm để chọn file khác</div>
            </div>
          ) : (
            <div>Kéo thả file vào đây, hoặc bấm để chọn</div>
          )}
          <input
            ref={inputRef}
            type="file"
            hidden
            accept=".pdf,.docx,.doc,.png,.jpg,.jpeg,.tiff,.html"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </div>

        <div style={{ marginTop: 16 }}>
          <label className="field">
            <span>Tiêu đề tài liệu</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="VD: Quy chế đào tạo đại học hệ chính quy"
            />
          </label>
        </div>

        <button className="btn" disabled={!file || busy} onClick={onUpload}>
          {busy ? 'Đang tải lên…' : 'Tải lên'}
        </button>
      </div>

      {result && (
        <div className="card">
          <h2>Đã tải lên</h2>
          <dl className="kv">
            <dt>document_key</dt><dd className="mono">{result.document_key}</dd>
            <dt>version_key</dt><dd className="mono">{result.version_key}</dd>
            <dt>source_path</dt><dd className="mono">{result.source_path}</dd>
            <dt>file_type</dt><dd className="mono">{result.file_type}</dd>
            <dt>checksum</dt><dd className="mono">{result.checksum}</dd>
            <dt>ocr_status</dt><dd><StatusBadge status={result.ocr_status} /></dd>
          </dl>
          <div className="foot-nav">
            <span />
            <button className="btn" onClick={() => goTo('ocr')}>Tiếp tục: OCR →</button>
          </div>
        </div>
      )}
    </>
  )
}
