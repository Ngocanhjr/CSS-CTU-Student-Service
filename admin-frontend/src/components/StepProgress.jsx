const ICON = {
  pending: '○',
  running: '◐',
  done: '✓',
  failed: '✕',
}

export default function StepProgress({ steps }) {
  if (!steps?.length) return null
  return (
    <div className="step-progress">
      {steps.map((s) => (
        <div key={s.key} className={`step ${s.state}`}>
          <span className={`ic ${s.state === 'running' ? 'spin' : ''}`}>
            {ICON[s.state] || '○'}
          </span>
          <span className="label">{s.label}</span>
          {s.sub && <span className="sub">{s.sub}</span>}
        </div>
      ))}
    </div>
  )
}
