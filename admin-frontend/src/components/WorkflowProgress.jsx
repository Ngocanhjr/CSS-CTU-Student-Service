function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M4.5 10.5l3.4 3.4 7.6-7.8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function WorkflowProgress({ steps, active, done, locked = false, onSelect }) {
  const activeIndex = steps.findIndex((step) => step.key === active)

  function fillPercent(index) {
    return done[steps[index + 1]?.key] || activeIndex > index || done[steps[index].key] ? 100 : 0
  }

  const reachable = (step, index) => index === 0
    || done[step.key]
    || done[steps[index - 1]?.key]
    || (activeIndex >= 0 && index <= activeIndex)

  return (
    <nav className="workflow-progress" aria-label="Tiến trình xử lý tài liệu">
      {activeIndex >= 0 && (
        <p className="sr-only">Bước {activeIndex + 1} trên {steps.length}: {steps[activeIndex].label}</p>
      )}
      <ol>
        {steps.map((step, index) => {
          const isDone = !!done[step.key]
          const isActive = active === step.key
          const isLast = index === steps.length - 1
          const isLocked = locked && !isActive

          return (
            <li key={step.key} className={isDone ? 'done' : ''}>
              <button
                type="button"
                className={isActive ? 'active' : ''}
                aria-current={isActive ? 'step' : undefined}
                disabled={isLocked || !reachable(step, index)}
                title={isLocked ? 'Đã khóa sau khi index' : undefined}
                onClick={() => onSelect(step.key)}
              >
                <span className="step-indicator" aria-hidden="true">
                  {isDone && !isActive ? <CheckIcon /> : index + 1}
                </span>
                {isDone && <span className="sr-only">Đã hoàn thành:</span>}
                <span className="step-label">{step.label}</span>
              </button>
              {!isLast && (
                <span className="step-connector" aria-hidden="true">
                  <span className="step-connector-fill" style={{ width: `${fillPercent(index)}%` }} />
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
