export default function LoadingState({ message = 'Đang tải…' }) {
  return (
    <p className="hint">
      <span className="spin" style={{ display: 'inline-block', marginRight: 6 }}>◐</span>
      {message}
    </p>
  )
}
