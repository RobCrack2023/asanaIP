import { toMonthInput, fromMonthInput, monthOptions, monthLabel } from '../dates'

// Dropdown for the expected close month. Takes and returns API date strings
// ("2026-07-01" or null), so callers never deal with the month/date conversion.
export default function MonthSelect({ value, onChange, disabled }) {
  return (
    <select
      value={toMonthInput(value)}
      onChange={(e) => onChange(fromMonthInput(e.target.value))}
      disabled={disabled}
    >
      <option value="">Sin definir</option>
      {monthOptions(value).map((m) => (
        <option key={m} value={m}>{monthLabel(m)}</option>
      ))}
    </select>
  )
}
