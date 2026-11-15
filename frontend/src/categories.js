// Mirrors CostCategory in core/models.py. Single source for every screen that
// paints a category, so a label or colour is only ever changed in one place.
//
// `short` is what fits in a select or a badge inside the quote table; `label`
// is the full wording used where there is room, and matches what the API
// sends back as category_display.
export const CATEGORIES = [
  { value: 'equipo', label: 'Equipo o material', short: 'Equipo', color: '#4573D2' },
  { value: 'servicio', label: 'Servicio propio', short: 'Servicio', color: '#7C3AED' },
  { value: 'gasto', label: 'Gasto operacional', short: 'Gasto', color: '#FD9A00' },
  { value: 'flete', label: 'Flete y traslado', short: 'Flete', color: '#4ECBC4' },
  { value: 'prevencion', label: 'Prevención y EPP', short: 'Prevención', color: '#E8384F' },
  { value: 'otro', label: 'Otro', short: 'Otro', color: '#9CA0A5' },
]

export const CATEGORY_CONFIG = Object.fromEntries(CATEGORIES.map((c) => [c.value, c]))

export const categoryLabel = (value) => CATEGORY_CONFIG[value]?.label ?? value

export const categoryShort = (value) => CATEGORY_CONFIG[value]?.short ?? value

export const categoryColor = (value) => CATEGORY_CONFIG[value]?.color ?? '#9CA0A5'

/**
 * Cost and sale per category, the way Quote.category_totals does it server-side.
 *
 * The quote form has no saved quote to ask the API about, so it computes the
 * same split from the lines being typed — the two must agree, which is why the
 * shape and the ordering are copied from the model rather than reinvented.
 */
export const categoryTotals = (items, { cost, sale }) => {
  const buckets = {}
  items.forEach((item) => {
    const key = item.category || 'equipo'
    const bucket = buckets[key] ?? (buckets[key] = { cost: 0, sale: 0 })
    bucket.cost += cost(item)
    bucket.sale += sale(item)
  })

  const totalCost = Object.values(buckets).reduce((sum, b) => sum + b.cost, 0)

  return CATEGORIES.filter((c) => buckets[c.value]).map((c) => {
    const { cost: bucketCost, sale: bucketSale } = buckets[c.value]
    return {
      category: c.value,
      label: c.label,
      color: c.color,
      cost: bucketCost,
      sale: bucketSale,
      profit: bucketSale - bucketCost,
      // Markup over cost, null when there is no cost to mark up.
      margin: bucketCost ? bucketSale / bucketCost - 1 : null,
      cost_share: totalCost ? bucketCost / totalCost : null,
    }
  })
}
