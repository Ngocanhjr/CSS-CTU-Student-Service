import { Trash2 } from "lucide-react";

export default function ResponsibleDepartmentPicker({
  departments,
  value,
  onChange,
  idPrefix,
  disabled = false,
  className = "",
}) {
  const selectedDepartments = value.length ? value : [""];

  function setDepartment(index, departmentCode) {
    onChange(selectedDepartments.map((item, currentIndex) => (
      currentIndex === index ? departmentCode : item
    )));
  }

  return (
    <fieldset
      className={`responsible-departments ${className}`.trim()}
      disabled={disabled}
    >
      <legend>Phòng ban phụ trách <b aria-hidden="true">*</b></legend>
      {selectedDepartments.map((selectedCode, index) => (
        <div className="responsible-department-row" key={`${index}-${selectedCode}`}>
          <label className="field" htmlFor={`${idPrefix}-${index}`}>
            <span className="sr-only">Phòng ban phụ trách {index + 1}</span>
            <select
              id={`${idPrefix}-${index}`}
              value={selectedCode}
              onChange={(event) => setDepartment(index, event.target.value)}
              required
            >
              <option value="">— Chọn phòng ban —</option>
              {departments
                .filter((department) => (
                  department.is_active
                  && (department.code === selectedCode || !value.includes(department.code))
                ))
                .map((department) => (
                  <option key={department.code} value={department.code}>
                    {department.code} — {department.name}
                  </option>
                ))}
            </select>
          </label>
          {selectedDepartments.length > 1 && (
            <button
              type="button"
              className="btn ghost small danger-icon"
              onClick={() => onChange(selectedDepartments.filter((_, currentIndex) => currentIndex !== index))}
              aria-label={`Bỏ phòng ban phụ trách ${index + 1}`}
              title="Bỏ phòng ban"
            >
              <Trash2 aria-hidden="true" />
            </button>
          )}
        </div>
      ))}
      <button
        type="button"
        className="btn ghost small"
        onClick={() => onChange([...value, ""])}
        disabled={selectedDepartments.some((item) => !item)}
      >
        + Thêm phòng ban
      </button>
    </fieldset>
  );
}
