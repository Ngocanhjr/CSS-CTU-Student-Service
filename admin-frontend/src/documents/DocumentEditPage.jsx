import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import AssetEditor from "../components/AssetEditor.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import PageHeader from "../components/PageHeader.jsx";
import LineNumberedTextarea from "../components/LineNumberedTextarea.jsx";
import { useReferenceData } from "../hooks/useReferenceData.js";
import { notify } from "../lib/notify.js";
import { Trash2 } from "lucide-react";

const editableAssets = (items = []) => items.map(({ title, url, asset_type }) => ({
  title,
  url,
  asset_type,
}));

function toForm(doc) {
  return {
    title: doc.title,
    document_type_id: doc.document_type_id,
    responsible_department: [...(doc.responsible_department || [])],
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
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [assetBusy, setAssetBusy] = useState(false);
  const [result, setResult] = useState(null);

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
        setAssets(editableAssets(d?.assets));
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

  function setResponsibleDepartment(index, value) {
    setResult(null);
    setForm((current) => ({
      ...current,
      responsible_department: current.responsible_department.map((item, currentIndex) => (
        currentIndex === index ? value : item
      )),
    }));
  }

  function addResponsibleDepartment() {
    setResult(null);
    setForm((current) => ({
      ...current,
      responsible_department: [...current.responsible_department, ""],
    }));
  }

  function removeResponsibleDepartment(index) {
    setResult(null);
    setForm((current) => ({
      ...current,
      responsible_department: current.responsible_department.filter((_, currentIndex) => currentIndex !== index),
    }));
  }

  async function saveAssets() {
    setAssetBusy(true);
    try {
      const updated = await api.updateDocumentAssets(documentId, assets);
      setDoc(updated);
      setAssets(editableAssets(updated.assets));
      notify.success("Đã cập nhật asset.");
    } catch (err) {
      notify.error(err.message);
    } finally {
      setAssetBusy(false);
    }
  }

  async function onSave() {
    setBusy(true);
    setResult(null);
    try {
      const res = await api.updateDocument(documentId, {
        metadata: form,
        canonical_markdown: markdown,
      });
      setDoc(res.document);
      setForm(toForm(res.document));
      setMarkdown(res.document.canonical_markdown);
      setResult(res);
      notify.success("Đã lưu thay đổi.");
      return res;
    } catch (err) {
      notify.error(err.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    setBusy(true);
    try {
      await api.publishDocument(documentId);
      const updated = await api.getDocument(documentId);
      setDoc(updated);
      setForm(toForm(updated));
      setResult({ updated: true, message: "Đã publish thành công" });
      notify.success("Đã publish tài liệu.");
    } catch (err) {
      notify.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleUnpublish() {
    if (!confirm("Unpublish sẽ ẩn tài liệu khỏi chatbot. Tiếp tục?")) return;
    setBusy(true);
    try {
      await api.unpublishDocument(documentId);
      const updated = await api.getDocument(documentId);
      setDoc(updated);
      setForm(toForm(updated));
      setResult({ updated: true, message: "Đã unpublish" });
      notify.info("Đã unpublish tài liệu.");
    } catch (err) {
      notify.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDeindex() {
    if (!confirm("Deindex sẽ xóa tất cả chunks và vectors. Tiếp tục?")) return;
    setBusy(true);
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
      notify.success("Đã deindex tài liệu.");
    } catch (err) {
      notify.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  const valid = form.title.trim()
    && form.document_type_id
    && form.responsible_department.length
    && form.responsible_department.every(Boolean);
  const editable = doc.rag_status === "not_indexed";
  const assetsReady = assets.every((asset) => (
    asset.title.trim() && asset.url.trim() && asset.asset_type
  ));
  const assetsChanged = JSON.stringify(assets) !== JSON.stringify(editableAssets(doc.assets));

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
                {enumOptions.validity_statuses.map((s) => (
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
              <span>Tiêu đề <b aria-hidden="true">*</b></span>
              <input
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
              />
            </label>
            <label className="field">
              <span>Loại tài liệu <b aria-hidden="true">*</b></span>
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
          <fieldset className="responsible-departments review-metadata-section">
            <legend>Phòng ban phụ trách <b aria-hidden="true">*</b></legend>
            {form.responsible_department.map((selectedCode, index) => (
              <div className="responsible-department-row" key={`${index}-${selectedCode}`}>
                <label className="field" htmlFor={`edit-responsible-department-${index}`}>
                  <span className="sr-only">Phòng ban phụ trách {index + 1}</span>
                  <select id={`edit-responsible-department-${index}`} value={selectedCode} onChange={(event) => setResponsibleDepartment(index, event.target.value)} required>
                    <option value="">— Chọn phòng ban —</option>
                    {departments.filter((department) => department.is_active && (department.code === selectedCode || !form.responsible_department.includes(department.code))).map((department) => (
                      <option key={department.code} value={department.code}>{department.code} — {department.name}</option>
                    ))}
                  </select>
                </label>
                {form.responsible_department.length > 1 && <button type="button" className="btn ghost small danger-icon" onClick={() => removeResponsibleDepartment(index)} aria-label={`Bỏ phòng ban phụ trách ${index + 1}`} title="Bỏ phòng ban"><Trash2 aria-hidden="true" /></button>}
              </div>
            ))}
            <button type="button" className="btn ghost small" onClick={addResponsibleDepartment} disabled={form.responsible_department.some((item) => !item)}>+ Thêm phòng ban</button>
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
          <LineNumberedTextarea
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
            PostgreSQL. Review, duyệt và tạo chunks thực hiện trong workflow
            ingestion.
          </p>
        </section>

        <section className="card" aria-labelledby="document-assets-heading">
          <h2 id="document-assets-heading">Asset liên kết</h2>
          <p className="hint">Asset không nằm trong chunk/vector nên có thể cập nhật mà không cần deindex.</p>
          <AssetEditor
            assets={assets}
            assetTypes={enumOptions.asset_types || []}
            disabled={refLoading || assetBusy}
            idPrefix="edit-asset"
            legend="Danh sách asset"
            onChange={setAssets}
          >
            <button type="button" className="btn small" onClick={saveAssets} disabled={assetBusy || !assetsReady || !assetsChanged}>
              {assetBusy ? "Đang lưu…" : "Lưu asset"}
            </button>
          </AssetEditor>
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
          {doc.review_status === "approved" && doc.rag_status === "not_indexed" && (
            <button type="button" className="btn ghost" onClick={() => onContinue(doc)} disabled={busy}>
              Review chunks →
            </button>
          )}
        </footer>
      </form>
    </>
  );
}
