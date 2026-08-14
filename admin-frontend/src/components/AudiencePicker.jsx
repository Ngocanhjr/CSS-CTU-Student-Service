export default function AudiencePicker({
  options,
  value,
  onChange,
  disabled = false,
  className = "",
}) {
  function toggle(audience) {
    onChange(
      value.includes(audience)
        ? value.filter((item) => item !== audience)
        : [...value, audience],
    );
  }

  return (
    <fieldset className={`audience-fieldset ${className}`.trim()} disabled={disabled}>
      <legend>Đối tượng sử dụng</legend>
      <menu className="pill-row">
        {options.map((audience) => (
          <li key={audience}>
            <button
              type="button"
              className="tag"
              aria-pressed={value.includes(audience)}
              onClick={() => toggle(audience)}
            >
              {value.includes(audience) ? "✓ " : ""}{audience}
            </button>
          </li>
        ))}
      </menu>
    </fieldset>
  );
}
