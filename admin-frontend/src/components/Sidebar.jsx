import RagLogo from "./RagLogo.jsx";
import { FolderOpen, Plus, Upload } from "lucide-react";

export default function Sidebar({
  steps,
  active,
  onSelect,
  onReset,
  collapsed,
}) {
  const processingActive = steps.some((step) => step.key === active);

  return (
    <aside
      id="admin-sidebar"
      className={`sidebar ${collapsed ? "collapsed" : ""}`}
      aria-label="Thanh điều hướng quản trị"
    >
      <header className="brand">
        <RagLogo className="brand-mark" />
        <span className="brand-copy">
          <strong>
            CTU Student
            <br />
            Service Center
          </strong>
          <small>Procedure Assistant</small>
        </span>
      </header>

      <nav aria-label="Khu vực quản trị">
        <p className="nav-heading">Quy trình</p>
        <ul className="nav-list section-list">
          <li>
            <button
              type="button"
              className={`nav-item section-item ${processingActive ? "active" : ""}`}
              aria-current={processingActive ? "page" : undefined}
              title={collapsed ? "Xử lý tài liệu" : undefined}
              onClick={() => onSelect(processingActive ? active : "upload")}
            >
              <span className="nav-icon" aria-hidden="true">
                <Upload size={16} />
              </span>
              <span className="nav-copy">
                <b>Xử lý tài liệu</b>
                <small>Tải · review · publish</small>
              </span>
              <span className="idx" aria-hidden="true">
                01
              </span>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`nav-item section-item ${active.startsWith("documents") ? "active" : ""}`}
              aria-current={active.startsWith("documents") ? "page" : undefined}
              title={collapsed ? "Quản lý tài liệu" : undefined}
              onClick={() => onSelect("documents")}
            >
              <span className="nav-icon" aria-hidden="true">
                <FolderOpen size={16} />
              </span>
              <span className="nav-copy">
                <b>Quản lý tài liệu</b>
                <small>Danh sách đã publish</small>
              </span>
              <span className="idx" aria-hidden="true">
                02
              </span>
            </button>
          </li>
        </ul>
      </nav>

      <button
        type="button"
        className="btn ghost small reset-action"
        onClick={onReset}
      >
        <Plus size={16} aria-hidden="true" />
        <span>Tài liệu mới</span>
      </button>
    </aside>
  );
}
