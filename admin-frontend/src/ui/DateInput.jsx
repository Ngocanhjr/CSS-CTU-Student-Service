import Field from './Field.jsx'

export default function DateInput({ label, hint, required, error, className = '', ...rest }) {
  const input = <input type="date" className={className} {...rest} />
  if (!label) return input
  return (
    <Field label={label} hint={hint} required={required} error={error}>
      {input}
    </Field>
  )
}
