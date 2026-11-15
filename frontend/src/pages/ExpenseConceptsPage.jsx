import { useState, useEffect, useCallback } from 'react'
import { Receipt, Plus, Edit2, Trash2, History, AlertTriangle } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import { formatMoney } from '../stages'
import { BLOCKS, SOURCES, ageLabel } from '../expenses'
import './ExpenseConceptsPage.css'

const today = () => new Date().toISOString().slice(0, 10)

const formatDate = (value) =>
  value
    ? new Date(`${value}T00:00:00`).toLocaleDateString('es', {
        day: 'numeric', month: 'short', year: 'numeric',
      })
    : '—'

// Three states, not two: a concept with no value yet is not the same as one
// whose value has gone old, and neither is the same as one that is current.
const freshness = (concept) => {
  if (concept.latest_amount == null) return { state: 'none', label: 'Sin valor' }
  const age = ageLabel(concept.age_days)
  return concept.is_stale
    ? { state: 'stale', label: `Desactualizado · ${age}` }
    : { state: 'fresh', label: `Vigente · ${age}` }
}

/**
 * What the company routinely pays for while executing.
 *
 * There are no prices here, on purpose: hotels and rentals move with the season
 * and the supplier. A concept keeps the values it has been seen at, each with
 * its date, so whoever is estimating can see the last known one and how old it
 * is — and decide whether to trust it or ask for a fresh quote.
 */
export default function ExpenseConceptsPage() {
  const [concepts, setConcepts] = useState(null)
  const [modal, setModal] = useState(null)
  const [loadingStarter, setLoadingStarter] = useState(false)

  const load = useCallback(
    () => api.get('/expense-concepts/').then((res) => setConcepts(res.data)),
    [],
  )

  useEffect(() => { load() }, [load])

  const loadStarter = async () => {
    setLoadingStarter(true)
    try {
      await api.post('/expense-concepts/starter/')
      await load()
    } finally {
      setLoadingStarter(false)
    }
  }

  const toggleActive = async (concept) => {
    await api.patch(`/expense-concepts/${concept.id}/`, { is_active: !concept.is_active })
    load()
  }

  const deleteConcept = async (concept) => {
    if (!confirm(
      `¿Eliminar "${concept.name}"? Se pierde su historial de valores. `
      + 'Las hojas y gastos que lo usaron no cambian. Si solo dejó de usarse, mejor desactívalo.'
    )) return
    await api.delete(`/expense-concepts/${concept.id}/`)
    load()
  }

  if (concepts === null) return null

  const staleCount = concepts.filter((c) => c.is_active && c.is_stale).length

  return (
    <div className="ec-page">
      <div className="ec-header">
        <div>
          <h1><Receipt size={20} /> Conceptos de gasto</h1>
          <p>
            Lo que pagan seguido al ejecutar. No guardan un precio: guardan los
            valores con su fecha, porque hoteles y arriendos cambian.
          </p>
        </div>
        {concepts.length > 0 && (
          <button className="btn btn-primary" onClick={() => setModal({ type: 'form' })}>
            <Plus size={14} /> Nuevo concepto
          </button>
        )}
      </div>

      {staleCount > 0 && (
        <div className="ec-banner">
          <AlertTriangle size={15} />
          <span>
            {staleCount} {staleCount === 1 ? 'concepto tiene' : 'conceptos tienen'} un valor
            de más de {concepts[0]?.stale_after_days ?? 90} días. Confírmalos con un precio
            actual antes de estimar con ellos.
          </span>
        </div>
      )}

      {concepts.length === 0 ? (
        <div className="ec-empty">
          <p>
            Aún no hay conceptos. Un concepto es algo que se paga seguido ejecutando:
            una noche de alojamiento, un día de camioneta, un kit de EPP.
          </p>
          <div className="ec-empty-actions">
            <button className="btn btn-primary" onClick={loadStarter} disabled={loadingStarter}>
              {loadingStarter ? 'Cargando...' : 'Cargar conceptos básicos'}
            </button>
            <button className="btn btn-secondary" onClick={() => setModal({ type: 'form' })}>
              Crear uno
            </button>
          </div>
          <span className="ec-empty-note">
            Los básicos son pasajes, alojamiento, viáticos, flete, camioneta, prevencionista,
            EPP y herramientas. Se cargan sin valor: tú pones el actual.
          </span>
        </div>
      ) : (
        BLOCKS.map((block) => {
          const rows = concepts.filter((c) => c.block === block.value)
          if (!rows.length) return null
          return (
            <div key={block.value} className="ec-group">
              <div className="ec-group-head">
                <h2>{block.label}</h2>
                <span>{block.hint}</span>
              </div>
              <div className="ec-table">
                <div className="ec-row ec-row-head">
                  <span>Concepto</span>
                  <span>Último valor</span>
                  <span>Estado</span>
                  <span>Origen</span>
                  <span />
                </div>
                {rows.map((concept) => {
                  const fresh = freshness(concept)
                  return (
                    <div key={concept.id} className={`ec-row ${concept.is_active ? '' : 'inactive'}`}>
                      <span className="ec-name">
                        {concept.name}
                        <em>por {concept.unit}</em>
                      </span>
                      <span className="ec-value">
                        {concept.latest_amount != null ? formatMoney(concept.latest_amount) : '—'}
                      </span>
                      <span><i className={`ec-badge ${fresh.state}`}>{fresh.label}</i></span>
                      <span className="ec-origin">
                        {concept.latest_source_display
                          ? `${concept.latest_source_display}${concept.latest_supplier ? ` · ${concept.latest_supplier}` : ''}`
                          : '—'}
                      </span>
                      <span className="ec-actions">
                        <button title="Valores e historial"
                                onClick={() => setModal({ type: 'values', concept })}>
                          <History size={14} />
                        </button>
                        <button title="Editar" onClick={() => setModal({ type: 'form', concept })}>
                          <Edit2 size={14} />
                        </button>
                        <button className="ec-toggle" onClick={() => toggleActive(concept)}>
                          {concept.is_active ? 'Activo' : 'Inactivo'}
                        </button>
                        <button className="danger" title="Eliminar" onClick={() => deleteConcept(concept)}>
                          <Trash2 size={14} />
                        </button>
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })
      )}

      {modal?.type === 'form' && (
        <ConceptFormModal concept={modal.concept} onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'values' && (
        <ConceptValuesModal concept={modal.concept} onClose={() => setModal(null)} onChanged={load} />
      )}
    </div>
  )
}

function ConceptFormModal({ concept, onClose, onSaved }) {
  const isEdit = !!concept
  const [form, setForm] = useState({
    name: concept?.name || '',
    block: concept?.block || 'viaje',
    unit: concept?.unit || '',
    initial_amount: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        name: form.name,
        block: form.block,
        unit: form.unit.trim() || 'unidad',
      }
      if (isEdit) {
        await api.patch(`/expense-concepts/${concept.id}/`, payload)
      } else {
        await api.post('/expense-concepts/', {
          ...payload,
          initial_amount: form.initial_amount ? Number(form.initial_amount) : null,
        })
      }
      onSaved()
      onClose()
    } catch (err) {
      const data = err.response?.data
      setError(data?.name?.[0] || data?.initial_amount?.[0] || 'No se pudo guardar el concepto.')
      setSaving(false)
    }
  }

  return (
    <Modal title={isEdit ? 'Editar concepto' : 'Nuevo concepto'} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="modal-field">
          <label>Nombre *</label>
          <input value={form.name} onChange={(e) => set('name', e.target.value)}
                 placeholder="Ej: Arriendo de camioneta" autoFocus required />
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Va en</label>
            <select value={form.block} onChange={(e) => set('block', e.target.value)}>
              {BLOCKS.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}
            </select>
          </div>
          <div className="modal-field">
            <label>Se cobra por</label>
            <input value={form.unit} onChange={(e) => set('unit', e.target.value)}
                   placeholder="noche, día, kit, tramo..." />
          </div>
        </div>

        {!isEdit && (
          <div className="modal-field">
            <label>Valor actual (opcional)</label>
            <input type="number" min="0" step="any" value={form.initial_amount}
                   onChange={(e) => set('initial_amount', e.target.value)} placeholder="0" />
            <span className="field-hint">
              Puedes dejarlo vacío y agregar valores después, con su fecha y proveedor.
            </span>
          </div>
        )}

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function ConceptValuesModal({ concept, onClose, onChanged }) {
  const [rates, setRates] = useState([])
  const [form, setForm] = useState({
    unit_amount: '', date: today(), source: 'cotizado', supplier: '', note: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const loadRates = useCallback(
    () => api.get(`/expense-concepts/${concept.id}/rates/`).then((res) => setRates(res.data)),
    [concept.id],
  )

  useEffect(() => { loadRates() }, [loadRates])

  const set = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post(`/expense-concepts/${concept.id}/rates/`, form)
      setForm((prev) => ({ ...prev, unit_amount: '', supplier: '', note: '' }))
      await loadRates()
      onChanged()
    } catch (err) {
      const data = err.response?.data
      setError(data?.unit_amount?.[0] || data?.source?.[0] || data?.date?.[0]
        || 'No se pudo guardar el valor.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={concept.name} onClose={onClose} className="modal-wide">
      <p className="ec-values-intro">
        Valor por {concept.unit}. El más reciente por fecha es el que se ofrece al
        armar una hoja; los demás quedan como historial.
      </p>

      <form onSubmit={handleSubmit} className="ec-values-form">
        {error && <div className="form-error">{error}</div>}
        <div className="form-row">
          <div className="modal-field">
            <label>Valor por {concept.unit} *</label>
            <input type="number" min="0" step="any" value={form.unit_amount}
                   onChange={(e) => set('unit_amount', e.target.value)} placeholder="0"
                   autoFocus required />
          </div>
          <div className="modal-field">
            <label>Fecha</label>
            <input type="date" value={form.date} onChange={(e) => set('date', e.target.value)} />
          </div>
          <div className="modal-field">
            <label>Origen</label>
            <select value={form.source} onChange={(e) => set('source', e.target.value)}>
              <option value="cotizado">Cotizado</option>
              <option value="estimado">Estimado</option>
            </select>
          </div>
        </div>
        <div className="form-row">
          <div className="modal-field">
            <label>Proveedor</label>
            <input value={form.supplier} onChange={(e) => set('supplier', e.target.value)}
                   placeholder="Ej: Hotel Talca" />
          </div>
          <div className="modal-field">
            <label>Nota</label>
            <input value={form.note} onChange={(e) => set('note', e.target.value)}
                   placeholder="Ej: tarifa temporada alta" />
          </div>
          <button type="submit" className="btn btn-primary ec-values-add" disabled={saving}>
            {saving ? 'Guardando...' : 'Agregar valor'}
          </button>
        </div>
      </form>

      <div className="ec-history">
        <div className="ec-history-row ec-history-head">
          <span>Fecha</span>
          <span>Valor</span>
          <span>Origen</span>
          <span>Proveedor / nota</span>
        </div>
        {rates.length === 0 && <div className="ec-history-empty">Todavía sin valores.</div>}
        {rates.map((rate, index) => (
          <div key={rate.id} className={`ec-history-row ${index === 0 ? 'latest' : ''}`}>
            <span>{formatDate(rate.date)}</span>
            <span className="ec-history-amount">{formatMoney(rate.unit_amount)}</span>
            <span><i className={`ec-source ${rate.source}`}>{SOURCES[rate.source] ?? rate.source}</i></span>
            <span className="ec-history-detail">
              {[rate.supplier, rate.note].filter(Boolean).join(' · ') || '—'}
            </span>
          </div>
        ))}
      </div>
    </Modal>
  )
}
