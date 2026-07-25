export default function Sidebar({ steps, active, onSelect, onReset }) {
  const processingActive = steps.some((step) => step.key === active)

  return (
    <aside className="sidebar" aria-label="Thanh điều hướng quản trị">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">CTU</span>
        <span className="brand-copy">
          <strong>Ingestion</strong>
          <small>Quản trị tài liệu</small>
        </span>
      </header>

      <nav aria-label="Khu vực quản trị">
        <ul className="nav-list section-list">
          <li>
            <button
              type="button"
              className={`nav-item section-item ${processingActive ? 'active' : ''}`}
              aria-current={processingActive ? 'page' : undefined}
              onClick={() => onSelect(processingActive ? active : 'upload')}
            >
              <span className="idx" aria-hidden="true">01</span>
              Xử lý tài liệu
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`nav-item section-item ${active.startsWith('documents') ? 'active' : ''}`}
              aria-current={active.startsWith('documents') ? 'page' : undefined}
              onClick={() => onSelect('documents')}
            >
              <span className="idx" aria-hidden="true">02</span>
              Quản lý tài liệu
            </button>
          </li>
        </ul>
      </nav>

      <button type="button" className="btn ghost small reset-action" onClick={onReset}>
        Bắt đầu tài liệu mới
      </button>
    </aside>
  )
}
