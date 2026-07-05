export default function Banner({ variant, children }) {
  return <div className={`banner ${variant === 'warn' ? 'warn' : ''}`}>{children}</div>
}
