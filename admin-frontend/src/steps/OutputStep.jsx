import { useState } from 'react'
import StatusBadge from '../components/StatusBadge.jsx'
import { documentTypes, departments } from '../api/referenceData.js'

function buildOutput(pipeline) {
  const { upload, ocr, metadata, ingest } = pipeline
  const docType = documentTypes.find((t) => t.id === metadata.document_type_id)
  return {
    document: {
      document_key: upload.document_key,
      title: metadata.title,
      domain: metadata.domain || null,
      audience: metadata.audience,
      document_type: docType ? { id: docType.id, code: docType.code, name: docType.name } : null,
    },
    document_version: {
      version_key: upload.version_key,
      title: metadata.title,
      code: metadata.code || null,
      issued_date: metadata.issued_date || null,
      is_latest: true,
      source_path: upload.source_path,
      canonical_markdown_path: ocr.canonical_markdown_path,
      file_type: upload.file_type,
      language: metadata.language,
      issuing_authority: metadata.issuing_authority || null,
      signer: metadata.signer || null,
      checksum: upload.checksum,
      ocr_status: 'done',
      review_status: 'approved',
      rag_status: ingest.rag_status,
    },
    document_recipients: metadata.recipients.map((r) => ({
      department: departments.find((d) => d.id === r.department_id)?.code,
      effective_date: r.effective_date,
    })),
    chunks: {
      parent_chunks: ingest.parent_chunks,
      child_chunks: ingest.child_chunks,
      total_chunks: ingest.total_chunks,
      sample_chunk_keys: ingest.sample_chunk_keys,
    },
    qdrant: {
      collection: 'ctu_documents',
      points_upserted: ingest.qdrant_points,
    },
  }
}

export default function OutputStep({ pipeline, goTo }) {
  const [copied, setCopied] = useState(false)
  const complete = pipeline.upload && pipeline.ocr && pipeline.metadata && pipeline.ingest

  if (!complete) {
    return (
      <>
        <div className="page-head"><h1>5 — Kết quả</h1></div>
        <div className="banner warn">
          Quy trình chưa hoàn tất. Hãy chạy ingest ở bước 4 trước.
          <div style={{ marginTop: 10 }}>
            <button className="btn small" onClick={() => goTo('ingest')}>← Về bước ingest</button>
          </div>
        </div>
      </>
    )
  }

  const output = buildOutput(pipeline)
  const json = JSON.stringify(output, null, 2)

  async function copy() {
    try {
      await navigator.clipboard.writeText(json)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  function download() {
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${pipeline.upload.version_key}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <div className="page-head">
        <h1>5 — Kết quả</h1>
        <p>Bản ghi đã ghi vào CSDL (mô phỏng). Đây là output cuối của quy trình ingest.</p>
      </div>

      <div className="card">
        <h2>Tóm tắt</h2>
        <dl className="kv">
          <dt>document_key</dt><dd className="mono">{output.document.document_key}</dd>
          <dt>version_key</dt><dd className="mono">{output.document_version.version_key}</dd>
          <dt>ocr_status</dt><dd><StatusBadge status="done" /></dd>
          <dt>review_status</dt><dd><StatusBadge status="approved" /></dd>
          <dt>rag_status</dt><dd><StatusBadge status={output.document_version.rag_status} /></dd>
          <dt>Tổng chunks</dt><dd>{output.chunks.total_chunks}</dd>
          <dt>Qdrant points</dt><dd>{output.qdrant.points_upserted}</dd>
        </dl>
      </div>

      <div className="card">
        <h2>Output JSON</h2>
        <div className="pill-row" style={{ marginBottom: 12 }}>
          <button className="btn small" onClick={copy}>{copied ? '✓ Đã copy' : 'Copy JSON'}</button>
          <button className="btn ghost small" onClick={download}>Tải .json</button>
        </div>
        <div className="json-out">{json}</div>
      </div>

      <div className="foot-nav">
        <button className="btn ghost" onClick={() => goTo('ingest')}>← Quay lại</button>
      </div>
    </>
  )
}
