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
