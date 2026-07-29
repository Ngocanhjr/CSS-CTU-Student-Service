import { Trash2 } from 'lucide-react'

const LABELS = {
  form: 'Biểu mẫu',
  template: 'Mẫu tài liệu',
  guide: 'Hướng dẫn',
  attachment: 'Đính kèm',
}

export default function AssetEditor({ assets, assetTypes, disabled = false, idPrefix, legend = 'Asset liên kết', hint, onChange, children }) {
  const setAsset = (index, key, value) => onChange(assets.map((asset, currentIndex) => (
    currentIndex === index ? { ...asset, [key]: value } : asset
  )))

  return (
    <fieldset className="asset-list" disabled={disabled}>
      <legend>{legend}</legend>
      {hint && <p className="hint">{hint}</p>}
      {assets.map((asset, index) => (
        <div className="asset-row" key={index}>
          <label className="field" htmlFor={`${idPrefix}-title-${index}`}>
            <span>Tiêu đề asset <b aria-hidden="true">*</b></span>
            <input id={`${idPrefix}-title-${index}`} value={asset.title} onChange={(event) => setAsset(index, 'title', event.target.value)} required />
          </label>
          <label className="field" htmlFor={`${idPrefix}-url-${index}`}>
            <span>Link <b aria-hidden="true">*</b></span>
            <input id={`${idPrefix}-url-${index}`} type="url" value={asset.url} onChange={(event) => setAsset(index, 'url', event.target.value)} placeholder="https://…" required />
          </label>
          <label className="field" htmlFor={`${idPrefix}-type-${index}`}>
            <span>Loại</span>
            <select id={`${idPrefix}-type-${index}`} value={asset.asset_type} onChange={(event) => setAsset(index, 'asset_type', event.target.value)} required>
              {assetTypes.map((type) => <option key={type} value={type}>{LABELS[type] || type}</option>)}
            </select>
          </label>
          <button type="button" className="btn ghost small danger-icon" onClick={() => onChange(assets.filter((_, currentIndex) => currentIndex !== index))} aria-label={`Xóa asset ${index + 1}`} title="Xóa asset"><Trash2 aria-hidden="true" /></button>
        </div>
      ))}
      <div className="asset-actions">
        <button type="button" className="btn ghost small" onClick={() => onChange([...assets, { title: '', url: '', asset_type: assetTypes[0] || '' }])} disabled={!assetTypes.length}>+ Thêm asset</button>
        {children}
      </div>
    </fieldset>
  )
}
