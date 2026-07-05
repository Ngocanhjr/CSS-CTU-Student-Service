import { useState } from 'react'
import { mockApi } from '../api/mockClient.js'
import {
  documentTypes,
  departments,
  audienceOptions,
  domainOptions,
  languageOptions,
} from '../api/referenceData.js'

function initialMeta(upload) {
  return {
    title: '',
    document_type_id: documentTypes[0].id,
    domain: '',
    audience: [],
    code: '',
    issued_date: '',
    issuing_authority: '',
    signer: '',
    language: 'vi',
    recipients: [], // [{ department_id, effective_date }]
  }
}

export default function MetadataStep({ pipeline, update, goTo }) {
  const upload = pipeline.upload
  const ocr = pipeline.ocr
  const [meta, setMeta] = useState(() => pipeline.metadata || initialMeta(upload))
  const [busy, setBusy] = useState(false)
  const [deptToAdd, setDeptToAdd] = useState(departments[0].id)
  const [effDate, setEffDate] = useState('')

  if (!ocr) {
    return (
      <>
        <div className="page-head"><h1>3 — Gắn metadata</h1></div>
        <div className="banner warn">
          Chưa có kết quả OCR. Hãy chạy OCR ở bước 2 trước.
          <div style={{ marginTop: 10 }}>
            <button className="btn small" onClick={() => goTo('ocr')}>← Về bước OCR</button>
          </div>
        </div>
      </>
    )
  }

  function set(key, value) {
    setMeta((m) => ({ ...m, [key]: value }))
  }

  function toggleAudience(a) {
    setMeta((m) => ({
      ...m,
      audience: m.audience.includes(a)
        ? m.audience.filter((x) => x !== a)
        : [...m.audience, a],
    }))
  }

  function addRecipient() {
    if (!effDate) return
    if (meta.recipients.some((r) => r.department_id === deptToAdd && r.effective_date === effDate)) return
    set('recipients', [...meta.recipients, { department_id: deptToAdd, effective_date: effDate }])
    setEffDate('')
  }

  function removeRecipient(i) {
    set('recipients', meta.recipients.filter((_, idx) => idx !== i))
  }

  const valid = meta.title.trim() && meta.document_type_id

  async function onSave() {
    setBusy(true)
    try {
      await mockApi.saveMetadata(upload.document_version_id, meta)
      update('metadata', meta)
      goTo('ingest')
    } finally {
      setBusy(false)
    }
  }

  const deptName = (id) => departments.find((d) => d.id === id)?.name || id

  return (
    <>
      <div className="page-head">
        <h1>3 — Gắn metadata</h1>
        <p>Nhập metadata cho tài liệu và version (lưu vào PostgreSQL css).</p>
      </div>

      <div className="card">
        <h2>Thông tin tài liệu</h2>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Tiêu đề *</span>
              <input value={meta.title} onChange={(e) => set('title', e.target.value)} placeholder="Tiêu đề tài liệu" />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Loại tài liệu (document_type) *</span>
              <select value={meta.document_type_id} onChange={(e) => set('document_type_id', Number(e.target.value))}>
                {documentTypes.map((t) => (
                  <option key={t.id} value={t.id}>{t.name} ({t.code})</option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Domain</span>
              <select value={meta.domain} onChange={(e) => set('domain', e.target.value)}>
                <option value="">— chọn —</option>
                {domainOptions.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Audience (JSONB)</span>
              <div className="pill-row">
                {audienceOptions.map((a) => (
                  <button
                    key={a}
                    className={`tag ${meta.audience.includes(a) ? '' : ''}`}
                    style={{ borderColor: meta.audience.includes(a) ? 'var(--accent)' : 'var(--border)' }}
                    onClick={() => toggleAudience(a)}
                    type="button"
                  >
                    {meta.audience.includes(a) ? '✓ ' : ''}{a}
                  </button>
                ))}
              </div>
            </label>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Thông tin version</h2>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Số hiệu (code)</span>
              <input value={meta.code} onChange={(e) => set('code', e.target.value)} placeholder="VD: 1234/QĐ-ĐHCT" />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Ngày ban hành (issued_date)</span>
              <input type="date" value={meta.issued_date} onChange={(e) => set('issued_date', e.target.value)} />
            </label>
          </div>
        </div>
        <div className="row">
          <div className="col">
            <label className="field">
              <span>Cơ quan ban hành (issuing_authority)</span>
              <input value={meta.issuing_authority} onChange={(e) => set('issuing_authority', e.target.value)} placeholder="VD: Trường ĐH Cần Thơ" />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Người ký (signer)</span>
              <input value={meta.signer} onChange={(e) => set('signer', e.target.value)} placeholder="VD: Hiệu trưởng" />
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Ngôn ngữ</span>
              <select value={meta.language} onChange={(e) => set('language', e.target.value)}>
                {languageOptions.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </label>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Phòng ban tiếp nhận (document_recipients)</h2>
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <div className="col">
            <label className="field">
              <span>Phòng ban</span>
              <select value={deptToAdd} onChange={(e) => setDeptToAdd(Number(e.target.value))}>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.code})</option>)}
              </select>
            </label>
          </div>
          <div className="col">
            <label className="field">
              <span>Ngày tiếp nhận (effective_date)</span>
              <input type="date" value={effDate} onChange={(e) => setEffDate(e.target.value)} />
            </label>
          </div>
          <div style={{ marginBottom: 12 }}>
            <button className="btn ghost small" type="button" onClick={addRecipient} disabled={!effDate}>+ Thêm</button>
          </div>
        </div>
        {meta.recipients.length > 0 ? (
          <table>
            <thead><tr><th>Phòng ban</th><th>effective_date</th><th></th></tr></thead>
            <tbody>
              {meta.recipients.map((r, i) => (
                <tr key={i}>
                  <td>{deptName(r.department_id)}</td>
                  <td className="mono">{r.effective_date}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn ghost small" onClick={() => removeRecipient(i)}>Xóa</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="hint">Chưa có phòng ban nào. Quan hệ version ↔ phòng ban là M:N qua bảng document_recipients.</p>
        )}
      </div>

      <div className="foot-nav">
        <button className="btn ghost" onClick={() => goTo('ocr')}>← Quay lại</button>
        <button className="btn" disabled={!valid || busy} onClick={onSave}>
          {busy ? 'Đang lưu…' : 'Lưu metadata & tiếp tục →'}
        </button>
      </div>
    </>
  )
}
