import { ArrowLeft, FileCheck2, FileScan, Loader2, Upload } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'react-toastify'
import { api } from '../api/client.js'
import LineNumberedTextarea from '../components/LineNumberedTextarea.jsx'
import PageHeader from '../components/PageHeader.jsx'

const ACCEPTED_OCR_FILES = '.pdf,.doc,.docx,.ppt,.pptx,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp'
const MAX_SOURCE_SIZE = 100 * 1024 * 1024

export default function OcrStep({ onBack, onContinue }) {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [markdown, setMarkdown] = useState('')
  const [resultMetadata, setResultMetadata] = useState(null)

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
    setResultMetadata(null)
  }

  async function startOcr() {
    if (!file) return
    setBusy(true)
    setMarkdown('')
    try {
      const result = await api.runOcr(file)
      setMarkdown(result.markdown)
      setResultMetadata({
        parser: result.parser,
        ocr_engine: result.ocr_engine,
        language: result.language,
      })
      toast.success('OCR hoàn tất. Hãy kiểm tra Markdown trước khi tiếp tục.')
    } catch (error) {
      toast.error(error.message || 'OCR thất bại; vui lòng thử lại.')
    } finally {
      setBusy(false)
    }
  }

  function continueToIngestion() {
    if (!file || !markdown.trim()) return
    const stem = file.name.replace(/\.[^.]+$/, '')
    const markdownFile = new File(
      [markdown],
      `${stem}_ocr.md`,
      { type: 'text/markdown;charset=utf-8' },
    )
    onContinue({ sourceFile: file, markdownFile, metadata: resultMetadata })
  }

  return (
    <>
      <PageHeader
        eyebrow="Chuẩn bị tài liệu · OCR"
        title="Tạo Markdown từ file nguồn"
        description="Tải file nguồn lên để OCR. PostgreSQL và R2 chỉ được ghi sau khi bạn kiểm tra Markdown và bấm Lưu ở bước tiếp theo."
      />

      <section className="card ocr-workspace" aria-labelledby="ocr-source-heading">
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
          <section className="ocr-review" aria-labelledby="ocr-review-heading">
            <header>
              <h2 id="ocr-review-heading">Review Markdown</h2>
              <p>Chỉnh lỗi OCR tại đây. Nội dung chỉ được lưu khi hoàn tất form ingestion.</p>
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
            <button type="button" className="btn" disabled={!markdown.trim()} onClick={continueToIngestion}>
              Tiếp tục nhập metadata
            </button>
          )}
        </nav>
      </section>
    </>
  )
}
