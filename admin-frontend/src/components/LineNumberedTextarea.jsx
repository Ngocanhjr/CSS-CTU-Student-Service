import { useMemo, useRef } from 'react'

export default function LineNumberedTextarea({ value = '', ...props }) {
  const gutterRef = useRef(null)
  const lineNumbers = useMemo(
    () => Array.from({ length: String(value).split('\n').length }, (_, index) => index + 1).join('\n'),
    [value],
  )

  function syncScroll(event) {
    if (gutterRef.current) gutterRef.current.scrollTop = event.currentTarget.scrollTop
  }

  return (
    <div className="line-numbered-editor">
      <pre ref={gutterRef} className="line-number-gutter" aria-hidden="true">{lineNumbers}</pre>
      <textarea {...props} value={value} wrap="off" onScroll={syncScroll} />
    </div>
  )
}
