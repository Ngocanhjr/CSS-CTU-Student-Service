"""Seed document types and departments.

Revision ID: 7b0c2fd5a1e4
Revises: 10aec260382b
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op


revision: str = "7b0c2fd5a1e4"
down_revision: Union[str, Sequence[str], None] = "10aec260382b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO css.document_types (code, name, is_active) VALUES
            ('noi_quy', 'Nội quy', TRUE),
            ('quy_trinh', 'Quy trình', TRUE),
            ('bieu_mau', 'Biểu mẫu', TRUE),
            ('hoi_dap', 'Hỏi đáp', TRUE),
            ('ke_hoach', 'Kế hoạch', TRUE),
            ('thong_bao', 'Thông báo', TRUE),
            ('bao_cao', 'Báo cáo', TRUE),
            ('huong_dan', 'Hướng dẫn', TRUE),
            ('quyet_dinh', 'Quyết định', TRUE),
            ('cong_van', 'Công văn', TRUE),
            ('thong_tu', 'Thông tư', TRUE),
            ('nghi_quyet', 'Nghị quyết', TRUE),
            ('unknown', 'Chưa xác định', TRUE)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            is_active = EXCLUDED.is_active;
        """
    )

    op.execute(
        """
        INSERT INTO css.departments (code, name, is_active) VALUES
            ('PHTQT', 'Phòng Hợp tác Quốc tế', TRUE),
            ('PDT', 'Phòng Đào tạo', TRUE),
            ('PCTSV', 'Phòng Công tác Sinh viên', TRUE),
            ('PKHTH', 'Phòng Kế hoạch Tổng hợp', TRUE),
            ('PKHTC', 'Phòng Kế hoạch Tài chính', TRUE),
            ('PTV', 'Phòng Tài vụ', TRUE),
            ('PTCCB', 'Phòng Tổ chức Cán bộ', TRUE),
            ('PTC', 'Phòng Tài chính', TRUE),
            ('PQTTB', 'Phòng Quản trị Thiết bị', TRUE),
            ('PQLKH', 'Phòng Quản lý Khoa học', TRUE),
            ('PTTPC', 'Phòng Thanh tra Pháp chế', TRUE),
            ('PTCPTNS', 'Phòng Tổ chức Cán bộ và Phát triển Nhân sự', TRUE),
            ('PCTCT', 'Phòng Công tác Chính trị', TRUE),
            ('TTGDQP&AN', 'Trung tâm Giáo dục Quốc phòng và An ninh', TRUE),
            ('TTQLCL', 'Trung tâm Quản lý Chất lượng', TRUE),
            ('TTHL', 'Trung tâm Học liệu', TRUE),
            ('TTTTQTM', 'Trung tâm Thông tin và Quản trị mạng', TRUE),
            ('TTDGNLNN', 'Trung tâm Đánh giá Năng lực Ngoại ngữ', TRUE),
            ('TTLKDT', 'Trung tâm Liên kết Đào tạo', TRUE),
            ('TTPVSV', 'Trung tâm Phục vụ Sinh viên', TRUE),
            ('KNN', 'Khoa Ngoại ngữ', TRUE),
            ('KDBDT', 'Khoa Dự bị Dân tộc', TRUE),
            ('KSDH', 'Khoa Sau đại học', TRUE),
            ('KGDTC', 'Khoa Giáo dục Thể chất', TRUE),
            ('VPTr', 'Văn phòng Trường', TRUE),
            ('DVQLN', 'Đơn vị Quản lý Ngành', TRUE),
            ('HDXMCNDHP', 'Hội đồng Xét miễn và Công nhận Điểm học phần', TRUE),
            ('HDDGNLNN', 'Hội đồng Đánh giá Năng lực Ngoại ngữ', TRUE),
            ('BGDDT', 'Bộ Giáo dục và Đào tạo', TRUE),
            ('BO', 'Các Bộ', TRUE),
            ('CQNB', 'Cơ quan ngang bộ', TRUE),
            ('CQCP', 'Cơ quan thuộc Chính phủ', TRUE),
            ('UBND-TT', 'Ủy ban nhân dân tỉnh, thành phố trực thuộc trung ương', TRUE),
            ('NHCSXH', 'Ngân hàng Chính sách Xã hội', TRUE)
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            is_active = EXCLUDED.is_active;
        """
    )


def downgrade() -> None:
    # Reference rows may already be used by documents; retain them to avoid data loss.
    pass
