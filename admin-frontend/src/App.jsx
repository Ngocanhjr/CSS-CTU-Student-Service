import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import UploadStep from './steps/UploadStep.jsx'
import OcrStep from './steps/OcrStep.jsx'
import ReviewStep from './steps/ReviewStep.jsx'
import ChunkReviewStep from './steps/ChunkReviewStep.jsx'
import IngestStep from './steps/IngestStep.jsx'
import DocumentsListPage from './documents/DocumentsListPage.jsx'
import DocumentEditPage from './documents/DocumentEditPage.jsx'
import WorkflowProgress from './components/WorkflowProgress.jsx'
import RagLogo from './components/RagLogo.jsx'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { toast, ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { api } from './api/client.js'

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

function toPipelineMetadata(document) {
  return {
    ...document,
    document_type: document.document_type_code,
    domain: document.domain || 'unknown',
    audience: document.audience || [],
    responsible_department: document.responsible_department || [],
    source_url: document.source_url || '',
    notes: document.notes || '',
  }
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
    ingest: pipeline.ingest?.job_status === 'completed'
      || ['indexed', 'published'].includes(pipeline.ingest?.rag_status),
  }
  const workflowLocked = ['indexed', 'published'].includes(
    pipeline.ingest?.rag_status || pipeline.upload?.metadata?.rag_status,
  )

  function update(key, value) {
    setPipeline((p) => ({ ...p, [key]: value }))
  }

  function reset() {
    setPipeline(emptyPipeline)
    setEditingVersionId(null)
    setActive('upload')
  }

  function selectSection(section) {
    if (section === 'documents') {
      setPipeline(emptyPipeline)
      setEditingVersionId(null)
    }
    setActive(section)
  }

  function goToWorkflow(step) {
    if (workflowLocked && step !== 'ingest') {
      toast.warning('Tài liệu đã index; không thể quay lại các bước trước. Hãy deindex nếu cần sửa.')
      return
    }
    setActive(step)
  }

  const shared = { pipeline, update, goTo: goToWorkflow }

  function openEdit(versionId) {
    setEditingVersionId(versionId)
    setActive('documents-edit')
  }

  function continueIndexing(document) {
    const metadata = toPipelineMetadata(document)
    const assets = document.assets || []
    setPipeline((current) => ({
      ...current,
      upload: {
        document_id: document.document_id,
        document_version_id: document.id,
        ingestion_job_id: document.last_job_id,
        markdown: document.canonical_markdown,
        assets,
        metadata,
      },
      review: {
        document_version_id: document.id,
        review_status: document.review_status,
        rag_status: document.rag_status,
        markdown: document.canonical_markdown,
        assets,
        metadata,
      },
      chunkPreview: null,
      chunkApproved: false,
      ingest: null,
    }))
    setActive('chunks')
  }

  async function resumeReview(versionId) {
    try {
      const document = await api.getDocument(versionId)
      if (document.rag_status !== 'not_indexed') {
        toast.warning('Version đã có dữ liệu RAG; không thể mở lại Review.')
        return
      }

      setPipeline((current) => ({
        ...current,
        upload: {
          document_id: document.document_id,
          document_version_id: document.id,
          ingestion_job_id: document.last_job_id,
          markdown: document.canonical_markdown,
          assets: document.assets || [],
          metadata: toPipelineMetadata(document),
        },
        review: null,
        chunkPreview: null,
        chunkApproved: false,
        ingest: null,
      }))
      setActive('review')
    } catch (error) {
      toast.error(error.message || 'Không thể mở lại Review.')
    }
  }

  async function resumeChunkReview(versionId) {
    try {
      const document = await api.getDocument(versionId)
      if (document.review_status !== 'approved' || document.rag_status !== 'not_indexed') {
        toast.warning('Chỉ có thể review chunks cho version đã duyệt và chưa index.')
        return
      }
      continueIndexing(document)
    } catch (error) {
      toast.error(error.message || 'Không thể mở Review chunks.')
    }
  }

  return (
    <article className="app-frame">
      <a href="#main-content" className="skip-link">Chuyển đến nội dung chính</a>
      <section className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`} aria-label="Ứng dụng quản trị tài liệu">
        <Sidebar
          steps={STEPS}
          active={active}
          onSelect={selectSection}
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
            <WorkflowProgress steps={STEPS} active={active} done={done} locked={workflowLocked} onSelect={goToWorkflow} />
          </header>
          <section className="workspace-content" id="main-content" aria-label="Nội dung quản trị">
          {active === 'upload' && (
            <UploadStep
              {...shared}
              onOpenOcr={() => setActive('ocr')}
            />
          )}
          {active === 'ocr' && <OcrStep {...shared} onBack={() => setActive('upload')} />}
          {active === 'review' && <ReviewStep {...shared} />}
          {active === 'chunks' && <ChunkReviewStep {...shared} />}
          {active === 'ingest' && <IngestStep {...shared} />}
          {active === 'documents' && <DocumentsListPage onEdit={openEdit} onReview={resumeReview} onReviewChunks={resumeChunkReview} onUploadNew={reset} />}
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
      <ToastContainer autoClose={4500} position="top-center" newestOnTop closeOnClick pauseOnFocusLoss draggable pauseOnHover theme="light" />
    </article>
  )
}
