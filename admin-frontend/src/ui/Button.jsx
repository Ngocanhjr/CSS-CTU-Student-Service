export default function Button({ variant = 'primary', size = 'md', className = '', ...rest }) {
  const cls = ['btn', variant === 'ghost' && 'ghost', size === 'small' && 'small', className]
    .filter(Boolean)
    .join(' ')
  return <button className={cls} {...rest} />
}
