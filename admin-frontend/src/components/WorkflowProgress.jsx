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

export default function WorkflowProgress({ steps, active, done, onSelect, activeStepProgress = 0.4 }) {
  const activeIndex = steps.findIndex((step) => step.key === active)

  // Connector giữa bước index và index+1: tô 100% khi đã đi qua,
  // tô một phần khi đang ở bước đó và bước chưa hoàn thành.
  function fillPercent(index) {
    const next = steps[index + 1]
    if (!next) return 0
    if (done[next.key]) return 100
    if (activeIndex > index) return 100
    if (activeIndex === index) return done[steps[index].key] ? 100 : Math.round(Math.min(Math.max(activeStepProgress, 0), 1) * 100)
    return done[steps[index].key] ? 100 : 0
  }

  const reachable = (step, index) => done[step.key] || (activeIndex >= 0 && index <= activeIndex) || index === 0

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

          return (
            <li key={step.key} className={isDone ? 'done' : ''}>
              <button
                type="button"
                className={isActive ? 'active' : ''}
                aria-current={isActive ? 'step' : undefined}
                disabled={!reachable(step, index)}
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
