// Mirrors ExpenseBlock in core/models.py, in the order the Gastos sheet has
// always listed them. The hint says what each block is for, so nobody has to
// guess whether the rented pickup is Viaje or Operaciones.
export const BLOCKS = [
  { value: 'viaje', label: 'Viaje', hint: 'Pasajes, alojamiento, viáticos' },
  { value: 'flete', label: 'Flete', hint: 'Traslado de equipos y materiales' },
  { value: 'operaciones', label: 'Operaciones', hint: 'Prevención, EPP, herramientas, arriendos' },
]

export const blockLabel = (value) =>
  BLOCKS.find((b) => b.value === value)?.label ?? value

// unit × cantidad × días. The sheet the team knows also had a "Fases" column;
// it stopped meaning anything years ago and is not carried over.
export const lineSubtotal = (line) =>
  (Number(line.unit_amount) || 0) * (Number(line.quantity) || 0) * (Number(line.days) || 0)

// Mirrors ExpenseRate.Source in core/models.py.
export const SOURCES = { estimado: 'Estimado', cotizado: 'Cotizado', real: 'Gasto real' }

// How old a concept's last known value is, in words. A price is only as useful
// as the reader's sense of how long ago it was true.
export const ageLabel = (days) => {
  if (days == null) return 'sin valor'
  if (days === 0) return 'hoy'
  if (days === 1) return 'ayer'
  if (days < 30) return `hace ${days} días`
  const months = Math.floor(days / 30)
  return months === 1 ? 'hace 1 mes' : `hace ${months} meses`
}

// The cost category an expense falls under, mirroring BLOCK_AS_QUOTE_LINE.
export const blockCategory = (block) => (block === 'flete' ? 'flete' : 'gasto')
