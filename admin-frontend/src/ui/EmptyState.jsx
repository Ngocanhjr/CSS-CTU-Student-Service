export default function EmptyState({ icon = '📄', title, message, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      {title && <p className="empty-title">{title}</p>}
      {message && <p className="hint">{message}</p>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  )
}
