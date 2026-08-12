import { useEffect, useState } from 'react'
import { FileText, Loader2, Trash2, Upload } from 'lucide-react'
import { toast } from 'react-toastify'
import { api } from '../api/client.js'
import { useReferenceData } from '../hooks/useReferenceData.js'
import PageHeader from '../components/PageHeader.jsx'

const MAX_MARKDOWN_SIZE_MB = 20
const MAX_SOURCE_SIZE_MB = 100
const ACCEPTED_EXTENSIONS = ['.md', '.markdown']
const ACCEPTED_SOURCE_EXTENSIONS = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.md', '.markdown']

function parseVietnameseDate(value) {
  const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value.trim())
  if (!match) return null

  const [, dayText, monthText, yearText] = match
  const day = Number(dayText)
  const month = Number(monthText)
  const year = Number(yearText)
  if (year < 1000) return null
  const candidate = new Date(Date.UTC(year, month - 1, day))

  if (
    candidate.getUTCFullYear() !== year
    || candidate.getUTCMonth() !== month - 1
    || candidate.getUTCDate() !== day
  ) return null

  return `${yearText}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function formatVietnameseDate(value) {
  if (!value) return ''

  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (isoMatch) {
    const [, year, month, day] = isoMatch
    return `${day}/${month}/${year}`
  }

  const isoDate = parseVietnameseDate(value)
  if (!isoDate) return value
  const [year, month, day] = isoDate.split('-')
  return `${day}/${month}/${year}`
}

const EMPTY_METADATA = {
  title: '',
  document_key: '',
  version_key: '',
  document_type: '',
  domain: 'unknown',
  audience: [],
  responsible_department: [],
  code: '',
  issued_date: '',
  effective_date: '',
  source_url: '',
  notes: '',
}
function getUploadErrorMessage({ name, message = '' }) {
  if (name === 'AbortError') return 'Kết nối quá thời gian. Vui lòng kiểm tra mạng và thử lại.'
  if (name === 'TypeError' || message === 'Failed to fetch') return 'Không thể kết nối server. Vui lòng thử lại sau.'
  if (/HTTP\s*5\d{2}/i.test(message)) return 'Lỗi server. Vui lòng thử lại sau.'
  if (/file|invalid|không hợp lệ|frontmatter|yaml/i.test(message)) return `File không hợp lệ: ${message}`
  return message || 'Đã xảy ra lỗi không xác định. Vui lòng thử lại.'
}

export default function UploadStep({ update, goTo }) {
  const [file, setFile] = useState(null)
  const [sourceFile, setSourceFile] = useState(null)
  const [departmentCode, setDepartmentCode] = useState('')
  const [metadata, setMetadata] = useState(EMPTY_METADATA)
  const [drag, setDrag] = useState(false)
  const [sourceDrag, setSourceDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [databaseStatus, setDatabaseStatus] = useState('checking')
  const { documentTypes, departments, enumOptions, loading: referencesLoading } = useReferenceData()
  const issuedDate = parseVietnameseDate(metadata.issued_date)
  const effectiveDate = parseVietnameseDate(metadata.effective_date)
  const datesAreValid = (
    (!metadata.issued_date || issuedDate)
    && (!metadata.effective_date || effectiveDate)
  )
  const uploadReady = Boolean(
    file
    && departmentCode
    && metadata.title.trim()
    && metadata.document_key.trim()
    && metadata.version_key.trim()
    && metadata.document_type
    && metadata.responsible_department.length
    && metadata.responsible_department.every(Boolean)
    && datesAreValid
    && (effectiveDate || issuedDate),
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
    setMetadata(EMPTY_METADATA)

    try {
      const preview = await api.previewMarkdownMetadata(f)
      const suggested = preview.metadata || {}
      setMetadata((current) => ({
        ...current,
        ...suggested,
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

  function toggleAudience(audience) {
    setMetadata((current) => ({
      ...current,
      audience: current.audience.includes(audience)
        ? current.audience.filter((item) => item !== audience)
        : [...current.audience, audience],
    }))
  }

  function setResponsibleDepartment(index, departmentCode) {
    setMetadata((current) => ({
      ...current,
      responsible_department: (current.responsible_department.length
        ? current.responsible_department
        : ['']
      ).map((item, currentIndex) => currentIndex === index ? departmentCode : item),
    }))
  }

  function addResponsibleDepartment() {
    setMetadata((current) => ({
      ...current,
      responsible_department: [...current.responsible_department, ''],
    }))
  }

  function removeResponsibleDepartment(index) {
    setMetadata((current) => ({
      ...current,
      responsible_department: current.responsible_department.filter((_, currentIndex) => currentIndex !== index),
    }))
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
      const uploadMetadata = Object.fromEntries(
        Object.entries({
          ...metadata,
          issued_date: issuedDate || '',
          effective_date: effectiveDate || '',
          responsible_department: metadata.responsible_department.filter(Boolean),
        }).filter(([, value]) => value !== ''),
      )
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

      <form className="card upload-form" aria-labelledby="upload-file-heading" onSubmit={(event) => { event.preventDefault(); onUpload() }}>
        <header className="upload-card-head">
          <h2 id="upload-file-heading">Chọn file</h2>
          <span className="file-types">Markdown bắt buộc</span>
        </header>
        <div className="upload-fields">
          <fieldset className="form-grid" disabled={referencesLoading}>
            <legend>Thông tin tài liệu</legend>
            <label className="field" htmlFor="upload-title">
              <span>Tiêu đề <b aria-hidden="true">*</b></span>
              <input id="upload-title" value={metadata.title} onChange={(event) => setMetadataField('title', event.target.value)} required />
            </label>
            <label className="field" htmlFor="upload-document-type">
              <span>Loại tài liệu <b aria-hidden="true">*</b></span>
              <select id="upload-document-type" value={metadata.document_type} onChange={(event) => setMetadataField('document_type', event.target.value)} required>
                <option value="">— Chọn loại tài liệu —</option>
                {documentTypes.filter((type) => type.is_active).map((type) => <option key={type.code} value={type.code}>{type.name} ({type.code})</option>)}
              </select>
            </label>
            <label className="field" htmlFor="upload-document-key">
              <span>Document key <b aria-hidden="true">*</b></span>
              <input id="upload-document-key" value={metadata.document_key} onChange={(event) => setMetadataField('document_key', event.target.value)} placeholder="vd: huong-dan-sinh-vien" required />
            </label>
            <label className="field" htmlFor="upload-version-key">
              <span>Version key <b aria-hidden="true">*</b></span>
              <input id="upload-version-key" value={metadata.version_key} onChange={(event) => setMetadataField('version_key', event.target.value)} placeholder="vd: hdsv-2026-01" required />
            </label>
            <label className="field" htmlFor="upload-domain">
              <span>Domain</span>
              <select id="upload-domain" value={metadata.domain} onChange={(event) => setMetadataField('domain', event.target.value)}>
                {enumOptions.domains.map((domain) => <option key={domain} value={domain}>{domain}</option>)}
              </select>
            </label>
            <label className="field" htmlFor="upload-code">
              <span>Số hiệu</span>
              <input id="upload-code" value={metadata.code} onChange={(event) => setMetadataField('code', event.target.value)} />
            </label>
          </fieldset>

          <fieldset className="responsible-departments" disabled={referencesLoading}>
            <legend>Phòng ban phụ trách <b aria-hidden="true">*</b></legend>
            {(metadata.responsible_department.length ? metadata.responsible_department : ['']).map((selectedCode, index) => (
              <div className="responsible-department-row" key={`${index}-${selectedCode}`}>
                <label className="field" htmlFor={`responsible-department-${index}`}>
                  <span className="sr-only">Phòng ban phụ trách {index + 1}</span>
                  <select id={`responsible-department-${index}`} value={selectedCode} onChange={(event) => setResponsibleDepartment(index, event.target.value)} required>
                    <option value="">— Chọn phòng ban —</option>
                    {departments.filter((department) => department.is_active && (department.code === selectedCode || !metadata.responsible_department.includes(department.code))).map((department) => (
                      <option key={department.code} value={department.code}>{department.code} — {department.name}</option>
                    ))}
                  </select>
                </label>
                {metadata.responsible_department.length > 1 && <button type="button" className="btn ghost small danger-icon" onClick={() => removeResponsibleDepartment(index)} aria-label={`Bỏ phòng ban phụ trách ${index + 1}`} title="Bỏ phòng ban"><Trash2 aria-hidden="true" /></button>}
              </div>
            ))}
            <button type="button" className="btn ghost small" onClick={addResponsibleDepartment} disabled={metadata.responsible_department.some((item) => !item)}>+ Thêm phòng ban</button>
          </fieldset>

          <fieldset className="form-grid" disabled={referencesLoading}>
            <legend>Thông tin bổ sung</legend>
            <label className="field" htmlFor="upload-issued-date">
              <span>Ngày ban hành <small>(Ngày/Tháng/Năm)</small></span>
              <input
                id="upload-issued-date"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                placeholder="DD/MM/YYYY"
                maxLength={10}
                value={metadata.issued_date}
                onChange={(event) => setMetadataField('issued_date', event.target.value)}
                onBlur={(event) => setMetadataField('issued_date', formatVietnameseDate(event.target.value))}
                aria-invalid={Boolean(metadata.issued_date && !issuedDate)}
              />
              {metadata.issued_date && !issuedDate && <small className="field-error">Nhập ngày hợp lệ theo DD/MM/YYYY.</small>}
            </label>
            <label className="field" htmlFor="upload-effective-date">
              <span>Ngày hiệu lực <small>(Ngày/Tháng/Năm)</small></span>
              <input
                id="upload-effective-date"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                placeholder="DD/MM/YYYY"
                maxLength={10}
                value={metadata.effective_date}
                onChange={(event) => setMetadataField('effective_date', event.target.value)}
                onBlur={(event) => setMetadataField('effective_date', formatVietnameseDate(event.target.value))}
                aria-invalid={Boolean(metadata.effective_date && !effectiveDate)}
              />
              {metadata.effective_date && !effectiveDate && <small className="field-error">Nhập ngày hợp lệ theo DD/MM/YYYY.</small>}
            </label>
            <label className="field" htmlFor="upload-source-url">
              <span>URL nguồn</span>
              <input id="upload-source-url" type="url" value={metadata.source_url} onChange={(event) => setMetadataField('source_url', event.target.value)} placeholder="https://…" />
            </label>
            <label className="field" htmlFor="upload-notes">
              <span>Ghi chú</span>
              <textarea className="metadata-notes" id="upload-notes" value={metadata.notes} onChange={(event) => setMetadataField('notes', event.target.value)} rows={1} />
            </label>
            <fieldset className="audience-fieldset">
              <legend>Đối tượng sử dụng</legend>
              <menu className="pill-row">
                {enumOptions.audiences.map((audience) => (
                  <li key={audience}><button type="button" className="tag" aria-pressed={metadata.audience.includes(audience)} onClick={() => toggleAudience(audience)}>{metadata.audience.includes(audience) ? '✓ ' : ''}{audience}</button></li>
                ))}
              </menu>
            </fieldset>
          </fieldset>

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
              {sourceFile ? <span className="selected-file"><strong>{sourceFile.name}</strong><small className="hint">{(sourceFile.size / 1024).toFixed(1)} KB</small></span> : <small className="dropzone-meta">PDF, DOC, DOCX, PPT, PPTX hoặc Markdown</small>}
              <input type="file" className="sr-only" accept={ACCEPTED_SOURCE_EXTENSIONS.join(',')} onChange={(e) => pickSource(e.target.files)} />
            </label>
          </div>
        </div>

        <div className="upload-actions">
          <label className="field upload-source-department" htmlFor="source-department-code">
            <span>Phòng ban lưu file nguồn <b aria-hidden="true">*</b></span>
            <select
              id="source-department-code"
              value={departmentCode}
              disabled={referencesLoading}
              onChange={(event) => setDepartmentCode(event.target.value)}
              required
            >
              <option value="">{referencesLoading ? 'Đang tải phòng ban…' : '— Chọn phòng ban —'}</option>
              {departments.filter((department) => department.is_active).map((department) => (
                <option key={department.code} value={department.code}>
                  {department.code} — {department.name}
                </option>
              ))}
            </select>
            <small className="hint">Dùng để tạo key riêng dưới <code>sources/</code>.</small>
          </label>
          <button type="submit" className="btn" disabled={!uploadReady || busy} aria-busy={busy}>
            {busy ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
            {busy ? 'Đang tải lên...' : 'Tải lên'}
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
