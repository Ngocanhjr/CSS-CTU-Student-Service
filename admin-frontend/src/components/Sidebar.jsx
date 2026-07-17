export default function Sidebar({ steps, active, done, onSelect, onReset, extraNav }) {
  return (
    <aside className="sidebar" aria-label="Thanh điều hướng quản trị">
      <header className="brand">
        <strong>CTU Ingestion</strong>
        <small>Quản trị tài liệu</small>
      </header>

      <nav aria-label="Quy trình nhập liệu">
        <ol className="nav-list">
          {steps.map((step, index) => (
            <li key={step.key}>
              <button
                type="button"
                className={`nav-item ${active === step.key ? 'active' : ''} ${done[step.key] ? 'done' : ''}`}
                aria-current={active === step.key ? 'step' : undefined}
                onClick={() => onSelect(step.key)}
              >
                <span className="idx" aria-hidden="true">{done[step.key] ? '✓' : index + 1}</span>
                {step.label}
              </button>
            </li>
          ))}
        </ol>
      </nav>

      {extraNav?.length > 0 && (
        <nav className="secondary-nav" aria-label="Quản lý dữ liệu">
          <ul className="nav-list">
            {extraNav.map((item) => (
              <li key={item.key}>
                <button
                  type="button"
                  className={`nav-item ${active === item.key ? 'active' : ''}`}
                  aria-current={active === item.key ? 'page' : undefined}
                  onClick={() => onSelect(item.key)}
                >
                  <span className="idx" aria-hidden="true">{item.icon || '📄'}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <button type="button" className="btn ghost small reset-action" onClick={onReset}>
        Bắt đầu tài liệu mới
      </button>
    </aside>
  )
}
