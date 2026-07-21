export default function WorkflowProgress({ steps, active, done, onSelect }) {
  return (
    <nav className="workflow-progress" aria-label="Tiến trình xử lý tài liệu">
      <ol>
        {steps.map((step, index) => (
          <li key={step.key} className={done[step.key] ? 'done' : ''}>
            <button
              type="button"
              className={active === step.key ? 'active' : ''}
              aria-current={active === step.key ? 'step' : undefined}
              onClick={() => onSelect(step.key)}
            >
              <span aria-hidden="true">{done[step.key] ? '✓' : index + 1}</span>
              <small>{step.label}</small>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
