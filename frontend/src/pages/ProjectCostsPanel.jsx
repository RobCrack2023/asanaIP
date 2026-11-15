import { useState, useEffect } from 'react'
import { Plus, Trash2, TrendingDown, TrendingUp, AlertTriangle } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import { formatMoney } from '../stages'
import { CATEGORIES, categoryColor } from '../categories'
import './ProjectCostsPanel.css'

const today = () => new Date().toISOString().slice(0, 10)

const percent = (value) => (value == null ? '—' : `${(Number(value) * 100).toFixed(0)}%`)

const formatDate = (value) =>
  value
    ? new Date(`${value}T00:00:00`).toLocaleDateString('es', {
        day: 'numeric', month: 'short', year: 'numeric',
      })
    : '—'

/**
 * What the project was sold for, against what it is costing.
 *
 * Everything the CRM reports up to the moment a deal is won is the quoted
 * margin. This is the earned one: the sale was fixed by a document the client
 * accepted, so every peso spent here comes straight out of it. Expenses are
 * always the company's — nothing on this screen is re-invoiced.
 */
export default function ProjectCostsPanel({ projectId }) {
  const [summary, setSummary] = useState(null)
  const [expenses, setExpenses] = useState([])
  const [modal, setModal] = useState(false)

  const load = () => {
    api.get(`/projects/${projectId}/costs/`).then((res) => setSummary(res.data))
    api.get(`/project-expenses/?project=${projectId}`).then((res) => setExpenses(res.data))
  }

  useEffect(() => { load() }, [projectId])

  const deleteExpense = async (expense) => {
    if (!confirm(`¿Eliminar "${expense.description}" de ${formatMoney(expense.amount)}?`)) return
    await api.delete(`/project-expenses/${expense.id}/`)
    load()
  }

  if (!summary) return null

  const sold = Number(summary.budget_sale) > 0
  // Expenses are always on top of the budget, so any of them is an overrun.
  const overrun = Number(summary.extra_cost) > 0

  return (
    <div className="costs-panel">
      {!sold && (
        <div className="costs-warning">
          <AlertTriangle size={15} />
          <span>
            Este proyecto no tiene un presupuesto sellado, así que no hay contra qué
            comparar. Se sella al ganar la oportunidad que lo origina.
          </span>
        </div>
      )}

      <div className="costs-cards">
        <div className="costs-card">
          <span className="costs-card-label">Costo presupuestado</span>
          <strong>{formatMoney(summary.budget_cost)}</strong>
        </div>
        <div className={`costs-card ${overrun ? 'bad' : 'good'}`}>
          <span className="costs-card-label">Gastos en ejecución</span>
          <strong>
            {overrun ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
            {formatMoney(summary.extra_cost)}
          </strong>
        </div>
        <div className="costs-card">
          <span className="costs-card-label">Costo real</span>
          <strong>{formatMoney(summary.real_cost)}</strong>
        </div>
      </div>

      {sold && (
        <div className="costs-margins">
          <div className="costs-margin">
            <span className="costs-card-label">Margen cotizado</span>
            <strong>{percent(summary.quoted_margin)}</strong>
            <span className="costs-margin-profit">{formatMoney(summary.quoted_profit)}</span>
          </div>
          <div className="costs-margin-arrow">→</div>
          <div className={`costs-margin ${overrun ? 'bad' : 'good'}`}>
            <span className="costs-card-label">Margen real</span>
            <strong>{percent(summary.real_margin)}</strong>
            <span className="costs-margin-profit">{formatMoney(summary.real_profit)}</span>
          </div>
          <p className="costs-margin-note">
            La venta no se mueve: el cliente ya aceptó el documento. Lo que aparece
            ejecutando se suma al costo y sale de la utilidad.
          </p>
        </div>
      )}

      {summary.by_category.length > 0 && (
        <div className="costs-table">
          <div className="costs-table-head">
            <span>Categoría</span>
            <span>Presupuestado</span>
            <span>Gastos extra</span>
            <span>Costo real</span>
          </div>
          {summary.by_category.map((row) => {
            const extra = Number(row.extra)
            return (
              <div key={row.category} className="costs-table-row">
                <span className="costs-cat">
                  <i className="cat-dot" style={{ background: categoryColor(row.category) }} />
                  {row.label}
                </span>
                <span>{formatMoney(row.budget)}</span>
                <span className={extra > 0 ? 'gap-bad' : ''}>
                  {extra > 0 ? '+' : ''}{formatMoney(extra)}
                </span>
                <span>{formatMoney(row.real)}</span>
              </div>
            )
          })}
        </div>
      )}

      <div className="costs-section-header">
        <h3>Gastos registrados</h3>
        <button className="opp-add-btn" onClick={() => setModal(true)}>
          <Plus size={13} /> Registrar gasto
        </button>
      </div>

      {expenses.length === 0 ? (
        <div className="costs-empty">
          Sin gastos registrados. Aquí va lo que aparece ejecutando: el neumático de
          la camioneta arrendada, una noche extra, un EPP de reemplazo.
        </div>
      ) : (
        <div className="costs-expenses">
          {expenses.map((expense) => (
            <div key={expense.id} className="costs-expense">
              <span className="costs-expense-date">{formatDate(expense.incurred_on)}</span>
              <span className="costs-cat">
                <i className="cat-dot" style={{ background: categoryColor(expense.category) }} />
                {expense.category_display}
              </span>
              <span className="costs-expense-desc">
                {expense.description}
                {expense.supplier && <em>{expense.supplier}</em>}
              </span>
              <span className="costs-expense-doc">{expense.document || '—'}</span>
              <span className="costs-expense-amount">{formatMoney(expense.amount)}</span>
              <button className="costs-expense-remove" title="Eliminar"
                      onClick={() => deleteExpense(expense)}>
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <ExpenseFormModal
          projectId={projectId}
          onClose={() => setModal(false)}
          onSaved={load}
        />
      )}
    </div>
  )
}

function ExpenseFormModal({ projectId, onClose, onSaved }) {
  const [form, setForm] = useState({
    incurred_on: today(), category: 'gasto', description: '',
    amount: '', supplier: '', document: '', notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/project-expenses/', { ...form, project: projectId })
      onSaved()
      onClose()
    } catch (err) {
      const data = err.response?.data
      setError(data?.amount?.[0] || data?.description?.[0] || 'No se pudo registrar el gasto.')
      setSaving(false)
    }
  }

  return (
    <Modal title="Registrar gasto" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <p className="costs-modal-hint">
          Gasto de la empresa. No se le cobra al cliente: descuenta de la utilidad
          que dejó la cotización.
        </p>

        <div className="modal-field">
          <label>Descripción *</label>
          <input value={form.description} onChange={(e) => set('description', e.target.value)}
                 placeholder="Ej: neumático camioneta arrendada" autoFocus required />
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Fecha</label>
            <input type="date" value={form.incurred_on}
                   onChange={(e) => set('incurred_on', e.target.value)} />
          </div>
          <div className="modal-field">
            <label>Categoría</label>
            <select value={form.category} onChange={(e) => set('category', e.target.value)}>
              {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div className="modal-field">
            <label>Monto *</label>
            <input type="number" min="0" step="any" value={form.amount}
                   onChange={(e) => set('amount', e.target.value)} placeholder="0" required />
          </div>
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Proveedor</label>
            <input value={form.supplier} onChange={(e) => set('supplier', e.target.value)} />
          </div>
          <div className="modal-field">
            <label>Documento</label>
            <input value={form.document} onChange={(e) => set('document', e.target.value)}
                   placeholder="N° de boleta o factura" />
          </div>
        </div>

        <div className="modal-field">
          <label>Notas</label>
          <textarea rows={2} value={form.notes} onChange={(e) => set('notes', e.target.value)}
                    placeholder="Qué pasó, por qué se gastó." />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Registrar'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
