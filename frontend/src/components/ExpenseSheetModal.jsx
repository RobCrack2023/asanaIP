import { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import api from '../api'
import Modal from './Modal'
import { formatMoney } from '../stages'
import { BLOCKS, lineSubtotal, ageLabel } from '../expenses'
import './ExpenseSheetModal.css'

const emptyLine = (block) => ({
  block, concept: null, description: '', unit_amount: '', quantity: '1', days: '1',
})

// What to tell the person about the value they are about to trust. The point
// is not the number but how long ago it was true.
const referenceText = (concept, old) => {
  if (!concept.latest_amount) return 'Sin valor de referencia: escribe el actual'
  const base = `Referencia ${formatMoney(concept.latest_amount)} por ${concept.unit} · ${ageLabel(concept.age_days)}`
  return old ? `${base} — confírmalo con un valor actual` : base
}

/**
 * The breakdown behind an operating-expense figure.
 *
 * In the spreadsheet this calculation lives on a sheet nothing references: a
 * person computes the total and retypes it into the quote, and the detail is
 * gone. Here it is saved, and the quote line is generated from it.
 */
export default function ExpenseSheetModal({ opportunityId, sheet, sheets = [], onClose, onSaved }) {
  const isEdit = !!sheet
  const [name, setName] = useState(sheet?.name || 'Hoja de gastos')
  const [notes, setNotes] = useState(sheet?.notes || '')
  const [lines, setLines] = useState(
    sheet?.lines?.length
      ? sheet.lines.map((l) => ({
          block: l.block, concept: l.concept ?? null, description: l.description,
          unit_amount: String(l.unit_amount), quantity: String(Number(l.quantity)),
          days: String(Number(l.days)),
        }))
      : [emptyLine('viaje')]
  )
  const [copyFrom, setCopyFrom] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [concepts, setConcepts] = useState([])

  useEffect(() => {
    api.get('/expense-concepts/?active=1').then((res) => setConcepts(res.data))
  }, [])

  const conceptById = Object.fromEntries(concepts.map((c) => [c.id, c]))

  // A line still holding its concept's stale value is the one to double-check:
  // once the person types a different number it is no longer the old one.
  const isOldValue = (line) => {
    const concept = conceptById[line.concept]
    return !!concept && concept.is_stale
      && Number(line.unit_amount) === Number(concept.latest_amount)
  }

  const addLine = (block) => setLines((prev) => [...prev, emptyLine(block)])

  const updateLine = (index, field, value) =>
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, [field]: value } : l)))

  const removeLine = (index) => setLines((prev) => prev.filter((_, i) => i !== index))

  // Starts the line from what the company last knew; the person then types
  // today's price if it moved.
  const addFromConcept = (block, conceptId) => {
    const concept = conceptById[conceptId]
    if (!concept) return
    setLines((prev) => [...prev, {
      ...emptyLine(block), concept: concept.id, description: concept.name,
      unit_amount: concept.latest_amount ? String(Number(concept.latest_amount)) : '',
    }])
  }

  // Copying an old sheet in replaces what is on screen; the estimate is rarely
  // new, and starting from the last project beats starting from memory.
  const applyCopy = (sheetId) => {
    setCopyFrom(sheetId)
    const source = sheets.find((s) => String(s.id) === String(sheetId))
    if (!source?.lines?.length) return
    setLines(source.lines.map((l) => ({
      block: l.block, concept: l.concept ?? null, description: l.description,
      unit_amount: String(l.unit_amount), quantity: String(Number(l.quantity)),
      days: String(Number(l.days)),
    })))
  }

  const blockTotal = (block) =>
    lines.filter((l) => l.block === block).reduce((sum, l) => sum + lineSubtotal(l), 0)

  const total = lines.reduce((sum, l) => sum + lineSubtotal(l), 0)

  const handleSubmit = async (e) => {
    e.preventDefault()
    const filled = lines.filter((l) => l.description.trim())
    if (!filled.length) {
      setError('Agrega al menos una línea con descripción.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = {
        opportunity: opportunityId,
        name,
        notes,
        lines: filled.map((l, index) => ({
          block: l.block,
          concept: l.concept ?? null,
          description: l.description.trim(),
          unit_amount: Number(l.unit_amount) || 0,
          quantity: Number(l.quantity) || 1,
          days: Number(l.days) || 1,
          order: index,
        })),
      }
      if (isEdit) {
        await api.patch(`/expense-sheets/${sheet.id}/`, payload)
      } else {
        await api.post('/expense-sheets/', payload)
      }
      onSaved()
      onClose()
    } catch (err) {
      const data = err.response?.data
      const lineError = Array.isArray(data?.lines)
        ? Object.values(data.lines.find((l) => l && Object.keys(l).length) || {})[0]?.[0]
        : null
      setError(lineError || data?.name?.[0] || 'No se pudo guardar la hoja de gastos.')
      setSaving(false)
    }
  }

  return (
    <Modal title={isEdit ? 'Hoja de gastos' : 'Nueva hoja de gastos'} onClose={onClose} className="modal-wide">
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="form-row">
          <div className="modal-field">
            <label>Nombre</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
                   placeholder="Ej: Gastos instalación — Fundo Los Nogales" autoFocus />
          </div>
          {!isEdit && sheets.length > 0 && (
            <div className="modal-field">
              <label>Partir desde</label>
              <select value={copyFrom} onChange={(e) => applyCopy(e.target.value)}>
                <option value="">Hoja en blanco</option>
                {sheets.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({formatMoney(s.total)})</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {BLOCKS.map((block) => {
          const blockLines = lines
            .map((line, index) => ({ line, index }))
            .filter(({ line }) => line.block === block.value)
          const blockConcepts = concepts.filter((c) => c.block === block.value)

          return (
            <div key={block.value} className="es-block">
              <div className="es-block-head">
                <span className="es-block-name">
                  {block.label}
                  <em>{block.hint}</em>
                </span>
                <span className="es-block-total">{formatMoney(blockTotal(block.value))}</span>
              </div>

              {blockLines.length > 0 && (
                <div className="es-lines">
                  <div className="es-line es-line-head">
                    <span>Detalle</span>
                    <span>Unitario</span>
                    <span>Cant.</span>
                    <span>Días</span>
                    <span>Subtotal</span>
                    <span />
                  </div>
                  {blockLines.map(({ line, index }) => (
                    <div key={index} className="es-line">
                      <div className="es-desc">
                        <input
                          value={line.description}
                          onChange={(e) => updateLine(index, 'description', e.target.value)}
                          placeholder="Ej: Alojamiento"
                        />
                        {conceptById[line.concept] && (
                          <span className={`es-ref ${isOldValue(line) ? 'stale' : ''}`}>
                            {referenceText(conceptById[line.concept], isOldValue(line))}
                          </span>
                        )}
                      </div>
                      <input type="number" min="0" step="any" value={line.unit_amount}
                             className={isOldValue(line) ? 'stale' : ''}
                             onChange={(e) => updateLine(index, 'unit_amount', e.target.value)}
                             placeholder="0" />
                      <input type="number" min="0" step="any" value={line.quantity}
                             onChange={(e) => updateLine(index, 'quantity', e.target.value)} />
                      <input type="number" min="0" step="any" value={line.days}
                             onChange={(e) => updateLine(index, 'days', e.target.value)} />
                      <span className="es-line-subtotal">{formatMoney(lineSubtotal(line))}</span>
                      <button type="button" className="es-line-remove" title="Quitar"
                              onClick={() => removeLine(index)}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="es-add-row">
                <button type="button" className="field-link" onClick={() => addLine(block.value)}>
                  <Plus size={12} /> Agregar a {block.label.toLowerCase()}
                </button>
                {blockConcepts.length > 0 && (
                  <select
                    className="es-concept-picker"
                    value=""
                    onChange={(e) => { addFromConcept(block.value, e.target.value); e.target.value = '' }}
                  >
                    <option value="">Partir de un concepto...</option>
                    {blockConcepts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                        {c.latest_amount
                          ? ` — ${formatMoney(c.latest_amount)} por ${c.unit} · ${ageLabel(c.age_days)}`
                          : ' — sin valor'}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>
          )
        })}

        <div className="es-total">
          <span>Total de gastos</span>
          <strong>{formatMoney(total)}</strong>
        </div>
        <p className="es-hint">
          Esto es costo. Lo que se cobra por estos gastos se decide con el margen
          de la línea, al llevarlos a la cotización. Los valores que escribas en
          líneas de un concepto quedan como referencia para la próxima hoja.
        </p>

        <div className="modal-field">
          <label>Notas</label>
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
                    placeholder="Ej: dos personas, tres días en terreno." />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Guardar hoja'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
