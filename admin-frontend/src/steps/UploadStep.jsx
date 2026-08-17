import { useEffect, useState } from 'react'
import { FileScan, FileText, Loader2, Upload } from 'lucide-react'
import { toast } from 'react-toastify'
import { api } from '../api/client.js'
import { useReferenceData } from '../hooks/useReferenceData.js'
import PageHeader from '../components/PageHeader.jsx'
import DocumentMetadataForm, {
  EMPTY_METADATA,
  formatVietnameseDate,
  getMetadataValidation,
  getUploadErrorMessage,
  prepareUploadMetadata,
  SourceDepartmentField,
} from '../components/DocumentMetadataForm.jsx'

const MAX_MARKDOWN_SIZE_MB = 20
const MAX_SOURCE_SIZE_MB = 100
const ACCEPTED_EXTENSIONS = ['.md', '.markdown']
const ACCEPTED_SOURCE_EXTENSIONS = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp', '.md', '.markdown']

export default function UploadStep({ update, goTo, onOpenOcr }) {
  const [file, setFile] = useState(null)
  const [sourceFile, setSourceFile] = useState(null)
  const [departmentCode, setDepartmentCode] = useState('')
  const [metadata, setMetadata] = useState(EMPTY_METADATA)
  const [drag, setDrag] = useState(false)
  const [sourceDrag, setSourceDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [databaseStatus, setDatabaseStatus] = useState('checking')
  const { documentTypes, departments, enumOptions, loading: referencesLoading } = useReferenceData()
  const { complete: metadataComplete } = getMetadataValidation(metadata)
  const uploadReady = Boolean(
    file
    && departmentCode
    && metadataComplete,
  )

  useEffect(() => {
    let active = true
    api.getDatabaseHealth()
      .then(({ status }) => active && setDatabaseStatus(status))
      .catch(() => active && setDatabaseStatus('unavailable'))
    return () => { active = false }
  }, [])

  function oneFile(files, label) {
    const selected = Array.from(files || [])
    if (selected.length !== 1) {
      toast.error(`${label} chỉ được chọn một file.`)
      return null
    }
    return selected[0]
  }

  async function pickCanonical(files) {
    const f = oneFile(files, 'Markdown nội dung')
    if (!f) return
    const name = f.name.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      toast.error(`Chỉ nhận tệp Markdown (${ACCEPTED_EXTENSIONS.join(', ')}).`)
      return
    }
    if (f.size > MAX_MARKDOWN_SIZE_MB * 1024 * 1024) {
      toast.error(`Tệp vượt giới hạn ${MAX_MARKDOWN_SIZE_MB} MB.`)
      return
    }
    setFile(f)
    setSourceFile(null)
    setMetadata(EMPTY_METADATA)

    try {
      const preview = await api.previewMarkdownMetadata(f)
      const suggested = preview.metadata || {}
      setMetadata((current) => ({
        ...current,
        ...suggested,
        document_type: documentTypes.some(({ code }) => code === suggested.document_type)
          ? suggested.document_type
          : '',
        domain: enumOptions.domains.includes(suggested.domain) ? suggested.domain : 'unknown',
        audience: Array.isArray(suggested.audience) ? suggested.audience : [],
        responsible_department: Array.isArray(suggested.responsible_department)
          ? suggested.responsible_department
          : [],
        issued_date: formatVietnameseDate(suggested.issued_date),
        effective_date: formatVietnameseDate(suggested.effective_date),
      }))
    } catch {
      // Không có YAML hoặc API preview chưa triển khai: người dùng nhập tay.
    }
  }

  function setMetadataField(key, value) {
    setMetadata((current) => ({ ...current, [key]: value }))
  }

  function pickSource(files) {
    const f = oneFile(files, 'File nguồn')
    if (!f) return
    const name = f.name.toLowerCase()
    if (!ACCEPTED_SOURCE_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      toast.error(`File nguồn chỉ nhận ${ACCEPTED_SOURCE_EXTENSIONS.join(', ')}.`)
      return
    }
    if (f.size > MAX_SOURCE_SIZE_MB * 1024 * 1024) {
      toast.error(`File nguồn vượt giới hạn ${MAX_SOURCE_SIZE_MB} MB.`)
      return
    }
    setSourceFile(f)
  }

  async function onUpload() {
    if (!uploadReady) return
    setBusy(true)
    try {
      const uploadMetadata = prepareUploadMetadata(metadata)
      const res = await api.uploadCanonicalMarkdown(file, sourceFile, departmentCode, uploadMetadata)
      update('upload', res)
      update('review', null)
      update('chunkPreview', null)
      update('chunkApproved', false)
      update('ingest', null)
      goTo('review')
    } catch (err) {
      toast.error(getUploadErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Ingestion · Bước 01 / 04"
        title="Tải Markdown tài liệu"
        description="Tải nội dung Markdown và khai báo metadata. Hệ thống sẽ tạo canonical Markdown có YAML trước khi chuyển sang bước review."
      />

      <p className={`database-health ${databaseStatus}`} role="status" aria-live="polite">
        <span aria-hidden="true">●</span>
        {databaseStatus === 'checking' && 'Đang kiểm tra PostgreSQL…'}
        {databaseStatus === 'available' && 'PostgreSQL đang hoạt động'}
        {databaseStatus === 'unavailable' && 'Không thể kết nối PostgreSQL'}
      </p>

      <aside className="ocr-entry card" aria-labelledby="ocr-entry-heading">
        <span className="ocr-entry-icon" aria-hidden="true"><FileScan /></span>
        <div>
          <h2 id="ocr-entry-heading">Chưa có file Markdown?</h2>
          <p>Chuyển PDF, Word, PowerPoint hoặc ảnh thành Markdown trước khi xử lý tài liệu.</p>
        </div>
        <button type="button" className="btn" onClick={onOpenOcr}>Mở OCR</button>
      </aside>

      <form className="card upload-form" aria-labelledby="upload-file-heading" onSubmit={(event) => { event.preventDefault(); onUpload() }}>
        <header className="upload-card-head">
          <h2 id="upload-file-heading">Chọn file</h2>
          <span className="file-types">Markdown bắt buộc</span>
        </header>
        <div className="upload-fields">
          <DocumentMetadataForm
            metadata={metadata}
            onChange={setMetadataField}
            documentTypes={documentTypes}
            departments={departments}
            enumOptions={enumOptions}
            loading={referencesLoading}
            idPrefix="upload"
          />

          <div className="upload-dropzones">
            <label
              className={`dropzone ${drag ? 'drag' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
              onDragEnter={(e) => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); pickCanonical(e.dataTransfer.files) }}
            >
              <span className="dropzone-icon" aria-hidden="true"><Upload /></span>
              <strong>Markdown nội dung <b aria-hidden="true">*</b></strong>
              {file ? <span className="selected-file"><strong>{file.name}</strong><small className="hint">{(file.size / 1024).toFixed(1)} KB</small></span> : <small className="dropzone-meta">{ACCEPTED_EXTENSIONS.join(', ')} · không cần YAML</small>}
              <input type="file" className="sr-only" accept=".md,.markdown,text/markdown" onChange={(e) => pickCanonical(e.target.files)} />
            </label>

            <label
              className={`dropzone optional ${sourceDrag ? 'drag' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setSourceDrag(true) }}
              onDragEnter={(e) => { e.preventDefault(); setSourceDrag(true) }}
              onDragLeave={() => setSourceDrag(false)}
              onDrop={(e) => { e.preventDefault(); setSourceDrag(false); pickSource(e.dataTransfer.files) }}
            >
              <span className="dropzone-icon" aria-hidden="true"><FileText /></span>
              <strong>File nguồn <small>(tùy chọn)</small></strong>
              {sourceFile ? <span className="selected-file"><strong>{sourceFile.name}</strong><small className="hint">{(sourceFile.size / 1024).toFixed(1)} KB</small></span> : <small className="dropzone-meta">PDF, Word, PowerPoint, ảnh hoặc Markdown</small>}
              <input type="file" className="sr-only" accept={ACCEPTED_SOURCE_EXTENSIONS.join(',')} onChange={(e) => pickSource(e.target.files)} />
            </label>
          </div>
        </div>

        <div className="upload-actions">
          <SourceDepartmentField
            departments={departments}
            value={departmentCode}
            onChange={setDepartmentCode}
            loading={referencesLoading}
            idPrefix="upload"
          />
          <button type="submit" className="btn" disabled={!uploadReady || busy} aria-busy={busy}>
            {busy ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
            {busy ? 'Đang lưu...' : 'Lưu và tiếp tục'}
          </button>
          {file && !busy && (
            <button type="button" className="btn ghost" onClick={() => { setFile(null); setSourceFile(null) }}>
              Bỏ chọn
            </button>
          )}
          {!uploadReady && <span className="hint">Nhập các trường bắt buộc, ít nhất một ngày ban hành/ngày hiệu lực, phòng ban phụ trách, phòng ban nguồn và Markdown để bật nút tải lên.</span>}
        </div>
      </form>

      <aside className="upload-tip">
        <span aria-hidden="true">◇</span>
        <p><strong>Mẹo:</strong> Markdown chỉ chứa nội dung. Hệ thống tự tạo YAML từ metadata bạn đã nhập.</p>
      </aside>

      <aside className="upload-notice">
        <span aria-hidden="true">!</span>
        <p>PostgreSQL phải hoạt động ở bước này để lưu bản ghi ingestion. Trạng thái kết nối đang hiển thị phía trên.</p>
      </aside>

    </>
  )
}
