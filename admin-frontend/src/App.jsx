import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import UploadStep from './steps/UploadStep.jsx'
import OcrStep from './steps/OcrStep.jsx'
import MetadataStep from './steps/MetadataStep.jsx'
import IngestStep from './steps/IngestStep.jsx'
import OutputStep from './steps/OutputStep.jsx'
import DocumentsListPage from './documents/DocumentsListPage.jsx'
import DocumentEditPage from './documents/DocumentEditPage.jsx'

const STEPS = [
  { key: 'upload', label: 'Tải tài liệu' },
  { key: 'ocr', label: 'OCR / Parse' },
  { key: 'metadata', label: 'Gắn metadata' },
  { key: 'ingest', label: 'Đưa vào CSDL' },
  { key: 'output', label: 'Kết quả' },
]

const EXTRA_NAV = [
  { key: 'documents', label: 'Quản lý tài liệu', icon: '📋' },
]

const emptyPipeline = {
  upload: null, // upload result
  ocr: null, // { markdown, canonical_markdown_path, ... }
  metadata: null, // metadata object
  ingest: null, // ingest result
}

export default function App() {
  const [active, setActive] = useState('upload')
  const [pipeline, setPipeline] = useState(emptyPipeline)
  const [editingVersionId, setEditingVersionId] = useState(null)

  const done = {
    upload: !!pipeline.upload,
    ocr: !!pipeline.ocr,
    metadata: !!pipeline.metadata,
    ingest: !!pipeline.ingest,
    output: !!pipeline.ingest,
  }

  function update(key, value) {
    setPipeline((p) => ({ ...p, [key]: value }))
  }

  function reset() {
    setPipeline(emptyPipeline)
    setActive('upload')
  }

  const shared = { pipeline, update, goTo: setActive }

  function openEdit(versionId) {
    setEditingVersionId(versionId)
    setActive('documents-edit')
  }

  return (
    <div className="app">
      <Sidebar
        steps={STEPS}
        active={active}
        done={done}
        onSelect={setActive}
        onReset={reset}
        extraNav={EXTRA_NAV}
      />
      <main className="main">
        {active === 'upload' && <UploadStep {...shared} />}
        {active === 'ocr' && <OcrStep {...shared} />}
        {active === 'metadata' && <MetadataStep {...shared} />}
        {active === 'ingest' && <IngestStep {...shared} />}
        {active === 'output' && <OutputStep {...shared} />}
        {active === 'documents' && <DocumentsListPage onEdit={openEdit} />}
        {active === 'documents-edit' && (
          <DocumentEditPage documentId={editingVersionId} onBack={() => setActive('documents')} />
        )}
      </main>
    </div>
  )
}
