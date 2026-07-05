// Mock API client shaped to the documented /api/v1 endpoints and css schema.
// Everything here is fake but structurally faithful, so swapping in a real
// backend later is a matter of replacing these functions with fetch() calls.
//
// Endpoint mapping (documented, not yet implemented server-side):
//   POST /api/v1/documents/upload            -> uploadDocument
//   POST /api/v1/versions/{id}/ocr           -> runOcr
//   PUT  /api/v1/versions/{id}/metadata      -> saveMetadata
//   POST /api/v1/versions/{id}/ingest        -> runIngest
//   GET  /api/v1/versions/{id}               -> getVersion

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

let seq = 100

function slugify(text) {
  return (text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 60)
}

// Simulated canonical markdown produced by LlamaParse OCR.
function fakeOcrMarkdown(fileName, title) {
  return `<!-- page: 1 -->
# ${title || 'Tài liệu'}

## Điều 1. Phạm vi áp dụng

Văn bản này quy định về quy trình xử lý hồ sơ sinh viên tại Trường.
Nguồn tệp: ${fileName}

## Điều 2. Đối tượng áp dụng

Áp dụng cho toàn thể sinh viên hệ chính quy.

<!-- page: 2 -->
## Điều 3. Trình tự thực hiện

1. Sinh viên nộp đơn tại phòng chức năng.
2. Phòng tiếp nhận kiểm tra tính hợp lệ.
3. Kết quả được trả trong vòng 5 ngày làm việc.

## Điều 4. Điều khoản thi hành

Quy định có hiệu lực kể từ ngày ký.
`
}

export const mockApi = {
  // POST /api/v1/documents/upload
  async uploadDocument({ file, title }) {
    await delay(700)
    const id = ++seq
    const docKey = slugify(title || file?.name || `tai-lieu-${id}`)
    return {
      document_id: id,
      document_key: docKey,
      document_version_id: id,
      version_key: `${docKey}-v1`,
      source_path: `uploads/${file?.name ?? 'unknown'}`,
      file_type: (file?.name?.split('.').pop() || 'pdf').toLowerCase(),
      checksum: 'sha256:' + Math.abs(hashStr(file?.name + String(file?.size))).toString(16).padStart(12, '0'),
      size: file?.size ?? 0,
      ocr_status: 'not_started',
      review_status: 'not_reviewed',
      rag_status: 'not_indexed',
    }
  },

  // POST /api/v1/versions/{id}/ocr  — streamed step callback
  async runOcr({ fileName, title }, onStep) {
    const steps = [
      { key: 'queued', label: 'Đưa vào hàng đợi LlamaParse', ms: 500 },
      { key: 'parsing', label: 'Phân tích tài liệu (OCR)', ms: 1400 },
      { key: 'markdown', label: 'Sinh canonical markdown', ms: 900 },
      { key: 'page_markers', label: 'Chèn page markers <!-- page: N -->', ms: 600 },
    ]
    for (const s of steps) {
      onStep?.({ ...s, state: 'running' })
      await delay(s.ms)
      onStep?.({ ...s, state: 'done' })
    }
    const markdown = fakeOcrMarkdown(fileName, title)
    return {
      ocr_status: 'need_review',
      canonical_markdown_path: `canonical/${slugify(title || fileName)}.md`,
      page_count: 2,
      char_count: markdown.length,
      markdown,
    }
  },

  // PUT /api/v1/versions/{id}/metadata
  async saveMetadata(versionId, metadata) {
    await delay(500)
    return {
      document_version_id: versionId,
      saved: true,
      metadata,
      review_status: 'reviewing',
    }
  },

  // POST /api/v1/versions/{id}/ingest — chunk -> embed -> index
  async runIngest({ markdown, versionKey }, onStep) {
    const parents = countHeadings(markdown)
    const children = Math.max(parents * 3, 6)
    const steps = [
      { key: 'chunking', label: 'Chunking (MarkdownHeaderTextSplitter)', ms: 1100, sub: `${parents} parent chunks` },
      { key: 'child_split', label: 'Cắt child chunks (Recursive splitter)', ms: 900, sub: `${children} child chunks` },
      { key: 'embedding', label: 'Embedding BGE-M3 (1024d)', ms: 1600, sub: `${children} vectors` },
      { key: 'pg_insert', label: 'Insert PostgreSQL (css.document_chunks)', ms: 800, sub: `${parents + children} rows` },
      { key: 'qdrant_upsert', label: 'Upsert Qdrant', ms: 1000, sub: `${children} points` },
    ]
    for (const s of steps) {
      onStep?.({ ...s, state: 'running' })
      await delay(s.ms)
      onStep?.({ ...s, state: 'done' })
    }
    return {
      rag_status: 'published',
      parent_chunks: parents,
      child_chunks: children,
      total_chunks: parents + children,
      qdrant_points: children,
      sample_chunk_keys: [
        `${versionKey}::p::0001`,
        `${versionKey}::c::0001`,
        `${versionKey}::c::0002`,
      ],
    }
  },
}

function countHeadings(md) {
  const m = (md || '').match(/^##?\s/gm)
  return m ? m.length : 4
}

function hashStr(s) {
  let h = 0
  for (let i = 0; i < (s || '').length; i++) {
    h = (h << 5) - h + s.charCodeAt(i)
    h |= 0
  }
  return h
}
