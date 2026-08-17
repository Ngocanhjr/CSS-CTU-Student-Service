import AudiencePicker from './AudiencePicker.jsx'
import ResponsibleDepartmentPicker from './ResponsibleDepartmentPicker.jsx'

export const EMPTY_METADATA = {
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
  is_latest: false,
  source_url: '',
  notes: '',
}

export function parseVietnameseDate(value) {
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

export function formatVietnameseDate(value) {
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

export function getUploadErrorMessage({ name, message = '' }) {
  if (name === 'AbortError') return 'Kết nối quá thời gian. Vui lòng kiểm tra mạng và thử lại.'
  if (name === 'TypeError' || message === 'Failed to fetch') return 'Không thể kết nối server. Vui lòng thử lại sau.'
  if (/HTTP\s*5\d{2}/i.test(message)) return 'Lỗi server. Vui lòng thử lại sau.'
  if (/file|invalid|không hợp lệ|frontmatter|yaml/i.test(message)) return `File không hợp lệ: ${message}`
  return message || 'Đã xảy ra lỗi không xác định. Vui lòng thử lại.'
}

export function getMetadataValidation(metadata) {
  const issuedDate = parseVietnameseDate(metadata.issued_date)
  const effectiveDate = parseVietnameseDate(metadata.effective_date)
  const datesAreValid = (
    (!metadata.issued_date || issuedDate)
    && (!metadata.effective_date || effectiveDate)
  )
  const complete = Boolean(
    metadata.title.trim()
    && metadata.document_key.trim()
    && metadata.version_key.trim()
    && metadata.document_type
    && metadata.responsible_department.length
    && metadata.responsible_department.every(Boolean)
    && datesAreValid
    && (effectiveDate || issuedDate)
  )

  return { complete, issuedDate, effectiveDate }
}

export function prepareUploadMetadata(metadata) {
  const { issuedDate, effectiveDate } = getMetadataValidation(metadata)
  return Object.fromEntries(
    Object.entries({
      ...metadata,
      issued_date: issuedDate || '',
      effective_date: effectiveDate || '',
      responsible_department: metadata.responsible_department.filter(Boolean),
    }).filter(([, value]) => value !== ''),
  )
}

export function SourceDepartmentField({ departments, value, onChange, loading, idPrefix }) {
  return (
    <label className="field upload-source-department" htmlFor={`${idPrefix}-source-department-code`}>
      <span>Phòng ban lưu file nguồn <b aria-hidden="true">*</b></span>
      <select
        id={`${idPrefix}-source-department-code`}
        value={value}
        disabled={loading}
        onChange={(event) => onChange(event.target.value)}
        required
      >
        <option value="">{loading ? 'Đang tải phòng ban…' : '— Chọn phòng ban —'}</option>
        {departments.filter((department) => department.is_active).map((department) => (
          <option key={department.code} value={department.code}>
            {department.code} — {department.name}
          </option>
        ))}
      </select>
      <small className="hint">Dùng để tạo key riêng dưới <code>sources/</code>.</small>
    </label>
  )
}

export default function DocumentMetadataForm({
  metadata,
  onChange,
  documentTypes,
  departments,
  enumOptions,
  loading,
  idPrefix,
}) {
  const { issuedDate, effectiveDate } = getMetadataValidation(metadata)
  const fieldId = (name) => `${idPrefix}-${name}`

  return (
    <>
      <fieldset className="form-grid" disabled={loading}>
        <legend>Thông tin tài liệu</legend>
        <label className="field" htmlFor={fieldId('title')}>
          <span>Tiêu đề <b aria-hidden="true">*</b></span>
          <input id={fieldId('title')} value={metadata.title} onChange={(event) => onChange('title', event.target.value)} required />
        </label>
        <label className="field" htmlFor={fieldId('document-type')}>
          <span>Loại tài liệu <b aria-hidden="true">*</b></span>
          <select id={fieldId('document-type')} value={metadata.document_type} onChange={(event) => onChange('document_type', event.target.value)} required>
            <option value="">— Chọn loại tài liệu —</option>
            {documentTypes.filter((type) => type.is_active).map((type) => <option key={type.code} value={type.code}>{type.name} ({type.code})</option>)}
          </select>
        </label>
        <label className="field" htmlFor={fieldId('document-key')}>
          <span>Document key <b aria-hidden="true">*</b></span>
          <input id={fieldId('document-key')} value={metadata.document_key} onChange={(event) => onChange('document_key', event.target.value)} placeholder="vd: huong-dan-sinh-vien" required />
        </label>
        <label className="field" htmlFor={fieldId('version-key')}>
          <span>Version key <b aria-hidden="true">*</b></span>
          <input id={fieldId('version-key')} value={metadata.version_key} onChange={(event) => onChange('version_key', event.target.value)} placeholder="vd: hdsv-2026-01" required />
        </label>
        <label className="field" htmlFor={fieldId('domain')}>
          <span>Domain</span>
          <select id={fieldId('domain')} value={metadata.domain} onChange={(event) => onChange('domain', event.target.value)}>
            {enumOptions.domains.map((domain) => <option key={domain} value={domain}>{domain}</option>)}
          </select>
        </label>
        <label className="field" htmlFor={fieldId('code')}>
          <span>Số hiệu</span>
          <input id={fieldId('code')} value={metadata.code} onChange={(event) => onChange('code', event.target.value)} />
        </label>
      </fieldset>

      <ResponsibleDepartmentPicker
        departments={departments}
        value={metadata.responsible_department}
        onChange={(value) => onChange('responsible_department', value)}
        idPrefix={`${idPrefix}-responsible-department`}
        disabled={loading}
      />

      <fieldset className="form-grid" disabled={loading}>
        <legend>Thông tin bổ sung</legend>
        <label className="field" htmlFor={fieldId('issued-date')}>
          <span>Ngày ban hành <small>(Ngày/Tháng/Năm)</small></span>
          <input
            id={fieldId('issued-date')}
            type="text"
            inputMode="numeric"
            autoComplete="off"
            placeholder="DD/MM/YYYY"
            maxLength={10}
            value={metadata.issued_date}
            onChange={(event) => onChange('issued_date', event.target.value)}
            onBlur={(event) => onChange('issued_date', formatVietnameseDate(event.target.value))}
            aria-invalid={Boolean(metadata.issued_date && !issuedDate)}
          />
          {metadata.issued_date && !issuedDate && <small className="field-error">Nhập ngày hợp lệ theo DD/MM/YYYY.</small>}
        </label>
        <label className="field" htmlFor={fieldId('effective-date')}>
          <span>Ngày hiệu lực <small>(Ngày/Tháng/Năm)</small></span>
          <input
            id={fieldId('effective-date')}
            type="text"
            inputMode="numeric"
            autoComplete="off"
            placeholder="DD/MM/YYYY"
            maxLength={10}
            value={metadata.effective_date}
            onChange={(event) => onChange('effective_date', event.target.value)}
            onBlur={(event) => onChange('effective_date', formatVietnameseDate(event.target.value))}
            aria-invalid={Boolean(metadata.effective_date && !effectiveDate)}
          />
          {metadata.effective_date && !effectiveDate && <small className="field-error">Nhập ngày hợp lệ theo DD/MM/YYYY.</small>}
        </label>
        <label className="field" htmlFor={fieldId('source-url')}>
          <span>URL nguồn</span>
          <input id={fieldId('source-url')} type="url" value={metadata.source_url} onChange={(event) => onChange('source_url', event.target.value)} placeholder="https://…" />
        </label>
        <label className="field" htmlFor={fieldId('notes')}>
          <span>Ghi chú</span>
          <textarea className="metadata-notes" id={fieldId('notes')} value={metadata.notes} onChange={(event) => onChange('notes', event.target.value)} rows={1} />
        </label>
        <AudiencePicker
          options={enumOptions.audiences}
          value={metadata.audience}
          onChange={(value) => onChange('audience', value)}
        />
        <label className="field checkbox-field" htmlFor={fieldId('is-latest')}>
          <input id={fieldId('is-latest')} type="checkbox" checked={Boolean(metadata.is_latest)} onChange={(event) => onChange('is_latest', event.target.checked)} />
          <span>Phiên bản mới nhất</span>
        </label>
      </fieldset>
    </>
  )
}
