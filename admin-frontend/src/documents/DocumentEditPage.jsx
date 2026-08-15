import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import AssetEditor from "../components/AssetEditor.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import PageHeader from "../components/PageHeader.jsx";
import LineNumberedTextarea from "../components/LineNumberedTextarea.jsx";
import { useReferenceData } from "../hooks/useReferenceData.js";
import { toast } from "react-toastify";
import AudiencePicker from "../components/AudiencePicker.jsx";
import ResponsibleDepartmentPicker from "../components/ResponsibleDepartmentPicker.jsx";
import {
  replaceMarkdownBody,
  splitCanonicalMarkdown,
} from "../utils/markdown.js";

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
  const [markdownBody, setMarkdownBody] = useState("");
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [assetBusy, setAssetBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getDocument(documentId)
      .then((d) => {
        if (cancelled) return;
        setDoc(d);
        setForm(d ? toForm(d) : null);
        setMarkdownBody(d ? splitCanonicalMarkdown(d.canonical_markdown).body : "");
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
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function saveAssets() {
    setAssetBusy(true);
    try {
      const updated = await api.updateDocumentAssets(documentId, assets);
      setDoc(updated);
      setAssets(editableAssets(updated.assets));
      toast.success("Đã cập nhật asset.");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setAssetBusy(false);
    }
  }

  async function onSave() {
    setBusy(true);
    try {
      const res = await api.updateDocument(documentId, {
        metadata: form,
        canonical_markdown: replaceMarkdownBody(
          doc.canonical_markdown,
          markdownBody,
        ),
      });
      setDoc(res.document);
      setForm(toForm(res.document));
      setMarkdownBody(splitCanonicalMarkdown(res.document.canonical_markdown).body);
      toast.success(res.updated ? "Đã lưu thay đổi." : "Không có thay đổi để lưu.");
      return res;
    } catch (err) {
      toast.error(err.message);
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
      toast.success("Đã publish tài liệu.");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function openCanonicalMarkdown() {
    const previewWindow = window.open("", "_blank");
    if (!previewWindow) {
      toast.error("Trình duyệt đã chặn tab xem canonical Markdown.");
      return;
    }

    previewWindow.opener = null;
    setPreviewBusy(true);
    try {
      const { url } = await api.getDocumentPreviewUrl(
        doc.version_key,
        "canonical_markdown",
      );
      previewWindow.location.replace(url);
    } catch (err) {
      previewWindow.close();
      toast.error(err.message);
    } finally {
      setPreviewBusy(false);
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
      toast.info("Đã unpublish tài liệu.");
    } catch (err) {
      toast.error(err.message);
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
      setMarkdownBody(splitCanonicalMarkdown(updated.canonical_markdown).body);
      toast.success(`Đã deindex: xóa ${res.chunks_deleted} chunks và ${res.vectors_deleted} vectors.`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteRetry() {
    if (!confirm("Thử lại việc xóa tài liệu?")) return;
    setBusy(true);
    try {
      await api.deleteDocument(documentId);
      toast.success("Đã xóa tài liệu.");
      onBack();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  const valid = form.title.trim()
    && form.document_type_id
    && form.responsible_department.length
    && form.responsible_department.every(Boolean);
  const requiresDeindex = doc.rag_status !== "not_indexed";
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
          {doc.rag_status === "published" && (
            <button
              type="button"
              className="btn small ghost warn"
              onClick={handleUnpublish}
              disabled={busy}
            >
              {busy ? "Đang xử lý…" : "Unpublish"}
            </button>
          )}
          {requiresDeindex && (
            <aside className="banner" role="status">
              <strong>Có thể lưu trực tiếp, không tạo embedding mới:</strong>
              <p>
                Số hiệu, ngày ban hành/hiệu lực/hết hiệu lực, tình trạng hiệu
                lực, domain và audience. Domain/audience được đồng bộ vào
                payload Qdrant tự động.
              </p>
            </aside>
          )}
          {doc.rag_status === "failed" && (
            <aside className="banner warn" role="alert">
              <strong>Index thất bại.</strong>
              <p>
                Bước lỗi:{" "}
                <span className="mono">{doc.last_job_step || "unknown"}</span>
              </p>
              <p>
                Vẫn có thể sửa các metadata không ảnh hưởng embedding. Muốn sửa
                nội dung hoặc phân loại, hãy xử lý dữ liệu index lỗi trước.
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
          {["chunked", "embedded", "indexed", "published", "deactivated"].includes(
            doc.rag_status,
          ) && (
            <aside className="banner warn" role="status">
              <p>
                {doc.rag_status === "deactivated"
                  ? doc.last_job_type === "delete"
                    ? "Delete trước đó chưa hoàn tất. Tài liệu đã bị loại khỏi retrieval; chạy lại để dọn nốt Qdrant/R2 rồi xóa PostgreSQL."
                    : "Deindex trước đó chưa hoàn tất. Tài liệu đã bị loại khỏi retrieval; chạy lại để dọn nốt Qdrant và PostgreSQL."
                  : "Tiêu đề, loại tài liệu, phòng ban phụ trách và nội dung canonical Markdown ảnh hưởng embedding nên đang bị khóa. Chỉ Deindex khi cần sửa các mục này."}
              </p>
              {doc.rag_status === "deactivated" && doc.last_job_error && (
                <p className="mono error-detail">{doc.last_job_error}</p>
              )}
              <button
                type="button"
                className="btn small ghost warn"
                onClick={
                  doc.last_job_type === "delete"
                    ? handleDeleteRetry
                    : handleDeindex
                }
                disabled={busy}
              >
                {busy
                  ? "Đang xử lý…"
                  : doc.rag_status === "deactivated"
                    ? doc.last_job_type === "delete"
                      ? "Thử lại Delete"
                      : "Thử lại Deindex"
                    : "Deindex"}
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
                disabled={requiresDeindex}
              />
            </label>
            <label className="field">
              <span>Loại tài liệu <b aria-hidden="true">*</b></span>
              <select
                value={form.document_type_id}
                onChange={(e) =>
                  set("document_type_id", Number(e.target.value))
                }
                disabled={requiresDeindex}
              >
                {documentTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.code})
                  </option>
                ))}
              </select>
            </label>
          </fieldset>
          {requiresDeindex && (
            <p className="hint">
              Tiêu đề và loại tài liệu tham gia tạo embedding; cần Deindex để
              sửa.
            </p>
          )}
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
          <AudiencePicker
            options={enumOptions.audiences}
            value={form.audience}
            onChange={(value) => set("audience", value)}
          />
          <p className="hint">
            Domain và audience có thể sửa trực tiếp; backend cập nhật payload
            Qdrant của mọi version thuộc tài liệu này mà không gọi lại mô hình
            embedding.
          </p>
          <ResponsibleDepartmentPicker
            departments={departments}
            value={form.responsible_department}
            onChange={(value) => set("responsible_department", value)}
            idPrefix="edit-responsible-department"
            disabled={requiresDeindex}
            className="review-metadata-section"
          />
          {requiresDeindex && (
            <p className="hint">
              Phòng ban phụ trách nằm trong text embedding; cần Deindex để sửa.
            </p>
          )}
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
            Số hiệu và các mốc thời gian chỉ cập nhật PostgreSQL/canonical
            Markdown, không cần Deindex.
          </p>
        </section>

        <section className="card" aria-labelledby="canonical-markdown-heading">
          <h2 id="canonical-markdown-heading">Nội dung canonical Markdown</h2>
          <nav className="document-file-actions" aria-label="Xem file canonical Markdown">
            <button
              type="button"
              className="text-link"
              onClick={openCanonicalMarkdown}
              disabled={previewBusy}
            >
              {previewBusy ? "Đang mở file…" : "Mở file đầy đủ từ R2"}
            </button>
          </nav>
          <label className="field" htmlFor="document-markdown">
            Nội dung Markdown
          </label>
          <LineNumberedTextarea
            id="document-markdown"
            className="markdown-editor"
            value={markdownBody}
            disabled={requiresDeindex}
            onChange={(e) => {
              setMarkdownBody(e.target.value);
            }}
          />
          <p className="hint">
            {requiresDeindex
              ? "Nội dung ảnh hưởng trực tiếp chunks và embedding; cần Deindex để sửa."
              : "Chỉ chỉnh phần nội dung; YAML frontmatter được cập nhật từ các trường metadata ở trên."}
          </p>
        </section>

        <section className="card" aria-labelledby="document-assets-heading">
          <h2 id="document-assets-heading">Asset liên kết</h2>
          <p className="hint">Asset không nằm trong chunk/vector nên có thể cập nhật mà không cần deindex.</p>
          <AssetEditor
            assets={assets}
            assetTypes={enumOptions.asset_types || []}
            disabled={refLoading || assetBusy || doc.rag_status === "deactivated"}
            idPrefix="edit-asset"
            legend="Danh sách asset"
            onChange={setAssets}
          >
            <button type="button" className="btn small" onClick={saveAssets} disabled={assetBusy || !assetsReady || !assetsChanged || doc.rag_status === "deactivated"}>
              {assetBusy ? "Đang lưu…" : "Lưu asset"}
            </button>
          </AssetEditor>
        </section>

        <footer className="foot-nav">
          <button type="button" className="btn ghost" onClick={onBack}>
            ← Quay lại danh sách
          </button>
          <button
            type="submit"
            className="btn"
            disabled={!valid || busy || doc.rag_status === "deactivated"}
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
