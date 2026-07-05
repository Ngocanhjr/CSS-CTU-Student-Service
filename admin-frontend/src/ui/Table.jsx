export default function Table({ columns, rows, rowKey, emptyMessage = 'Không có dữ liệu.' }) {
  if (!rows?.length) return <p className="hint">{emptyMessage}</p>
  return (
    <table>
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key}>{c.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={rowKey ? rowKey(row) : i}>
            {columns.map((c) => (
              <td key={c.key} style={c.align ? { textAlign: c.align } : undefined}>
                {c.render ? c.render(row) : row[c.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
