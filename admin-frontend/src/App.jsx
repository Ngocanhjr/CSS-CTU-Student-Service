import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import UploadStep from './steps/UploadStep.jsx'
import ReviewStep from './steps/ReviewStep.jsx'
import ChunkReviewStep from './steps/ChunkReviewStep.jsx'
import IngestStep from './steps/IngestStep.jsx'
import DocumentsListPage from './documents/DocumentsListPage.jsx'
import DocumentEditPage from './documents/DocumentEditPage.jsx'
import WorkflowProgress from './components/WorkflowProgress.jsx'
import RagLogo from './components/RagLogo.jsx'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'

const STEPS = [
  { key: 'upload', label: 'Tải Markdown' },
  { key: 'review', label: 'Review & approve' },
  { key: 'chunks', label: 'Review chunks' },
  { key: 'ingest', label: 'Index & publish' },
]

const emptyPipeline = {
  upload: null,
  review: null,
  chunkPreview: null,
  chunkApproved: false,
  ingest: null,
}

export default function App() {
  const [active, setActive] = useState('upload')
  const [pipeline, setPipeline] = useState(emptyPipeline)
  const [editingVersionId, setEditingVersionId] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const done = {
    upload: !!pipeline.upload,
    review: !!pipeline.review,
    chunks: pipeline.chunkApproved,
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

  function continueIndexing(document) {
    const metadata = {
      document_key: document.document_key,
      version_key: document.version_key,
      title: document.title,
      document_type: 'unknown',
      domain: document.domain || '',
      audience: document.audience || [],
      responsible_department: [],
      checksum: document.checksum,
      ocr_status: document.ocr_status,
      review_status: document.review_status,
      rag_status: document.rag_status,
    }
    setPipeline((current) => ({
      ...current,
      upload: {
        document_id: document.document_id,
        document_version_id: document.id,
        ingestion_job_id: null,
        markdown: document.canonical_markdown,
        metadata,
      },
      review: {
        document_version_id: document.id,
        review_status: document.review_status,
        rag_status: document.rag_status,
        markdown: document.canonical_markdown,
        metadata,
      },
      chunkPreview: null,
      chunkApproved: false,
      ingest: null,
    }))
    setActive('chunks')
  }

  return (
    <article className="app-frame">
      <a href="#main-content" className="skip-link">Chuyển đến nội dung chính</a>
      <section className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`} aria-label="Ứng dụng quản trị tài liệu">
        <Sidebar
          steps={STEPS}
          active={active}
          onSelect={setActive}
          onReset={reset}
          collapsed={sidebarCollapsed}
        />
        <main className="workspace">
          <header className="workspace-bar">
            <button
              type="button"
              className="sidebar-toggle"
              aria-controls="admin-sidebar"
              aria-expanded={!sidebarCollapsed}
              aria-label={sidebarCollapsed ? 'Mở thanh bên' : 'Thu gọn thanh bên'}
              title={sidebarCollapsed ? 'Mở thanh bên' : 'Thu gọn thanh bên'}
              onClick={() => setSidebarCollapsed((value) => !value)}
            >
              {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
            <WorkflowProgress steps={STEPS} active={active} done={done} onSelect={setActive} />
          </header>
          <section className="workspace-content" id="main-content" aria-label="Nội dung quản trị">
          {active === 'upload' && <UploadStep {...shared} />}
          {active === 'review' && <ReviewStep {...shared} />}
          {active === 'chunks' && <ChunkReviewStep {...shared} />}
          {active === 'ingest' && <IngestStep {...shared} />}
          {active === 'documents' && <DocumentsListPage onEdit={openEdit} onUploadNew={reset} />}
          {active === 'documents-edit' && (
            <DocumentEditPage
              documentId={editingVersionId}
              onBack={() => setActive('documents')}
              onContinue={continueIndexing}
            />
          )}
          </section>
        </main>
      </section>
      <footer className="site-footer" aria-label="Thông tin hệ thống">
        <p className="site-footer-brand">
          <RagLogo className="site-footer-mark" />
          <span>
            <strong>CTU Student Service Center</strong>
            <small>Procedure Assistant</small>
          </span>
        </p>
        <nav className="site-footer-links" aria-label="Liên kết chân trang">
          <a href="#system-docs">Tài liệu hệ thống</a>
          <a href="#privacy">Chính sách bảo mật</a>
          <a href="#support">Hỗ trợ</a>
        </nav>
        <small className="site-footer-copyright">© 2026 Trường Đại học Cần Thơ</small>
      </footer>
    </article>
  )
}
