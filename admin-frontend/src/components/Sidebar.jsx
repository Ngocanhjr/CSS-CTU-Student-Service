export default function Sidebar({ steps, active, done, onSelect, onReset, extraNav }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        CTU Ingestion
        <small>Admin Console — prototype</small>
      </div>
      {steps.map((s, i) => (
        <button
          key={s.key}
          className={`nav-item ${active === s.key ? 'active' : ''} ${done[s.key] ? 'done' : ''}`}
          onClick={() => onSelect(s.key)}
        >
          <span className="idx">{done[s.key] ? '✓' : i + 1}</span>
          {s.label}
        </button>
      ))}

      {extraNav?.length > 0 && (
        <>
          <div className="divider" />
          {extraNav.map((s) => (
            <button
              key={s.key}
              className={`nav-item ${active === s.key ? 'active' : ''}`}
              onClick={() => onSelect(s.key)}
            >
              <span className="idx">{s.icon || '📄'}</span>
              {s.label}
            </button>
          ))}
        </>
      )}

      <div style={{ flex: 1 }} />
      <button className="btn ghost small" onClick={onReset}>
        Bắt đầu tài liệu mới
      </button>
    </aside>
  )
}
