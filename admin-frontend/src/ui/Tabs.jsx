import { useState } from 'react'

export default function Tabs({ tabs, defaultKey }) {
  const [activeKey, setActiveKey] = useState(defaultKey || tabs[0]?.key)
  const active = tabs.find((t) => t.key === activeKey) || tabs[0]

  return (
    <div>
      <div className="tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`tab ${activeKey === t.key ? 'active' : ''} ${t.disabled ? 'disabled' : ''}`}
            disabled={t.disabled}
            onClick={() => setActiveKey(t.key)}
            title={t.disabled ? t.disabledReason : undefined}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="tab-panel">{active?.content}</div>
    </div>
  )
}
