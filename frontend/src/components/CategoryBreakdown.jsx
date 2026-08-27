import './CategoryBreakdown.css'

const percent = (value, digits = 0) =>
  value == null ? '—' : `${(Number(value) * 100).toFixed(digits)}%`

/**
 * Where the money of a quote goes, split by kind of cost.
 *
 * This is the reading the evaluación spreadsheet cannot give: a blended 49%
 * margin hides that the equipment carried 38%, the own labour 180% and the
 * operating expenses were quoted almost at cost. The bar makes the weight of
 * each kind readable before the numbers are.
 *
 * `rows` come either from the API (Quote.category_totals) or from
 * categoryTotals() while a quote is being typed — the two share a shape.
 */
export default function CategoryBreakdown({ rows, money, title = 'Composición del costo' }) {
  if (!rows?.length) return null

  return (
    <div className="cat-breakdown">
      <div className="cat-breakdown-title">{title}</div>

      <div className="cat-bar">
        {rows.map((row) => (
          <span
            key={row.category}
            className="cat-bar-slice"
            style={{ width: `${(Number(row.cost_share) || 0) * 100}%`, background: row.color }}
            title={`${row.label} — ${percent(row.cost_share, 1)} del costo`}
          />
        ))}
      </div>

      <div className="cat-rows">
        <div className="cat-row cat-row-head">
          <span className="cat-row-name">Categoría</span>
          <span className="cat-row-share">% costo</span>
          <span className="cat-row-money">Costo</span>
          <span className="cat-row-margin">Margen</span>
          <span className="cat-row-money">Venta</span>
        </div>
        {rows.map((row) => (
          <div key={row.category} className="cat-row">
            <span className="cat-row-name">
              <i className="cat-dot" style={{ background: row.color }} />
              {row.label}
            </span>
            <span className="cat-row-share">{percent(row.cost_share, 0)}</span>
            <span className="cat-row-money">{money(row.cost)}</span>
            <span className="cat-row-margin">{percent(row.margin, 0)}</span>
            <span className="cat-row-money">{money(row.sale)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
