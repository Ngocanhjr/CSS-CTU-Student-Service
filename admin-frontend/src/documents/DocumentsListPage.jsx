import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import StatusBadge from "../components/StatusBadge.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { useReferenceData } from "../hooks/useReferenceData.js";

function EmptyStateIcon() {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path
        d="M11 4h7l5 5v13a2 2 0 01-2 2H11a2 2 0 01-2-2V6a2 2 0 012-2z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M18 4v5h5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle
        cx="14.5"
        cy="16.5"
        r="3.5"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M17.2 19.2L20 22"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function DocumentsListPage({ onEdit, onReview, onReviewChunks, onUploadNew }) {
  const {
    documentTypes,
    departments,
    enumOptions,
    loading: refLoading,
  } = useReferenceData();
  const [query, setQuery] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [documentTypeId, setDocumentTypeId] = useState("");
  const [ragStatus, setRagStatus] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    api
      .listDocuments()
      .then((rows) => {
        if (!cancelled) {
          setResults(rows.items || rows);
          setSearched(true);
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function search() {
    setBusy(true);
    try {
      const rows = await api.listDocuments({
        query,
        department_id: departmentId,
        document_type_id: documentTypeId,
        rag_status: ragStatus,
        review_status: reviewStatus,
      });
      setResults(rows.items || rows);
      setSearched(true);
    } finally {
      setBusy(false);
    }
  }

  function clearFilters() {
    setQuery("");
    setDepartmentId("");
    setDocumentTypeId("");
    setRagStatus("");
    setReviewStatus("");
  }

  async function handleDelete(versionId) {
    if (!confirm("Bạn có chắc muốn xóa tài liệu này?")) return;
    setDeleteError(null);
    try {
      await api.deleteDocument(versionId);
      setResults((prev) => prev.filter((d) => d.id !== versionId));
    } catch (err) {
      setDeleteError(err.message);
    }
  }

  const hasFilters = Boolean(
    query || departmentId || documentTypeId || ragStatus || reviewStatus,
  );
  const deptName = (id) => departments.find((d) => d.id === id)?.name || id;
  const typeName = (id) => documentTypes.find((t) => t.id === id)?.name || id;

  return (
    <>
      <PageHeader
        eyebrow="Documents"
        title="Quản lý tài liệu"
        description="Tìm kiếm tài liệu đã tải lên và sửa metadata/canonical Markdown. Chunk và Qdrant được xử lý ở workflow Index."
      />

      <form
        className="card"
        onSubmit={(event) => {
          event.preventDefault();
          search();
        }}
      >
        <fieldset className="filter-grid">
          <legend>Tìm kiếm tài liệu</legend>
          <label className="field">
            <span>Từ khoá</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tiêu đề, document_key, số hiệu…"
            />
          </label>
          <label className="field">
            <span>Phòng ban</span>
            <select
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
            >
              <option value="">— Tất cả —</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Loại tài liệu</span>
            <select
              value={documentTypeId}
              onChange={(e) => setDocumentTypeId(e.target.value)}
            >
              <option value="">— Tất cả —</option>
              {documentTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Trạng thái duyệt</span>
            <select
              value={reviewStatus}
              onChange={(e) => setReviewStatus(e.target.value)}
            >
              <option value="">— Tất cả —</option>
              {enumOptions.review_statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Trạng thái RAG</span>
            <select
              value={ragStatus}
              onChange={(e) => setRagStatus(e.target.value)}
            >
              <option value="">— Tất cả —</option>
              {enumOptions.rag_statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn filter-submit" disabled={busy}>
            {busy ? "Đang tìm…" : "Tìm kiếm"}
          </button>
        </fieldset>
      </form>

      {deleteError && (
        <div className="card error" role="alert">
          <p>Lỗi khi xóa: {deleteError}</p>
          <button
            type="button"
            className="btn ghost small"
            onClick={() => setDeleteError(null)}
          >
            Đóng
          </button>
        </div>
      )}

      <section className="card" aria-labelledby="document-results-heading">
        <h2 id="document-results-heading">
          Kết quả {results ? `(${results.length})` : ""}
        </h2>
        {results && results.length > 0 ? (
          <div className="table-scroll">
            <table className="documents-table">
              <caption>Danh sách phiên bản tài liệu phù hợp bộ lọc</caption>
              <thead>
                <tr>
                  <th scope="col">Tiêu đề</th>
                  <th scope="col">Loại</th>
                  <th scope="col">Phòng ban</th>
                  <th scope="col">Version / Hiệu lực</th>
                  <th scope="col">OCR</th>
                  <th scope="col">Duyệt</th>
                  <th scope="col">RAG</th>
                  <th scope="col">Cập nhật lúc</th>
                  <th scope="col">
                    <span className="sr-only">Thao tác</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((d) => {
                  const canReview = ['not_reviewed', 'reviewing', 'need_fix'].includes(d.review_status)
                    && d.rag_status === 'not_indexed'
                  const canReviewChunks = d.review_status === 'approved'
                    && d.rag_status === 'not_indexed'

                  return (
                  <tr key={d.id}>
                    <td>
                      <strong>{d.title}</strong>
                      <small className="document-key mono muted">
                        {d.document_key}
                      </small>
                    </td>
                    <td>{typeName(d.document_type_id)}</td>
                    <td>{deptName(d.department_id)}</td>
                    <td>
                      <span className="document-version mono">
                        {d.version_label || "—"}
                      </span>
                      <StatusBadge status={d.validity_status} />
                    </td>
                    <td className="status-cell">
                      <StatusBadge status={d.ocr_status} />
                    </td>
                    <td className="status-cell">
                      <StatusBadge status={d.review_status} />
                    </td>
                    <td className="status-cell">
                      <StatusBadge status={d.rag_status} />
                    </td>
                    <td className="mono">
                      <time dateTime={d.updated_at}>
                        {new Date(d.updated_at).toLocaleString("vi-VN")}
                      </time>
                    </td>
                    <td className="table-action">
                      {canReview ? (
                        <button
                          type="button"
                          className="btn small"
                          onClick={() => onReview(d.id)}
                        >
                          Review
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn ghost small"
                          onClick={() => onEdit(d.id)}
                        >
                          Sửa
                        </button>
                      )}
                      {canReviewChunks && (
                        <button
                          type="button"
                          className="btn ghost small"
                          onClick={() => onReviewChunks(d.id)}
                        >
                          Review chunks
                        </button>
                      )}
                      {(d.rag_status === "not_indexed" ||
                        d.rag_status === "failed") && (
                        <button
                          type="button"
                          className="btn ghost small danger"
                          onClick={() => handleDelete(d.id)}
                        >
                          Xóa
                        </button>
                      )}
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : busy ? (
          <p className="hint">Đang tìm kiếm…</p>
        ) : (
          <div className="empty-state">
            <span className="empty-state-art" aria-hidden="true">
              <EmptyStateIcon />
            </span>
            <h3>
              {hasFilters
                ? "Không có tài liệu nào khớp bộ lọc"
                : "Chưa có tài liệu nào"}
            </h3>
            <p>
              {hasFilters
                ? "Thử bỏ vài điều kiện lọc hoặc dùng từ khoá ngắn hơn. Tài liệu mới cũng có thể chưa được tải lên."
                : "Tải canonical Markdown đầu tiên lên để bắt đầu quy trình duyệt và index."}
            </p>
            <div className="empty-state-actions">
              {hasFilters && (
                <button
                  type="button"
                  className="btn ghost"
                  onClick={clearFilters}
                >
                  Xoá bộ lọc
                </button>
              )}
              {onUploadNew && (
                <button type="button" className="btn" onClick={onUploadNew}>
                  Tải tài liệu mới
                </button>
              )}
            </div>
          </div>
        )}
      </section>
    </>
  );
}
