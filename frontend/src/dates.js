// Expected close dates are tracked at month precision — at the prospect stage an
// exact day is guesswork. The API field stays a DateField, so a month round-trips
// as the first day of that month.

export const toMonthInput = (date) => (date ? date.slice(0, 7) : '')

export const fromMonthInput = (month) => (month ? `${month}-01` : null)

// Compact form for tables: "jul 2026"
export const formatMonth = (date) => {
  if (!date) return '—'
  return new Date(date + 'T00:00:00').toLocaleDateString('es', { month: 'short', year: 'numeric' })
}

// Readable form for dropdown options: "Julio 2026"
export const monthLabel = (month) => {
  const name = new Date(`${month}-01T00:00:00`).toLocaleDateString('es', { month: 'long' })
  return `${name.charAt(0).toUpperCase()}${name.slice(1)} ${month.slice(0, 4)}`
}

// Months offered in the picker, starting from the current one. A value already
// stored outside that window (an older opportunity) is kept so editing another
// field never silently drops it.
export const monthOptions = (selectedDate, count = 24) => {
  const today = new Date()
  const months = []
  for (let i = 0; i < count; i++) {
    const d = new Date(today.getFullYear(), today.getMonth() + i, 1)
    months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  const current = toMonthInput(selectedDate)
  if (current && !months.includes(current)) months.unshift(current)
  return months
}
