import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { api } from '../api/client.js'
import AssetEditor from '../components/AssetEditor.jsx'
import PageHeader from '../components/PageHeader.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import LineNumberedTextarea from '../components/LineNumberedTextarea.jsx'
import { useReferenceData } from '../hooks/useReferenceData.js'
import { notify } from '../lib/notify.js'

function splitCanonicalMarkdown(canonicalMarkdown) {
  const match = canonicalMarkdown.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n)?/)
  return match
    ? { frontmatter: match[0], body: canonicalMarkdown.slice(match[0].length) }
    : { frontmatter: '', body: canonicalMarkdown }
}

function withFrontmatterValues(markdown, values) {
  return markdown.replace(/^---\r?\n([\s\S]*?)\r?\n---/, (_, frontmatter) => {
    const updated = Object.entries(values).reduce((yaml, [key, value]) => {
      const field = new RegExp(`^${key}:[^\\r\\n]*(?:\\r?\\n(?:[ \\t]+|- )[^\\r\\n]*)*`, 'm')
      const emptyValue = ['source_url', 'notes'].includes(key) ? '""' : 'null'
      const line = `${key}: ${value === '' || value == null ? emptyValue : JSON.stringify(value)}`
      return field.test(yaml) ? yaml.replace(field, line) : `${yaml}\n${line}`
    }, frontmatter)
    return `---\n${updated}\n---`
  })
}

export default function ReviewStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const metadata = upload?.metadata
  const { documentTypes, departments, enumOptions, loading: referencesLoading } = useReferenceData()
  const initialAssets = (pipeline.review?.assets || upload?.assets || [])
    .map(({ title, url, asset_type }) => ({ title, url, asset_type }))
  const [frontmatter] = useState(() => splitCanonicalMarkdown(upload?.markdown || '').frontmatter)
  const [markdown, setMarkdown] = useState(() => splitCanonicalMarkdown(upload?.markdown || '').body)
  const [reviewMetadata, setReviewMetadata] = useState(() => ({
    ...metadata,
    notes: metadata?.notes || '',
    audience: [...(metadata?.audience || [])],
    responsible_department: metadata?.responsible_department?.length
      ? [...metadata.responsible_department]
      : [''],
  }))
  const [assets, setAssets] = useState(initialAssets)
  const [persistedAssets, setPersistedAssets] = useState(initialAssets)
  const [validityStatus, setValidityStatus] = useState(metadata?.validity_status || 'unknown')
  const [busy, setBusy] = useState(false)
  const [assetBusy, setAssetBusy] = useState(false)

  if (!upload) {
    return (
      <>
        <PageHeader eyebrow="Ingestion / 02" title="Review nội dung" />
        <aside className="banner warn">
          Chưa có canonical Markdown.
          <p><button type="button" className="btn small" onClick={() => goTo('upload')}>← Tải Markdown</button></p>
        </aside>
      </>
    )
  }

  function setMetadataField(key, value) {
    setReviewMetadata((current) => ({ ...current, [key]: value }))
  }

  function toggleAudience(audience) {
    setReviewMetadata((current) => ({
      ...current,
      audience: current.audience.includes(audience)
        ? current.audience.filter((item) => item !== audience)
        : [...current.audience, audience],
    }))
  }

  function setResponsibleDepartment(index, value) {
    setReviewMetadata((current) => ({
      ...current,
      responsible_department: current.responsible_department.map((item, currentIndex) => currentIndex === index ? value : item),
    }))
  }

  function addResponsibleDepartment() {
    setReviewMetadata((current) => ({ ...current, responsible_department: [...current.responsible_department, ''] }))
  }

  function removeResponsibleDepartment(index) {
    setReviewMetadata((current) => ({
      ...current,
      responsible_department: current.responsible_department.filter((_, currentIndex) => currentIndex !== index),
    }))
  }

  const assetsReady = assets.every((asset) => asset.title.trim() && asset.url.trim() && asset.asset_type)
  const assetsChanged = JSON.stringify(assets) !== JSON.stringify(persistedAssets)
  const metadataReady = reviewMetadata.title?.trim()
    && reviewMetadata.document_type
    && reviewMetadata.responsible_department.length
    && reviewMetadata.responsible_department.every(Boolean)

  async function saveReview() {
    if (!assetsReady) return
    setBusy(true)
    try {
      const reviewedMarkdown = withFrontmatterValues(`${frontmatter}${markdown}`, {
        title: reviewMetadata.title,
        document_type: reviewMetadata.document_type,
        domain: reviewMetadata.domain,
        audience: reviewMetadata.audience,
        responsible_department: reviewMetadata.responsible_department,
        code: reviewMetadata.code,
        issued_date: reviewMetadata.issued_date,
        effective_date: reviewMetadata.effective_date,
        expiry_date: reviewMetadata.expiry_date,
        source_url: reviewMetadata.source_url,
        notes: reviewMetadata.notes,
        validity_status: validityStatus,
      })
      const reviewed = await api.reviewCanonicalMarkdown(upload.document_version_id, reviewedMarkdown, assets)
      const savedAssets = reviewed.assets || assets
      setMarkdown(splitCanonicalMarkdown(reviewed.markdown || reviewedMarkdown).body)
      update('upload', {
        ...upload,
        ...reviewed,
        assets: savedAssets,
        markdown: reviewed.markdown || reviewedMarkdown,
        metadata: {
          ...metadata,
          ...reviewMetadata,
          validity_status: validityStatus,
          ...(reviewed.metadata || {}),
        },
      })
      update('review', { ...reviewed, assets: savedAssets })
      update('chunkPreview', null)
      update('chunkApproved', false)
      update('ingest', null)
      notify.success('Đã lưu và approve canonical Markdown.')
      goTo('chunks')
    } catch (err) {
      notify.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function saveAssets() {
    setAssetBusy(true)
    try {
      const document = await api.updateDocumentAssets(upload.document_version_id, assets)
      const saved = (document.assets || []).map(({ title, url, asset_type }) => ({ title, url, asset_type }))
      setAssets(saved)
      setPersistedAssets(saved)
      update('upload', { ...upload, assets: saved })
      if (pipeline.review) update('review', { ...pipeline.review, assets: saved })
      notify.success('Đã cập nhật asset.')
    } catch (error) {
      notify.error(error.message)
    } finally {
      setAssetBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Ingestion / 02"
        title="Review và approve"
        description="Kiểm tra metadata và chỉnh nội dung Markdown. YAML frontmatter được hệ thống quản lý."
      />

      <section className="card" aria-labelledby="review-status-heading">
        <h2 id="review-status-heading">Trạng thái và metadata</h2>
        <dl className="kv">
          <dt>document_version_id</dt><dd className="mono">{upload.document_version_id}</dd>
          <dt>document_key</dt><dd className="mono">{metadata.document_key}</dd>
          <dt>version_key</dt><dd className="mono">{metadata.version_key}</dd>
          <dt>checksum OCR</dt><dd className="mono">{metadata.checksum}</dd>
          <dt>ocr_status</dt><dd><StatusBadge status={metadata.ocr_status} /></dd>
          <dt>review_status</dt><dd><StatusBadge status={pipeline.review?.review_status || metadata.review_status} /></dd>
          <dt>rag_status</dt><dd><StatusBadge status={pipeline.review?.rag_status || metadata.rag_status} /></dd>
          <dt>Hiệu lực</dt><dd>
            <select aria-label="Tình trạng hiệu lực" value={validityStatus} disabled={referencesLoading} onChange={(event) => setValidityStatus(event.target.value)}>
              {enumOptions.validity_statuses.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </dd>
          {metadata.language && <><dt>Ngôn ngữ</dt><dd className="mono">{metadata.language}</dd></>}
          <dt>Tài liệu gốc</dt><dd><a className="text-link" href={`/api/v1/admin/document-versions/${upload.document_version_id}/source-preview`} target="_blank" rel="noreferrer">Mở tài liệu gốc</a></dd>
          {pipeline.review && <><dt>Bước kế tiếp</dt><dd className="mono">chunking</dd></>}
        </dl>

        <fieldset className="form-grid review-metadata" disabled={referencesLoading}>
          <legend>Thông tin tài liệu</legend>
          <label className="field" htmlFor="review-title">
            <span>Tiêu đề <b aria-hidden="true">*</b></span>
            <input id="review-title" value={reviewMetadata.title || ''} onChange={(event) => setMetadataField('title', event.target.value)} required />
          </label>
          <label className="field" htmlFor="review-document-type">
            <span>Loại tài liệu <b aria-hidden="true">*</b></span>
            <select id="review-document-type" value={reviewMetadata.document_type || ''} onChange={(event) => setMetadataField('document_type', event.target.value)} required>
              <option value="">— Chọn loại tài liệu —</option>
              {documentTypes.filter((type) => type.is_active).map((type) => <option key={type.code} value={type.code}>{type.name} ({type.code})</option>)}
            </select>
          </label>
          <label className="field" htmlFor="review-domain">
            <span>Domain</span>
            <select id="review-domain" value={reviewMetadata.domain || 'unknown'} onChange={(event) => setMetadataField('domain', event.target.value)}>
              {enumOptions.domains.map((domain) => <option key={domain} value={domain}>{domain}</option>)}
            </select>
          </label>
          <label className="field" htmlFor="review-code">
            <span>Số hiệu</span>
            <input id="review-code" value={reviewMetadata.code || ''} onChange={(event) => setMetadataField('code', event.target.value)} />
          </label>
          <label className="field" htmlFor="review-issued-date">
            <span>Ngày ban hành</span>
            <input id="review-issued-date" type="date" value={reviewMetadata.issued_date || ''} onChange={(event) => setMetadataField('issued_date', event.target.value)} />
          </label>
          <label className="field" htmlFor="review-effective-date">
            <span>Ngày hiệu lực</span>
            <input id="review-effective-date" type="date" value={reviewMetadata.effective_date || ''} onChange={(event) => setMetadataField('effective_date', event.target.value)} />
          </label>
          <label className="field" htmlFor="review-expiry-date">
            <span>Ngày hết hiệu lực</span>
            <input id="review-expiry-date" type="date" value={reviewMetadata.expiry_date || ''} onChange={(event) => setMetadataField('expiry_date', event.target.value)} />
          </label>
          <label className="field" htmlFor="review-source-url">
            <span>URL nguồn</span>
            <input id="review-source-url" type="url" value={reviewMetadata.source_url || ''} onChange={(event) => setMetadataField('source_url', event.target.value)} placeholder="https://…" />
          </label>
          <label className="field" htmlFor="review-notes">
            <span>Ghi chú</span>
            <textarea className="metadata-notes" id="review-notes" value={reviewMetadata.notes || ''} onChange={(event) => setMetadataField('notes', event.target.value)} rows={1} />
          </label>
        </fieldset>

        <fieldset className="audience-fieldset review-metadata-section" disabled={referencesLoading}>
          <legend>Đối tượng sử dụng</legend>
          <menu className="pill-row">
            {enumOptions.audiences.map((audience) => (
              <li key={audience}><button type="button" className="tag" aria-pressed={reviewMetadata.audience.includes(audience)} onClick={() => toggleAudience(audience)}>{reviewMetadata.audience.includes(audience) ? '✓ ' : ''}{audience}</button></li>
            ))}
          </menu>
        </fieldset>

        <fieldset className="responsible-departments review-metadata-section" disabled={referencesLoading}>
          <legend>Phòng ban phụ trách <b aria-hidden="true">*</b></legend>
          {reviewMetadata.responsible_department.map((selectedCode, index) => (
            <div className="responsible-department-row" key={`${index}-${selectedCode}`}>
              <label className="field" htmlFor={`review-responsible-department-${index}`}>
                <span className="sr-only">Phòng ban phụ trách {index + 1}</span>
                <select id={`review-responsible-department-${index}`} value={selectedCode} onChange={(event) => setResponsibleDepartment(index, event.target.value)} required>
                  <option value="">— Chọn phòng ban —</option>
                  {departments.filter((department) => department.is_active && (department.code === selectedCode || !reviewMetadata.responsible_department.includes(department.code))).map((department) => (
                    <option key={department.code} value={department.code}>{department.code} — {department.name}</option>
                  ))}
                </select>
              </label>
              {reviewMetadata.responsible_department.length > 1 && <button type="button" className="btn ghost small danger-icon" onClick={() => removeResponsibleDepartment(index)} aria-label={`Bỏ phòng ban phụ trách ${index + 1}`} title="Bỏ phòng ban"><Trash2 aria-hidden="true" /></button>}
            </div>
          ))}
          <button type="button" className="btn ghost small" onClick={addResponsibleDepartment} disabled={reviewMetadata.responsible_department.some((item) => !item)}>+ Thêm phòng ban</button>
        </fieldset>
      </section>

      <section className="card" aria-labelledby="review-content-heading">
        <h2 id="review-content-heading">Nội dung cần review</h2>
        <label className="field" htmlFor="canonical-markdown">
          <span>Canonical Markdown</span>
          <LineNumberedTextarea
            id="canonical-markdown"
            className="markdown-editor large"
            value={markdown}
            onChange={(event) => setMarkdown(event.target.value)}
          />
        </label>

        <AssetEditor
          assets={assets}
          assetTypes={enumOptions.asset_types || []}
          disabled={referencesLoading || assetBusy}
          idPrefix="review-asset"
          hint="Thêm biểu mẫu hoặc tài liệu cần mở từ câu trả lời. Asset không được đưa vào chunk/vector."
          onChange={setAssets}
        >
          <button type="button" className="btn small" onClick={saveAssets} disabled={assetBusy || !assetsReady || !assetsChanged}>
            {assetBusy ? 'Đang lưu…' : 'Lưu asset'}
          </button>
        </AssetEditor>

        <nav className="foot-nav" aria-label="Điều hướng review">
          <button type="button" className="btn ghost" onClick={() => goTo('upload')}>← Tải lại file</button>
          <button type="button" className="btn" disabled={busy || !markdown.trim() || !assetsReady || !metadataReady} onClick={saveReview}>
            {busy ? 'Đang approve…' : 'Lưu và duyệt sang Review chunks →'}
          </button>
        </nav>
      </section>
    </>
  )
}
