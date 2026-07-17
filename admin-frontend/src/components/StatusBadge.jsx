const COLOR = {
  // ocr_status
  not_started: 'slate',
  processing: 'blue',
  need_review: 'amber',
  failed: 'red',
  done: 'green',
  // review_status
  not_reviewed: 'slate',
  reviewing: 'blue',
  need_fix: 'amber',
  approved: 'green',
  rejected: 'red',
  // rag_status
  not_indexed: 'slate',
  chunked: 'blue',
  embedded: 'blue',
  indexed: 'blue',
  published: 'green',
  deactivated: 'slate',
  // validity_status
  unchecked: 'slate',
  valid: 'green',
  expired: 'red',
  replaced: 'amber',
  unknown: 'slate',
}

const LABEL = {
  not_started: 'Chưa bắt đầu',
  processing: 'Đang xử lý',
  need_review: 'Chờ duyệt',
  failed: 'Thất bại',
  done: 'Hoàn tất',
  not_reviewed: 'Chưa duyệt',
  reviewing: 'Đang duyệt',
  need_fix: 'Cần sửa',
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  not_indexed: 'Chưa index',
  chunked: 'Đã chunk',
  embedded: 'Đã embed',
  indexed: 'Đã index',
  published: 'Đã xuất bản',
  deactivated: 'Ngừng dùng',
  unchecked: 'Chưa kiểm tra',
  valid: 'Còn hiệu lực',
  expired: 'Hết hiệu lực',
  replaced: 'Đã bị thay thế',
  unknown: 'Không rõ',
}

export default function StatusBadge({ status }) {
  if (!status) return null
  const color = COLOR[status] || 'slate'
  return (
    <span className={`badge ${color}`} role="status">{LABEL[status] || status}</span>
  )
}
