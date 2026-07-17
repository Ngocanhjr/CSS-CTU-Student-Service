import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import UploadStep from './steps/UploadStep.jsx'
import ReviewStep from './steps/ReviewStep.jsx'
import IngestStep from './steps/IngestStep.jsx'
import DocumentsListPage from './documents/DocumentsListPage.jsx'
import DocumentEditPage from './documents/DocumentEditPage.jsx'

const STEPS = [
  { key: 'upload', label: 'Tải Markdown' },
  { key: 'review', label: 'Review nội dung' },
  { key: 'ingest', label: 'Đưa vào CSDL' },
]

const EXTRA_NAV = [
  { key: 'documents', label: 'Quản lý tài liệu', icon: '📋' },
]

const emptyPipeline = {
  upload: null,
  review: null,
  ingest: null,
}

export default function App() {
  const [active, setActive] = useState('upload')
  const [pipeline, setPipeline] = useState(emptyPipeline)
  const [editingVersionId, setEditingVersionId] = useState(null)

  const done = {
    upload: !!pipeline.upload,
    review: !!pipeline.review,
    ingest: !!pipeline.ingest,
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
      <main className="main" id="main-content">
        {active === 'upload' && <UploadStep {...shared} />}
        {active === 'review' && <ReviewStep {...shared} />}
        {active === 'ingest' && <IngestStep {...shared} />}
        {active === 'documents' && <DocumentsListPage onEdit={openEdit} />}
        {active === 'documents-edit' && (
          <DocumentEditPage documentId={editingVersionId} onBack={() => setActive('documents')} />
        )}
      </main>
    </div>
  )
}
