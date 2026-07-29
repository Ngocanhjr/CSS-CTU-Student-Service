const STATUS = {
  not_started: ['slate', 'Chưa bắt đầu'], completed: ['green', 'Hoàn tất'],
  processing: ['blue', 'Đang xử lý'], need_review: ['amber', 'Chờ duyệt'],
  failed: ['red', 'Thất bại'], done: ['green', 'Hoàn tất'],
  pending: ['slate', 'Đang chờ'], running: ['blue', 'Đang chạy'],
  not_reviewed: ['slate', 'Chưa duyệt'], reviewing: ['blue', 'Đang duyệt'],
  need_fix: ['amber', 'Cần sửa'], approved: ['green', 'Đã duyệt'],
  rejected: ['red', 'Từ chối'], not_indexed: ['slate', 'Chưa index'],
  chunked: ['blue', 'Đã chunk'], embedded: ['blue', 'Đã embed'],
  indexed: ['blue', 'Đã index'], published: ['green', 'Đã xuất bản'],
  deactivated: ['slate', 'Ngừng dùng'], unchecked: ['slate', 'Chưa kiểm tra'],
  valid: ['green', 'Còn hiệu lực'], expired: ['red', 'Hết hiệu lực'],
  replaced: ['amber', 'Đã bị thay thế'], unknown: ['slate', 'Không rõ'],
}

export default function StatusBadge({ status }) {
  if (!status) return null
  const [color, label] = STATUS[status] || ['slate', status]
  return <span className={`badge ${color}`} role="status">{label}</span>
}
