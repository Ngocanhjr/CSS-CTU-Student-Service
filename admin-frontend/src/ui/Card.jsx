export default function Card({ title, actions, children, className = '', ...rest }) {
  return (
    <div className={`card ${className}`} {...rest}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  )
}
