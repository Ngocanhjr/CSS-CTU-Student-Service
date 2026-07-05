export default function Field({ label, hint, required, error, children }) {
  return (
    <label className="field">
      <span>
        {label}
        {required && <span className="req-mark"> *</span>}
      </span>
      {children}
      {error ? (
        <p className="field-error">{error}</p>
      ) : hint ? (
        <p className="hint">{hint}</p>
      ) : null}
    </label>
  )
}
