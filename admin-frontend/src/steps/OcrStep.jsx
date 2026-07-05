import { useState } from 'react'
import { mockApi } from '../api/mockClient.js'
import StatusBadge from '../components/StatusBadge.jsx'
import StepProgress from '../components/StepProgress.jsx'

const OCR_STEPS = [
  { key: 'queued', label: 'Đưa vào hàng đợi LlamaParse' },
  { key: 'parsing', label: 'Phân tích tài liệu (OCR)' },
  { key: 'markdown', label: 'Sinh canonical markdown' },
  { key: 'page_markers', label: 'Chèn page markers <!-- page: N -->' },
]

export default function OcrStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const ocr = pipeline.ocr
  const [busy, setBusy] = useState(false)
  const [steps, setSteps] = useState(
    OCR_STEPS.map((s) => ({ ...s, state: 'pending' })),
  )

  if (!upload) {
    return (
      <>
        <div className="page-head">
          <h1>2 — OCR / Parse</h1>
        </div>
        <div className="banner warn">
          Chưa có tài liệu. Hãy tải tài liệu ở bước 1 trước.
          <div style={{ marginTop: 10 }}>
            <button className="btn small" onClick={() => goTo('upload')}>← Về bước tải lên</button>
          </div>
        </div>
      </>
    )
  }

  async function onRun() {
    setBusy(true)
    setSteps(OCR_STEPS.map((s) => ({ ...s, state: 'pending' })))
    try {
      const res = await mockApi.runOcr(
        { fileName: upload.fileName, title: upload.document_key },
        (step) => {
          setSteps((prev) =>
            prev.map((s) => (s.key === step.key ? { ...s, state: step.state } : s)),
          )
        },
      )
      update('ocr', res)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>2 — OCR / Parse</h1>
        <p>Chạy LlamaParse để trích xuất nội dung thành canonical markdown.</p>
      </div>

      <div className="card">
        <h2>Tài liệu nguồn</h2>
        <dl className="kv">
          <dt>version_key</dt><dd className="mono">{upload.version_key}</dd>
          <dt>source_path</dt><dd className="mono">{upload.source_path}</dd>
          <dt>ocr_status</dt><dd><StatusBadge status={ocr ? ocr.ocr_status : upload.ocr_status} /></dd>
        </dl>
        <button className="btn" disabled={busy} onClick={onRun}>
          {busy ? 'Đang chạy OCR…' : ocr ? 'Chạy lại OCR' : 'Chạy OCR'}
        </button>
      </div>

      {(busy || ocr) && (
        <div className="card">
          <h2>Tiến trình</h2>
          <StepProgress steps={steps} />
        </div>
      )}

      {ocr && (
        <div className="card">
          <h2>Kết quả OCR</h2>
          <dl className="kv">
            <dt>canonical_markdown_path</dt><dd className="mono">{ocr.canonical_markdown_path}</dd>
            <dt>page_count</dt><dd>{ocr.page_count}</dd>
            <dt>char_count</dt><dd>{ocr.char_count}</dd>
          </dl>
          <div className="divider" />
          <span className="muted" style={{ fontSize: 12 }}>Xem trước canonical markdown</span>
          <textarea
            style={{ marginTop: 8, minHeight: 200 }}
            value={ocr.markdown}
            onChange={(e) => update('ocr', { ...ocr, markdown: e.target.value })}
          />
          <p className="hint">Bạn có thể sửa markdown trước khi gắn metadata (mô phỏng review/need_fix).</p>
          <div className="foot-nav">
            <button className="btn ghost" onClick={() => goTo('upload')}>← Quay lại</button>
            <button className="btn" onClick={() => goTo('metadata')}>Tiếp tục: Metadata →</button>
          </div>
        </div>
      )}
    </>
  )
}
