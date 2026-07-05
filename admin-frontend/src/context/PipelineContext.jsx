import { createContext, useContext, useState } from 'react'

const PipelineContext = createContext(null)

const emptyPipeline = {
  upload: null, // upload result
  ocr: null, // { markdown, canonical_markdown_path, ... }
  metadata: null, // metadata object
  ingest: null, // ingest result
}

const emptyErrors = {
  upload: null,
  ocr: null,
  metadata: null,
  ingest: null,
}

export function PipelineProvider({ children }) {
  const [pipeline, setPipeline] = useState(emptyPipeline)
  const [errors, setErrors] = useState(emptyErrors)

  function update(key, value) {
    setPipeline((p) => ({ ...p, [key]: value }))
  }

  function setError(key, message) {
    setErrors((e) => ({ ...e, [key]: message }))
  }

  function reset() {
    setPipeline(emptyPipeline)
    setErrors(emptyErrors)
  }

  const done = {
    upload: !!pipeline.upload,
    ocr: !!pipeline.ocr,
    metadata: !!pipeline.metadata,
    ingest: !!pipeline.ingest,
  }

  return (
    <PipelineContext.Provider value={{ pipeline, update, errors, setError, reset, done }}>
      {children}
    </PipelineContext.Provider>
  )
}

export function usePipeline() {
  const ctx = useContext(PipelineContext)
  if (!ctx) throw new Error('usePipeline must be used within PipelineProvider')
  return ctx
}
