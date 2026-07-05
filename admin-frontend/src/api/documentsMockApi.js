// Mock API layer for document management (search + edit existing documents),
// shaped to the documented /api/v1 endpoints and css schema, mirroring the
// style of mockClient.js. Fake but structurally faithful, so swapping in
// real fetch() calls later is a 1:1 replacement.
//
// Endpoint mapping (documented, not yet implemented server-side):
//   GET  /api/v1/versions?query=&department_id=&document_type_id=&rag_status=&review_status=  -> listDocuments
//   GET  /api/v1/versions/{id}                                                                  -> getDocument
//   PUT  /api/v1/versions/{id}                                                                  -> updateDocument (metadata + content, syncs PostgreSQL + Qdrant)

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

function normalize(text) {
  return (text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}

function fakeContent(title) {
  return `<!-- page: 1 -->
# ${title}

## Điều 1. Phạm vi áp dụng

Văn bản này quy định các nội dung liên quan đến "${title}".

## Điều 2. Điều khoản thi hành

Quy định có hiệu lực kể từ ngày ký.
`
}

const documents = [
  {
    id: 1,
    document_id: 1,
    document_key: 'quy-che-dao-tao-dai-hoc-chinh-quy',
    title: 'Quy chế đào tạo đại học hệ chính quy',
    department_id: 1,
    document_type_id: 1,
    domain: 'dao_tao',
    audience: ['sinh_vien', 'giang_vien'],
    code: '1234/QĐ-ĐHCT',
    version_label: 'Bản 2023',
    version_key: 'quy-che-dao-tao-dai-hoc-chinh-quy-v1',
    issued_date: '2023-08-01',
    effective_date: '2023-09-01',
    expiry_date: '',
    canonical_markdown: fakeContent('Quy chế đào tạo đại học hệ chính quy'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'published',
    updated_at: '2026-06-02T08:12:00Z',
  },
  {
    id: 2,
    document_id: 2,
    document_key: 'quy-trinh-xet-hoc-bong-khuyen-khich-hoc-tap',
    title: 'Quy trình xét học bổng khuyến khích học tập',
    department_id: 2,
    document_type_id: 2,
    domain: 'hoc_bong',
    audience: ['sinh_vien'],
    code: '567/QĐ-ĐHCT',
    version_label: 'Bản 2024',
    version_key: 'quy-trinh-xet-hoc-bong-khuyen-khich-hoc-tap-v1',
    issued_date: '2024-01-15',
    effective_date: '2024-02-01',
    expiry_date: '',
    canonical_markdown: fakeContent('Quy trình xét học bổng khuyến khích học tập'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'published',
    updated_at: '2026-06-10T09:30:00Z',
  },
  {
    id: 3,
    document_id: 3,
    document_key: 'bieu-mau-don-xin-nghi-hoc-tam-thoi',
    title: 'Biểu mẫu đơn xin nghỉ học tạm thời',
    department_id: 1,
    document_type_id: 3,
    domain: 'dao_tao',
    audience: ['sinh_vien'],
    code: '',
    version_label: 'Bản nháp',
    version_key: 'bieu-mau-don-xin-nghi-hoc-tam-thoi-v1',
    issued_date: '',
    effective_date: '',
    expiry_date: '',
    canonical_markdown: fakeContent('Biểu mẫu đơn xin nghỉ học tạm thời'),
    validity_status: 'unchecked',
    ocr_status: 'need_review',
    review_status: 'reviewing',
    rag_status: 'not_indexed',
    updated_at: '2026-06-25T14:05:00Z',
  },
  {
    id: 4,
    document_id: 4,
    document_key: 'hoi-dap-ve-hoc-phi-hoc-ky',
    title: 'Hỏi đáp về học phí học kỳ',
    department_id: 3,
    document_type_id: 4,
    domain: 'hoc_phi',
    audience: ['sinh_vien', 'tan_sinh_vien'],
    code: '',
    version_label: 'Bản 2025',
    version_key: 'hoi-dap-ve-hoc-phi-hoc-ky-v1',
    issued_date: '2025-08-10',
    effective_date: '2025-08-15',
    expiry_date: '',
    canonical_markdown: fakeContent('Hỏi đáp về học phí học kỳ'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'published',
    updated_at: '2026-05-20T11:00:00Z',
  },
  {
    id: 5,
    document_id: 5,
    document_key: 'noi-quy-ky-tuc-xa-nam-2016',
    title: 'Nội quy Ký túc xá năm 2016',
    department_id: 4,
    document_type_id: 1,
    domain: 'noi_tru',
    audience: ['sinh_vien'],
    code: '89/QĐ-ĐHCT',
    version_label: 'Bản 2016',
    version_key: 'noi-quy-ky-tuc-xa-nam-2016-v1',
    issued_date: '2016-03-01',
    effective_date: '2016-03-15',
    expiry_date: '2023-08-31',
    canonical_markdown: fakeContent('Nội quy Ký túc xá năm 2016'),
    validity_status: 'replaced',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'deactivated',
    updated_at: '2026-04-18T10:00:00Z',
  },
  {
    id: 6,
    document_id: 6,
    document_key: 'noi-quy-ky-tuc-xa-nam-2023',
    title: 'Nội quy Ký túc xá năm 2023 (bản thay thế)',
    department_id: 4,
    document_type_id: 1,
    domain: 'noi_tru',
    audience: ['sinh_vien'],
    code: '210/QĐ-ĐHCT',
    version_label: 'Bản 2023',
    version_key: 'noi-quy-ky-tuc-xa-nam-2023-v1',
    issued_date: '2023-09-01',
    effective_date: '2023-09-01',
    expiry_date: '',
    canonical_markdown: fakeContent('Nội quy Ký túc xá năm 2023'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'published',
    updated_at: '2026-06-28T16:45:00Z',
  },
  {
    id: 7,
    document_id: 7,
    document_key: 'quy-trinh-xu-ly-khieu-nai-ky-luat-sinh-vien',
    title: 'Quy trình xử lý khiếu nại kỷ luật sinh viên',
    department_id: 2,
    document_type_id: 2,
    domain: 'ky_luat',
    audience: ['sinh_vien', 'can_bo'],
    code: '',
    version_label: 'Bản dự thảo',
    version_key: 'quy-trinh-xu-ly-khieu-nai-ky-luat-sinh-vien-v1',
    issued_date: '',
    effective_date: '',
    expiry_date: '',
    canonical_markdown: fakeContent('Quy trình xử lý khiếu nại kỷ luật sinh viên'),
    validity_status: 'unchecked',
    ocr_status: 'done',
    review_status: 'need_fix',
    rag_status: 'not_indexed',
    updated_at: '2026-06-30T13:20:00Z',
  },
  {
    id: 8,
    document_id: 8,
    document_key: 'ke-hoach-tot-nghiep-hk1-2025-2026',
    title: 'Kế hoạch tốt nghiệp học kỳ 1 năm học 2025-2026',
    department_id: 1,
    document_type_id: 2,
    domain: 'tot_nghiep',
    audience: ['sinh_vien'],
    code: '812/KH-ĐHCT',
    version_label: 'Bản 2025',
    version_key: 'ke-hoach-tot-nghiep-hk1-2025-2026-v1',
    issued_date: '2025-11-01',
    effective_date: '2025-11-05',
    expiry_date: '2026-06-30',
    canonical_markdown: fakeContent('Kế hoạch tốt nghiệp học kỳ 1 năm học 2025-2026'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'published',
    updated_at: '2026-05-02T08:00:00Z',
  },
  {
    id: 9,
    document_id: 9,
    document_key: 'bieu-mau-dang-ky-hoc-phan-cai-thien-diem',
    title: 'Biểu mẫu đăng ký học phần cải thiện điểm',
    department_id: 1,
    document_type_id: 3,
    domain: 'dao_tao',
    audience: ['sinh_vien'],
    code: '',
    version_label: '',
    version_key: 'bieu-mau-dang-ky-hoc-phan-cai-thien-diem-v1',
    issued_date: '',
    effective_date: '',
    expiry_date: '',
    canonical_markdown: fakeContent('Biểu mẫu đăng ký học phần cải thiện điểm'),
    validity_status: 'unchecked',
    ocr_status: 'not_started',
    review_status: 'not_reviewed',
    rag_status: 'not_indexed',
    updated_at: '2026-07-01T09:15:00Z',
  },
  {
    id: 10,
    document_id: 10,
    document_key: 'thong-bao-hoc-phi-hk2-2025-2026',
    title: 'Thông báo học phí học kỳ 2 năm học 2025-2026',
    department_id: 3,
    document_type_id: 4,
    domain: 'hoc_phi',
    audience: ['sinh_vien', 'tan_sinh_vien', 'can_bo'],
    code: '95/TB-ĐHCT',
    version_label: 'Bản 2026',
    version_key: 'thong-bao-hoc-phi-hk2-2025-2026-v1',
    issued_date: '2026-01-10',
    effective_date: '2026-01-15',
    expiry_date: '',
    canonical_markdown: fakeContent('Thông báo học phí học kỳ 2 năm học 2025-2026'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'indexed',
    updated_at: '2026-06-15T10:40:00Z',
  },
  {
    id: 11,
    document_id: 11,
    document_key: 'quy-trinh-danh-gia-nckh-sinh-vien',
    title: 'Quy trình đánh giá kết quả nghiên cứu khoa học sinh viên',
    department_id: 5,
    document_type_id: 2,
    domain: 'dao_tao',
    audience: ['sinh_vien', 'giang_vien'],
    code: '',
    version_label: 'Bản 2025',
    version_key: 'quy-trinh-danh-gia-nckh-sinh-vien-v1',
    issued_date: '2025-03-01',
    effective_date: '2025-03-10',
    expiry_date: '',
    canonical_markdown: fakeContent('Quy trình đánh giá kết quả nghiên cứu khoa học sinh viên'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'chunked',
    updated_at: '2026-06-22T15:50:00Z',
  },
  {
    id: 12,
    document_id: 12,
    document_key: 'hoi-dap-thu-tuc-bao-luu-ket-qua-hoc-tap',
    title: 'Hỏi đáp thủ tục xin bảo lưu kết quả học tập',
    department_id: 1,
    document_type_id: 4,
    domain: 'dao_tao',
    audience: ['sinh_vien'],
    code: '',
    version_label: 'Bản 2025',
    version_key: 'hoi-dap-thu-tuc-bao-luu-ket-qua-hoc-tap-v1',
    issued_date: '2025-05-01',
    effective_date: '2025-05-05',
    expiry_date: '',
    canonical_markdown: fakeContent('Hỏi đáp thủ tục xin bảo lưu kết quả học tập'),
    validity_status: 'valid',
    ocr_status: 'done',
    review_status: 'approved',
    rag_status: 'failed',
    updated_at: '2026-06-08T12:25:00Z',
  },
]

export const documentsMockApi = {
  // GET /api/v1/versions
  async listDocuments({ query = '', department_id = '', document_type_id = '', rag_status = '', review_status = '' } = {}) {
    await delay(400)
    const q = normalize(query.trim())
    return documents
      .filter((d) => {
        if (q) {
          const haystack = normalize(`${d.title} ${d.document_key} ${d.code}`)
          if (!haystack.includes(q)) return false
        }
        if (department_id && String(d.department_id) !== String(department_id)) return false
        if (document_type_id && String(d.document_type_id) !== String(document_type_id)) return false
        if (rag_status && d.rag_status !== rag_status) return false
        if (review_status && d.review_status !== review_status) return false
        return true
      })
      .map((d) => ({ ...d, audience: [...d.audience] }))
      .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
  },

  // GET /api/v1/versions/{id}
  async getDocument(versionId) {
    await delay(300)
    const doc = documents.find((d) => d.id === Number(versionId))
    return doc ? { ...doc, audience: [...doc.audience] } : null
  },

  // PUT /api/v1/versions/{id} — updates metadata/content, then re-syncs PostgreSQL + Qdrant
  async updateDocument(versionId, { metadata, canonical_markdown }, onStep) {
    const doc = documents.find((d) => d.id === Number(versionId))
    if (!doc) throw new Error('Document not found')

    const contentChanged = canonical_markdown !== undefined && canonical_markdown !== doc.canonical_markdown
    const metadataChanged = Object.keys(metadata || {}).some(
      (k) => JSON.stringify(metadata[k]) !== JSON.stringify(doc[k]),
    )

    if (!contentChanged && !metadataChanged) {
      return { updated: false, document: { ...doc, audience: [...doc.audience] } }
    }

    const steps = [
      { key: 'pg_update', label: 'Cập nhật PostgreSQL (documents / document_versions / document_version_status)', ms: 600 },
    ]

    const wasIndexed = doc.rag_status !== 'not_indexed'

    if (contentChanged) {
      steps.push(
        { key: 'chunking', label: 'Chunk lại nội dung (MarkdownHeaderTextSplitter)', ms: 800 },
        { key: 'embedding', label: 'Embedding lại BGE-M3 (1024d)', ms: 1200 },
        { key: 'qdrant_delete', label: `Xoá vector cũ theo version_key (${doc.version_key})`, ms: 500 },
        { key: 'qdrant_upsert', label: 'Upsert vector mới vào Qdrant', ms: 900 },
      )
    } else if (metadataChanged && wasIndexed) {
      steps.push({ key: 'qdrant_payload', label: 'Cập nhật payload Qdrant (giữ nguyên vector)', ms: 500 })
    }

    for (const s of steps) {
      onStep?.({ key: s.key, label: s.label, state: 'running' })
      await delay(s.ms)
      onStep?.({ key: s.key, label: s.label, state: 'done' })
    }

    Object.assign(doc, metadata)
    if (contentChanged) {
      doc.canonical_markdown = canonical_markdown
      doc.rag_status = wasIndexed ? 'published' : doc.rag_status
    }
    doc.updated_at = new Date().toISOString()

    return { updated: true, document: { ...doc, audience: [...doc.audience] } }
  },
}
