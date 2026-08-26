// Mirrors Opportunity.Stage in core/models.py. Single source for every screen
// that paints a stage, so a label or colour is only ever changed in one place.

export const STAGES = [
  { value: 'prospecto', label: 'Prospecto', color: '#9ca0a5' },
  { value: 'cotizacion_enviada', label: 'Cotización enviada', color: '#4573d2' },
  { value: 'negociacion', label: 'Negociación', color: '#fd9a00' },
  { value: 'ganada', label: 'Ganada', color: '#5da283' },
  { value: 'perdida', label: 'Perdida', color: '#e8384f' },
]

// Closing an opportunity goes through mark_won / mark_lost, which need a team
// or a reason — those two stages are never a plain edit.
export const OPEN_STAGES = STAGES.filter((s) => !['ganada', 'perdida'].includes(s.value))

export const STAGE_CONFIG = Object.fromEntries(STAGES.map((s) => [s.value, s]))

export const stageLabel = (value) => STAGE_CONFIG[value]?.label ?? value

export const isOpen = (stage) => stage !== 'ganada' && stage !== 'perdida'

export const formatMoney = (amount) => {
  if (amount == null) return '—'
  return new Intl.NumberFormat('es-CL', {
    style: 'currency', currency: 'CLP', maximumFractionDigits: 0,
  }).format(Number(amount) || 0)
}
