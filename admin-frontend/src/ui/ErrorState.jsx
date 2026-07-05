export default function ErrorState({ title = 'Đã xảy ra lỗi', message, action }) {
  return (
    <div className="banner warn">
      <strong>{title}</strong>
      {message && <p style={{ margin: '6px 0 0' }}>{message}</p>}
      {action && <div style={{ marginTop: 10 }}>{action}</div>}
    </div>
  )
}
