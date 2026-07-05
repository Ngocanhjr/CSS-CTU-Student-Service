import Field from './Field.jsx'

export default function Select({ label, hint, required, error, className = '', ...rest }) {
  const select = <select className={className} {...rest} />
  if (!label) return select
  return (
    <Field label={label} hint={hint} required={required} error={error}>
      {select}
    </Field>
  )
}
