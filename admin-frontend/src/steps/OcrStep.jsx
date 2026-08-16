import { ArrowLeft, ExternalLink, FileCheck2, FileScan, Loader2, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import { api } from '../api/client.js'
import { useReferenceData } from '../hooks/useReferenceData.js'
import DocumentMetadataForm, {
  EMPTY_METADATA,
  formatVietnameseDate,
  getMetadataValidation,
  getUploadErrorMessage,
  prepareUploadMetadata,
  SourceDepartmentField,
} from '../components/DocumentMetadataForm.jsx'
import LineNumberedTextarea from '../components/LineNumberedTextarea.jsx'
import PageHeader from '../components/PageHeader.jsx'

const ACCEPTED_OCR_FILES = '.pdf,.doc,.docx,.ppt,.pptx,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp'
const MAX_SOURCE_SIZE = 100 * 1024 * 1024

export default function OcrStep({ onBack, update, goTo }) {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [markdown, setMarkdown] = useState('')
  const [metadata, setMetadata] = useState(EMPTY_METADATA)
  const [ocrMetadata, setOcrMetadata] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [departmentCode, setDepartmentCode] = useState('')
  const { documentTypes, departments, enumOptions, loading: referencesLoading } = useReferenceData()
  const { complete: metadataComplete } = getMetadataValidation(metadata)
  const saveReady = Boolean(markdown.trim() && file && departmentCode && metadataComplete)

  useEffect(() => {
    if (!markdown) {
      setPreviewUrl('')
      return undefined
    }

    const url = URL.createObjectURL(new Blob([markdown], { type: 'text/plain;charset=utf-8' }))
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [markdown])

  function selectFile(selectedFile) {
    if (!selectedFile) return
    const accepted = ACCEPTED_OCR_FILES.split(',')
    if (!accepted.some((extension) => selectedFile.name.toLowerCase().endsWith(extension))) {
      toast.error('Định dạng file chưa được hỗ trợ OCR.')
      return
    }
    if (selectedFile.size > MAX_SOURCE_SIZE) {
      toast.error('File OCR vượt quá 100 MB.')
      return
    }
    setFile(selectedFile)
    setMarkdown('')
    setMetadata(EMPTY_METADATA)
    setOcrMetadata(null)
    setDepartmentCode('')
  }

  async function startOcr() {
    if (!file) return
    setBusy(true)
    setMarkdown('')
    try {
      const result = await api.runOcr(file)
      setMarkdown(result.markdown)
      const suggested = result.metadata || {}
      setOcrMetadata(suggested)
      setMetadata({
        ...EMPTY_METADATA,
        title: suggested.title || '',
        document_key: suggested.document_key || '',
        version_key: suggested.version_key || '',
        document_type: documentTypes.some(({ code }) => code === suggested.document_type)
          ? suggested.document_type
          : '',
        domain: enumOptions.domains.includes(suggested.domain) ? suggested.domain : 'unknown',
        audience: Array.isArray(suggested.audience) ? suggested.audience : [],
        responsible_department: Array.isArray(suggested.responsible_department)
          ? suggested.responsible_department
          : [],
        code: suggested.code || '',
        issued_date: formatVietnameseDate(suggested.issued_date),
        effective_date: formatVietnameseDate(suggested.effective_date),
        source_url: suggested.source_url || '',
        notes: suggested.notes || '',
      })
      toast.success('OCR hoàn tất. Hãy kiểm tra Markdown và nhập thông tin tài liệu.')
    } catch (error) {
      toast.error(error.message || 'OCR thất bại; vui lòng thử lại.')
    } finally {
      setBusy(false)
    }
  }

  function setMetadataField(key, value) {
    setMetadata((current) => ({ ...current, [key]: value }))
  }

  async function saveAndContinue() {
    if (!saveReady) return
    const stem = file.name.replace(/\.[^.]+$/, '')
    const markdownFile = new File(
      [markdown],
      `${stem}_ocr.md`,
      { type: 'text/markdown;charset=utf-8' },
    )
    setSaving(true)
    try {
      const uploadMetadata = prepareUploadMetadata(metadata)
      if (ocrMetadata?.parser) uploadMetadata.parser = ocrMetadata.parser
      if (ocrMetadata?.ocr_engine) uploadMetadata.ocr_engine = ocrMetadata.ocr_engine

      const result = await api.uploadCanonicalMarkdown(
        markdownFile,
        file,
        departmentCode,
        uploadMetadata,
      )
      update('upload', result)
      update('review', null)
      update('chunkPreview', null)
      update('chunkApproved', false)
      update('ingest', null)
      goTo('review')
    } catch (error) {
      toast.error(getUploadErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Chuẩn bị tài liệu · OCR"
        title="Tạo Markdown từ file nguồn"
        description="Tải file nguồn lên để OCR. PostgreSQL và R2 chỉ được ghi sau khi bạn kiểm tra Markdown và bấm Lưu ở bước tiếp theo."
      />

      <form
        className="card ocr-workspace"
        aria-labelledby="ocr-source-heading"
        onSubmit={(event) => { event.preventDefault(); saveAndContinue() }}
      >
        <header>
          <h2 id="ocr-source-heading">File cần OCR</h2>
          <p>Hỗ trợ PDF, Word, PowerPoint và ảnh.</p>
        </header>

        <label
          className={`dropzone ocr-dropzone ${drag ? 'drag' : ''}`}
          onDragOver={(event) => { event.preventDefault(); setDrag(true) }}
          onDragEnter={(event) => { event.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDrag(false)
            selectFile(event.dataTransfer.files?.[0])
          }}
        >
          <span className="dropzone-icon" aria-hidden="true"><Upload /></span>
          <strong>{file ? file.name : 'Chọn hoặc thả file vào đây'}</strong>
          <small className="dropzone-meta">Tối đa 100 MB · mỗi lần một file</small>
          <input
            type="file"
            className="sr-only"
            accept={ACCEPTED_OCR_FILES}
            onChange={(event) => selectFile(event.target.files?.[0])}
          />
        </label>

        <p className={`ocr-status ${busy ? 'processing' : markdown ? 'done' : 'idle'}`} role="status" aria-live="polite">
          {busy && <><Loader2 size={16} className="spin" /> Đang upload và xử lý OCR…</>}
          {!busy && markdown && <><FileCheck2 size={16} /> OCR hoàn tất · chưa lưu PostgreSQL/R2</>}
          {!busy && !markdown && 'Chưa bắt đầu OCR'}
        </p>

        {markdown && (
          <>
            <section className="ocr-metadata" aria-labelledby="ocr-metadata-heading">
              <header>
                <h2 id="ocr-metadata-heading">Thông tin tài liệu</h2>
                <p>Nhập metadata để lưu file nguồn, canonical Markdown và tạo version tài liệu.</p>
              </header>
              <div className="ocr-result-tools">
                <dl className="ocr-technical-metadata">
                  <div>
                    <dt>Checksum SHA-256</dt>
                    <dd><code>{ocrMetadata?.checksum || 'Chưa có'}</code></dd>
                  </div>
                </dl>
                {previewUrl && (
                  <a
                    className="btn ghost"
                    href={previewUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={16} /> Xem nhanh bản OCR đầy đủ
                  </a>
                )}
              </div>
              <div className="upload-fields">
                <DocumentMetadataForm
                  metadata={metadata}
                  onChange={setMetadataField}
                  documentTypes={documentTypes}
                  departments={departments}
                  enumOptions={enumOptions}
                  loading={referencesLoading}
                  idPrefix="ocr"
                />
                <SourceDepartmentField
                  departments={departments}
                  value={departmentCode}
                  onChange={setDepartmentCode}
                  loading={referencesLoading}
                  idPrefix="ocr"
                />
              </div>
            </section>

            <section className="ocr-review" aria-labelledby="ocr-review-heading">
              <header>
                <h2 id="ocr-review-heading">Review Markdown</h2>
                <p>Chỉnh lỗi OCR tại đây trước khi lưu tài liệu.</p>
              </header>
              <label className="field" htmlFor="ocr-markdown">
                <span>Markdown sau OCR</span>
                <LineNumberedTextarea
                  id="ocr-markdown"
                  className="markdown-editor large"
                  value={markdown}
                  onChange={(event) => setMarkdown(event.target.value)}
                />
              </label>
            </section>
          </>
        )}

        <nav className="foot-nav" aria-label="Điều hướng OCR">
          <button type="button" className="btn ghost" onClick={onBack}>
            <ArrowLeft size={16} /> Quay lại upload
          </button>
          {!markdown && (
            <button type="button" className="btn" disabled={!file || busy} onClick={startOcr} aria-busy={busy}>
              {busy ? <Loader2 size={16} className="spin" /> : <FileScan size={16} />}
              {busy ? 'Đang OCR…' : 'Bắt đầu OCR'}
            </button>
          )}
          {markdown && (
            <div className="ocr-save-actions">
              <button type="submit" className="btn" disabled={!saveReady || saving} aria-busy={saving}>
                {saving ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
                {saving ? 'Đang lưu...' : 'Lưu và tiếp tục'}
              </button>
              {!saveReady && (
                <span className="hint">
                  Nhập các trường bắt buộc, ít nhất một ngày ban hành/ngày hiệu lực, phòng ban phụ trách và phòng ban nguồn để lưu.
                </span>
              )}
            </div>
          )}
        </nav>
      </form>
    </>
  )
}
