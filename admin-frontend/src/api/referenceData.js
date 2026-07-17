// Reference data shaped to the css schema (see chatbot/db_note.md).
// Used by the mock API layer; swap for real /api/v1 responses later.

export const documentTypes = [
  { id: 1, code: 'noi_quy', name: 'Nội quy', is_active: true },
  { id: 2, code: 'quy_trinh', name: 'Quy trình', is_active: true },
  { id: 3, code: 'bieu_mau', name: 'Biểu mẫu', is_active: true },
  { id: 4, code: 'hoi_dap', name: 'Hỏi đáp', is_active: true },
]

export const departments = [
  { id: 1, code: 'PDT', name: 'Phòng Đào tạo', is_active: true },
  { id: 2, code: 'PCTSV', name: 'Phòng Công tác Sinh viên', is_active: true },
  { id: 3, code: 'PKHTC', name: 'Phòng Kế hoạch Tài chính', is_active: true },
  { id: 4, code: 'PTCHC', name: 'Phòng Tổ chức Hành chính', is_active: true },
  { id: 5, code: 'TTQLCL', name: 'Trung tâm Quản lý Chất lượng', is_active: true },
]

export const audienceOptions = ['sinh_vien', 'giang_vien', 'can_bo', 'tan_sinh_vien']

export const domainOptions = [
  'dao_tao',
  'hoc_phi',
  'hoc_bong',
  'ky_luat',
  'tot_nghiep',
  'noi_tru',
]

// Status enums from db_note.md
export const reviewStatuses = ['not_reviewed', 'reviewing', 'need_fix', 'approved', 'rejected']
export const ragStatuses = [
  'not_indexed', 'chunked', 'embedded', 'indexed', 'published', 'deactivated', 'failed',
]
