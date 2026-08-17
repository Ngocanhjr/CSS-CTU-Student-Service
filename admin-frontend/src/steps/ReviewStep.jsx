import { useState } from 'react'
import { toast } from 'react-toastify'
import { api } from '../api/client.js'
import AssetEditor from '../components/AssetEditor.jsx'
import PageHeader from '../components/PageHeader.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import LineNumberedTextarea from '../components/LineNumberedTextarea.jsx'
import { useReferenceData } from '../hooks/useReferenceData.js'
import AudiencePicker from '../components/AudiencePicker.jsx'
import ResponsibleDepartmentPicker from '../components/ResponsibleDepartmentPicker.jsx'
import { splitCanonicalMarkdown } from '../utils/markdown.js'

export default function ReviewStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const metadata = upload?.metadata
  const { documentTypes, departments, enumOptions, loading: referencesLoading } = useReferenceData()
  const initialAssets = (pipeline.review?.assets || upload?.assets || [])
    .map(({ title, url, asset_type }) => ({ title, url, asset_type }))
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

  const assetsReady = assets.every((asset) => asset.title.trim() && asset.url.trim() && asset.asset_type)
  const assetsChanged = JSON.stringify(assets) !== JSON.stringify(persistedAssets)
  const metadataReady = reviewMetadata.title?.trim()
    && reviewMetadata.document_type
    && reviewMetadata.responsible_department.length
    && reviewMetadata.responsible_department.every(Boolean)

  async function openStoredFile(fileType) {
    const previewWindow = window.open('', '_blank')
    if (!previewWindow) {
      toast.error('Trình duyệt đã chặn tab xem tài liệu.')
      return
    }
    previewWindow.opener = null
    try {
      const { url } = await api.getDocumentPreviewUrl(metadata.version_key, fileType)
      previewWindow.location.replace(url)
    } catch (error) {
      previewWindow.close()
      toast.error(error.message)
    }
  }

  function downloadCanonicalMarkdown() {
    const savedMarkdown = pipeline.review?.markdown || upload.markdown
    const url = URL.createObjectURL(new Blob(
      [savedMarkdown],
      { type: 'text/markdown;charset=utf-8' },
    ))
    const link = document.createElement('a')
    link.href = url
    link.download = `${metadata.version_key || 'canonical'}.md`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  async function saveReview() {
    if (!assetsReady) return
    setBusy(true)
    try {
      const reviewed = await api.reviewCanonicalMarkdown(
        upload.document_version_id,
        markdown,
        reviewMetadata,
        assets,
      )
      const savedAssets = reviewed.assets || assets
      setMarkdown(splitCanonicalMarkdown(reviewed.markdown).body)
      update('upload', {
        ...upload,
        ...reviewed,
        assets: savedAssets,
        markdown: reviewed.markdown,
        metadata: {
          ...metadata,
          ...reviewMetadata,
          ...(reviewed.metadata || {}),
        },
      })
      update('review', { ...reviewed, assets: savedAssets })
      update('chunkPreview', null)
      update('chunkApproved', false)
      update('ingest', null)
      toast.success('Đã lưu và approve canonical Markdown.')
      goTo('chunks')
    } catch (err) {
      toast.error(err.message)
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
      toast.success('Đã cập nhật asset.')
    } catch (error) {
      toast.error(error.message)
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
            <select aria-label="Tình trạng hiệu lực" value={reviewMetadata.validity_status} disabled={referencesLoading} onChange={(event) => setMetadataField('validity_status', event.target.value)}>
              {enumOptions.validity_statuses.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </dd>
          {metadata.language && <><dt>Ngôn ngữ</dt><dd className="mono">{metadata.language}</dd></>}
          <dt>Tệp tài liệu</dt>
          <dd>
            <nav className="document-file-actions" aria-label="Xem và tải tệp tài liệu">
              <button type="button" className="text-link" onClick={() => openStoredFile('source')}>Mở tài liệu gốc</button>
              <button type="button" className="text-link" onClick={() => openStoredFile('canonical_markdown')}>Mở Markdown đã lưu</button>
              <button type="button" className="text-link" onClick={downloadCanonicalMarkdown}>Tải Markdown đã lưu</button>
            </nav>
          </dd>
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
          <label className="field checkbox-field" htmlFor="review-is-latest">
            <input id="review-is-latest" type="checkbox" checked={Boolean(reviewMetadata.is_latest)} onChange={(event) => setMetadataField('is_latest', event.target.checked)} />
            <span>Phiên bản mới nhất</span>
          </label>
        </fieldset>

        <AudiencePicker
          options={enumOptions.audiences}
          value={reviewMetadata.audience}
          onChange={(value) => setMetadataField('audience', value)}
          disabled={referencesLoading}
          className="review-metadata-section"
        />

        <ResponsibleDepartmentPicker
          departments={departments}
          value={reviewMetadata.responsible_department}
          onChange={(value) => setMetadataField('responsible_department', value)}
          idPrefix="review-responsible-department"
          disabled={referencesLoading}
          className="review-metadata-section"
        />
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
