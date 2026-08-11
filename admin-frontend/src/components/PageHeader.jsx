export default function PageHeader({ title, description, eyebrow }) {
  return (
    <header className="page-head">
      {eyebrow && <p className="page-eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </header>
  )
}
