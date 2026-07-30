import { useState } from 'react'
import { api } from '../api/client.js'
import PageHeader from '../components/PageHeader.jsx'
import { notify } from '../lib/notify.js'

function reportText(report) {
  if (typeof report === 'string') return report
  return [report.code, report.page && `trang ${report.page}`, report.reason]
    .filter(Boolean)
    .join(' — ')
}

export default function ChunkReviewStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const preview = pipeline.chunkPreview
  const errors = preview?.errors || []
  const warnings = preview?.warnings || []
  const [busy, setBusy] = useState(false)

  if (!pipeline.review) {
    return (
      <>
        <PageHeader eyebrow="Ingestion / 03" title="Review chunks" />
        <aside className="banner warn">
          Canonical Markdown chưa được approve.
          <p><button type="button" className="btn small" onClick={() => goTo('review')}>← Review Markdown</button></p>
        </aside>
      </>
    )
  }

  async function createPreview() {
    setBusy(true)
    update('chunkApproved', false)
    try {
      update('chunkPreview', await api.previewChunks(upload.document_version_id))
      notify.success('Đã tạo chunk preview.')
    } catch (err) {
      notify.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  function approvePreview() {
    update('chunkApproved', true)
    goTo('ingest')
  }

  return (
    <>
      <PageHeader
        eyebrow="Ingestion / 03"
        title="Review chunks"
        description="Kiểm tra parent/child, heading, trang, độ dài và cảnh báo trước khi embedding."
      />

      <section className="card" aria-labelledby="preview-action-heading">
        <h2 id="preview-action-heading">Chunk preview</h2>
        <dl className="kv">
          <dt>document_version_id</dt><dd className="mono">{upload.document_version_id}</dd>
          <dt>version_key</dt><dd className="mono">{upload.metadata.version_key}</dd>
          <dt>Trạng thái</dt><dd>{pipeline.chunkApproved ? 'Đã duyệt' : preview ? 'Chờ duyệt' : 'Chưa tạo'}</dd>
        </dl>
        <button type="button" className="btn" disabled={busy} onClick={createPreview}>
          {busy ? 'Đang tạo preview…' : preview ? 'Tạo lại preview' : 'Tạo chunk preview'}
        </button>
      </section>

      {preview && (
        <>
          <section className="card" aria-labelledby="preview-summary-heading">
            <h2 id="preview-summary-heading">Tổng quan</h2>
            <dl className="kv">
              <dt>parent_chunks</dt><dd>{preview.parent_chunks}</dd>
              <dt>child_chunks</dt><dd>{preview.child_chunks}</dd>
              <dt>total_chunks</dt><dd>{preview.total_chunks}</dd>
              <dt>warnings</dt><dd>{warnings.length}</dd>
              <dt>errors</dt><dd>{errors.length}</dd>
            </dl>

            {errors.length > 0 && (
              <aside className="banner warn" role="alert">
                <strong>Lỗi phải sửa trước khi index</strong>
                <ul>{errors.map((item, index) => <li key={index}>{reportText(item)}</li>)}</ul>
              </aside>
            )}

            {warnings.length > 0 && (
              <aside className="banner">
                <strong>Cảnh báo cần kiểm tra</strong>
                <ul>{warnings.map((item, index) => <li key={index}>{reportText(item)}</li>)}</ul>
              </aside>
            )}
          </section>

          <section className="card" aria-labelledby="chunk-list-heading">
            <h2 id="chunk-list-heading">Danh sách chunks</h2>
            <figure className="table-scroll">
              <table>
                <caption>Parent và child chunks được tạo từ canonical Markdown</caption>
                <thead>
                  <tr>
                    <th scope="col">Loại</th>
                    <th scope="col">Chunk key</th>
                    <th scope="col">Quan hệ item</th>
                    <th scope="col">Heading</th>
                    <th scope="col">Trang</th>
                    <th scope="col">Tokens</th>
                    <th scope="col">Nội dung</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.chunks.map((chunk) => (
                    <tr key={chunk.chunk_key}>
                      <td>{chunk.chunk_type}</td>
                      <td className="mono">{chunk.chunk_key}<small className="document-key muted">{chunk.parent_chunk_key}</small></td>
                      <td>
                        <span className="mono">{chunk.item_path?.join(' › ') || '—'}</span>
                        {chunk.parent_item_key && <small className="document-key muted">parent: {chunk.parent_item_key}</small>}
                      </td>
                      <td>{chunk.heading_path?.join(' › ') || '—'}</td>
                      <td>{chunk.page_start || '—'}{chunk.page_end && chunk.page_end !== chunk.page_start ? `–${chunk.page_end}` : ''}</td>
                      <td>{chunk.token_count ?? '—'}</td>
                      <td>{chunk.content_preview}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </figure>
          </section>

          <nav className="foot-nav" aria-label="Duyệt chunk preview">
            <button type="button" className="btn ghost" onClick={() => goTo('review')}>← Sửa Markdown</button>
            <button type="button" className="btn" disabled={errors.length > 0} onClick={approvePreview}>Approve chunks và tiếp tục →</button>
          </nav>
        </>
      )}
    </>
  )
}
