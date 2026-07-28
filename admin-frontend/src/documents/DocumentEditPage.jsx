import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import StatusBadge from "../components/StatusBadge.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { useReferenceData } from "../hooks/useReferenceData.js";

const VALIDITY_STATUSES = [
  "unchecked",
  "valid",
  "expired",
  "replaced",
  "unknown",
];

function toForm(doc) {
  return {
    title: doc.title,
    document_type_id: doc.document_type_id,
    department_id: doc.department_id,
    domain: doc.domain,
    audience: [...doc.audience],
    code: doc.code,
    version_label: doc.version_label,
    issued_date: doc.issued_date,
    effective_date: doc.effective_date,
    expiry_date: doc.expiry_date,
    validity_status: doc.validity_status,
  };
}

export default function DocumentEditPage({ documentId, onBack, onContinue }) {
  const {
    documentTypes,
    departments,
    enumOptions,
    loading: refLoading,
  } = useReferenceData();

  const [doc, setDoc] = useState(null);
  const [form, setForm] = useState(null);
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getDocument(documentId)
      .then((d) => {
        if (cancelled) return;
        setDoc(d);
        setForm(d ? toForm(d) : null);
        setMarkdown(d ? d.canonical_markdown : "");
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setDoc(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (loading || refLoading) {
    return (
      <>
        <PageHeader eyebrow="Documents / Edit" title="Sửa tài liệu" />
        <p className="hint" role="status">
          Đang tải…
        </p>
      </>
    );
  }

  if (!doc) {
    return (
      <>
        <PageHeader eyebrow="Documents / Edit" title="Sửa tài liệu" />
        <aside className="banner warn">
          Không tìm thấy tài liệu.
          <p>
            <button type="button" className="btn small" onClick={onBack}>
              ← Quay lại danh sách
            </button>
          </p>
        </aside>
      </>
    );
  }

  function set(key, value) {
    setResult(null);
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleAudience(a) {
    setResult(null);
    setForm((f) => ({
      ...f,
      audience: f.audience.includes(a)
        ? f.audience.filter((x) => x !== a)
        : [...f.audience, a],
    }));
  }

  async function onSave() {
    setBusy(true);
    setResult(null);
    setError("");
    try {
      const res = await api.updateDocument(documentId, {
        metadata: form,
        canonical_markdown: markdown,
      });
      setDoc(res.document);
      setForm(toForm(res.document));
      setMarkdown(res.document.canonical_markdown);
      setResult(res);
      return res;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function saveAndContinue() {
    try {
      if (result?.updated) {
        onContinue(result.document);
        return;
      }
      const saved = await onSave();
      if (saved) onContinue(saved.document);
    } catch (err) {
      setError(err.message || "Không thể mở Chunk preview");
    }
  }

  async function handlePublish() {
    setBusy(true);
    setError("");
    try {
      await api.publishDocument(documentId);
      const updated = await api.getDocument(documentId);
      setDoc(updated);
      setForm(toForm(updated));
      setResult({ updated: true, message: "Đã publish thành công" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleUnpublish() {
    if (!confirm("Unpublish sẽ ẩn tài liệu khỏi chatbot. Tiếp tục?")) return;
    setBusy(true);
    setError("");
    try {
      await api.unpublishDocument(documentId);
      const updated = await api.getDocument(documentId);
      setDoc(updated);
      setForm(toForm(updated));
      setResult({ updated: true, message: "Đã unpublish" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDeindex() {
    if (!confirm("Deindex sẽ xóa tất cả chunks và vectors. Tiếp tục?")) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.deindexDocument(documentId);
      const updated = await api.getDocument(documentId);
      setDoc(updated);
      setForm(toForm(updated));
      setMarkdown(updated.canonical_markdown);
      setResult({
        updated: true,
        message: `Đã xóa ${res.chunks_deleted} chunks và ${res.vectors_deleted} vectors`,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const valid = form.title.trim() && form.document_type_id;
  const editable = doc.rag_status === "not_indexed";

  return (
    <>
      <PageHeader
        eyebrow="Documents / Edit"
        title="Sửa tài liệu"
        description={
          <span className="mono muted">
            {doc.document_key} — {doc.version_key}
          </span>
        }
      />

      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave();
        }}
      >
        <section className="card" aria-labelledby="current-status-heading">
          <h2 id="current-status-heading">Trạng thái hiện tại</h2>
          <dl className="kv">
            <dt>OCR</dt>
            <dd>
              <StatusBadge status={doc.ocr_status} />
            </dd>
            <dt>Hiệu lực</dt>
            <dd>
              <select
                aria-label="Tình trạng hiệu lực"
                value={form.validity_status}
                onChange={(e) => set("validity_status", e.target.value)}
              >
                {VALIDITY_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </dd>
            <dt>Duyệt nội dung</dt>
            <dd>
              <StatusBadge status={doc.review_status} />
            </dd>
            <dt>RAG</dt>
            <dd>
              <StatusBadge status={doc.rag_status} />
            </dd>
          </dl>
          <p className="hint">
            OCR và RAG là kết quả của pipeline tự động, không sửa trực tiếp ở
            đây.
          </p>
          {doc.rag_status === "failed" && (
            <aside className="banner warn" role="alert">
              <strong>Index thất bại — không sửa trực tiếp version này.</strong>
              <p>
                Bước lỗi:{" "}
                <span className="mono">{doc.last_job_step || "unknown"}</span>
              </p>
              {doc.last_job_error && (
                <p className="mono error-detail">{doc.last_job_error}</p>
              )}
              <button
                type="button"
                className="btn small"
                onClick={() => onContinue(doc)}
              >
                Thử lại Index →
              </button>
            </aside>
          )}
          {["chunked", "embedded", "indexed", "published"].includes(
            doc.rag_status,
          ) && (
            <aside className="banner warn" role="status">
              <p>
                Version đã có dữ liệu RAG. Muốn sửa phải deindex và dọn
                chunks/vector trước.
              </p>
              <button
                type="button"
                className="btn small ghost warn"
                onClick={handleDeindex}
                disabled={busy}
              >
                {busy ? "Đang xử lý…" : "Deindex"}
              </button>
            </aside>
          )}
        </section>

        <section
          className="card"
          aria-labelledby="document-information-heading"
        >
          <h2 id="document-information-heading">Thông tin tài liệu</h2>
          <fieldset className="form-grid">
            <legend className="sr-only">Thông tin phân loại tài liệu</legend>
            <label className="field">
              <span>Tiêu đề *</span>
              <input
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
              />
            </label>
            <label className="field">
              <span>Loại tài liệu *</span>
              <select
                value={form.document_type_id}
                onChange={(e) =>
                  set("document_type_id", Number(e.target.value))
                }
              >
                {documentTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.code})
                  </option>
                ))}
              </select>
            </label>
          </fieldset>
          <fieldset className="form-grid">
            <legend className="sr-only">Đơn vị và lĩnh vực tài liệu</legend>
            <label className="field">
              <span>Phòng ban</span>
              <select
                value={form.department_id}
                onChange={(e) => set("department_id", Number(e.target.value))}
              >
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.code})
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Domain</span>
              <select
                value={form.domain}
                onChange={(e) => set("domain", e.target.value)}
              >
                <option value="">— chọn —</option>
                {enumOptions.domains.map((domain) => (
                  <option key={domain} value={domain}>
                    {domain}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>
          <fieldset className="audience-fieldset">
            <legend>Audience (JSONB)</legend>
            <menu className="pill-row">
              {enumOptions.audiences.map((a) => (
                <li key={a}>
                  <button
                    type="button"
                    className="tag"
                    aria-pressed={form.audience.includes(a)}
                    onClick={() => toggleAudience(a)}
                  >
                    {form.audience.includes(a) ? "✓ " : ""}
                    {a}
                  </button>
                </li>
              ))}
            </menu>
          </fieldset>
        </section>

        <section className="card" aria-labelledby="version-information-heading">
          <h2 id="version-information-heading">Thông tin version</h2>
          <fieldset className="form-grid">
            <legend className="sr-only">Số hiệu và nhãn phiên bản</legend>
            <label className="field">
              <span>Số hiệu (code)</span>
              <input
                value={form.code || ""}
                onChange={(e) => set("code", e.target.value)}
              />
            </label>
            <label className="field">
              <span>Nhãn version</span>
              <input
                value={form.version_label || ""}
                readOnly
                aria-describedby="version-key-hint"
              />
            </label>
          </fieldset>
          <fieldset className="form-grid three-columns">
            <legend className="sr-only">Mốc thời gian phiên bản</legend>
            <label className="field">
              <span>Ngày ban hành</span>
              <input
                type="date"
                value={form.issued_date || ""}
                onChange={(e) => set("issued_date", e.target.value)}
              />
            </label>
            <label className="field">
              <span>Ngày hiệu lực</span>
              <input
                type="date"
                value={form.effective_date || ""}
                onChange={(e) => set("effective_date", e.target.value)}
              />
            </label>
            <label className="field">
              <span>Ngày hết hiệu lực</span>
              <input
                type="date"
                value={form.expiry_date || ""}
                onChange={(e) => set("expiry_date", e.target.value)}
              />
            </label>
          </fieldset>
          <p id="version-key-hint" className="hint">
            Version key là định danh provenance, không sửa trong workflow này.
          </p>
        </section>

        <section className="card" aria-labelledby="canonical-markdown-heading">
          <h2 id="canonical-markdown-heading">Nội dung canonical Markdown</h2>
          <label className="field" htmlFor="document-markdown">
            Canonical Markdown và YAML frontmatter
          </label>
          <textarea
            id="document-markdown"
            className="markdown-editor"
            value={markdown}
            onChange={(e) => {
              setResult(null);
              setMarkdown(e.target.value);
            }}
          />
          <p className="hint">
            Lưu thay đổi cập nhật canonical Markdown và metadata trong
            PostgreSQL. Sau đó chuyển qua Review → Chunks → Index để tạo chunk,
            embedding và upsert Qdrant.
          </p>
        </section>

        <section
          className="card workflow-card"
          aria-labelledby="index-workflow-heading"
        >
          <h2 id="index-workflow-heading">Tiếp tục indexing</h2>
          <p className="hint">
            Lưu xong sẽ chuyển tài liệu sang Chunk preview. Sau khi duyệt
            preview, bước Index sẽ lưu PostgreSQL chunks, tạo embedding và
            upsert Qdrant.
          </p>
          <button
            type="button"
            className="btn"
            disabled={!valid || busy || !editable}
            onClick={(event) => {
              event.preventDefault();
              void saveAndContinue();
            }}
          >
            {busy
              ? "Đang lưu…"
              : result?.updated
                ? "Mở Chunk preview →"
                : "Lưu và mở Chunk preview →"}
          </button>
        </section>

        {result && !result.updated && (
          <p className="banner" role="status">
            Không có thay đổi nào để lưu.
          </p>
        )}
        {result?.updated && (
          <p className="banner" role="status">
            Đã lưu thay đổi thành công. Cập nhật lúc{" "}
            {new Date(result.document.updated_at).toLocaleString("vi-VN")}.
          </p>
        )}
        {error && (
          <p className="banner warn" role="alert">
            {error}
          </p>
        )}
        <footer className="foot-nav">
          <button type="button" className="btn ghost" onClick={onBack}>
            ← Quay lại danh sách
          </button>
          <button
            type="submit"
            className="btn"
            disabled={!valid || busy || !editable}
          >
            {busy ? "Đang lưu…" : "Lưu thay đổi"}
          </button>
        </footer>
      </form>
    </>
  );
}
