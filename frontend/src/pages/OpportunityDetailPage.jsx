import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Check, Trash2, Trophy, XCircle, FileText, Plus, ExternalLink, ChevronRight,
  Activity, MessageSquare, Phone, Users, Mail, ArrowRight,
} from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import MonthSelect from '../components/MonthSelect'
import CompleteTaskModal from '../components/CompleteTaskModal'
import { formatDateTime } from '../dates'
import { OPEN_STAGES, formatMoney } from '../stages'
import { MarkWonModal, MarkLostModal } from '../components/OutcomeModals'
import '../pages/ProjectView.css'
import './OpportunityDetailPage.css'

const QUOTE_STATUS_LABELS = {
  draft: 'Borrador',
  sent: 'Enviada',
  approved: 'Aprobada',
  rejected: 'Rechazada',
}

// Kinds the user can log by hand; stage moves are written by the server.
const ACTIVITY_KINDS = [
  { value: 'note', label: 'Nota', icon: MessageSquare, placeholder: 'Anota lo que pasó...' },
  { value: 'call', label: 'Llamada', icon: Phone, placeholder: '¿Con quién hablaste y qué acordaron?' },
  { value: 'meeting', label: 'Reunión', icon: Users, placeholder: '¿Qué se definió en la reunión?' },
  { value: 'email', label: 'Correo', icon: Mail, placeholder: 'Resume el correo enviado o recibido.' },
]

const ACTIVITY_ICONS = {
  note: MessageSquare,
  call: Phone,
  meeting: Users,
  email: Mail,
  stage_change: ArrowRight,
  won: Trophy,
  lost: XCircle,
}

export default function OpportunityDetailPage() {
  const { opportunityId } = useParams()
  const navigate = useNavigate()
  const [opportunity, setOpportunity] = useState(null)
  const [tasks, setTasks] = useState([])
  const [users, setUsers] = useState([])
  const [teams, setTeams] = useState([])
  const [products, setProducts] = useState([])
  const [activities, setActivities] = useState([])
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [modal, setModal] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const newTaskRef = useRef(null)

  const loadActivities = () =>
    api.get(`/opportunity-activities/?opportunity=${opportunityId}`)
      .then((res) => setActivities(res.data))

  const load = () => {
    setLoadError(null)
    api.get(`/opportunities/${opportunityId}/`)
      .then((res) => setOpportunity(res.data))
      .catch(() => setLoadError('No tenés acceso a esta oportunidad o no existe.'))
    api.get(`/tasks/?opportunity=${opportunityId}`).then((res) => setTasks(res.data))
    loadActivities()
  }

  useEffect(() => {
    load()
    api.get('/users/').then((res) => setUsers(res.data))
    api.get('/teams/').then((res) => setTeams(res.data))
    api.get('/products/?active=1').then((res) => setProducts(res.data))
  }, [opportunityId])

  const updateOpportunity = async (data) => {
    setOpportunity((prev) => ({ ...prev, ...data }))
    await api.patch(`/opportunities/${opportunityId}/`, data)
    // A stage move is logged server-side, so pull the entry it just wrote.
    if (data.stage) loadActivities()
  }

  const addActivity = async (kind, body) => {
    const res = await api.post('/opportunity-activities/', {
      opportunity: Number(opportunityId), kind, body,
    })
    setActivities((prev) => [res.data, ...prev])
  }

  const deleteActivity = async (activity) => {
    if (!confirm('¿Eliminar esta actividad de la bitácora?')) return
    await api.delete(`/opportunity-activities/${activity.id}/`)
    setActivities((prev) => prev.filter((a) => a.id !== activity.id))
  }

  const addTask = async () => {
    if (!newTaskTitle.trim()) return
    const title = newTaskTitle
    setNewTaskTitle('')
    const res = await api.post('/tasks/', { title, opportunity: Number(opportunityId) })
    setTasks((prev) => [...prev, res.data])
  }

  const toggleTask = (task) => {
    if (task.status === 'completed') {
      applyTaskStatus(task, 'pending')
    } else {
      setModal({ type: 'complete', task })
    }
  }

  const applyTaskStatus = async (task, newStatus, note = '') => {
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: newStatus } : t)))
    const payload = { status: newStatus }
    if (newStatus === 'completed') payload.completion_note = note
    await api.patch(`/tasks/${task.id}/`, payload)
  }

  const deleteTask = async (taskId) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId))
    await api.delete(`/tasks/${taskId}/`)
  }

  const assignTask = async (taskId, assigneeId) => {
    const res = await api.patch(`/tasks/${taskId}/`, { assignee: assigneeId || null })
    setTasks((prev) => prev.map((t) => (t.id === taskId ? res.data : t)))
  }

  const addQuote = async (data) => {
    const res = await api.post('/quotes/', { ...data, opportunity: Number(opportunityId) })
    setOpportunity((prev) => ({ ...prev, quotes: [res.data, ...prev.quotes] }))
  }

  const deleteQuote = async (quote) => {
    if (!confirm(`¿Eliminar esta cotización de ${formatMoney(quote.total_amount)}?`)) return
    await api.delete(`/quotes/${quote.id}/`)
    setOpportunity((prev) => ({ ...prev, quotes: prev.quotes.filter((q) => q.id !== quote.id) }))
  }

  const markWon = async (teamId) => {
    const res = await api.post(`/opportunities/${opportunityId}/mark_won/`, { team_id: teamId })
    navigate(`/project/${res.data.project}`)
  }

  const markLost = async (reason) => {
    const res = await api.post(`/opportunities/${opportunityId}/mark_lost/`, { reason })
    setOpportunity(res.data)
    loadActivities()
  }

  if (loadError) return <div className="loading">{loadError}</div>
  if (!opportunity) return <div className="loading">Cargando oportunidad...</div>

  const isOpen = opportunity.stage !== 'ganada' && opportunity.stage !== 'perdida'

  return (
    <div className="opp-detail-page">
      <button className="opp-back-btn" onClick={() => navigate('/opportunities')}>
        <ArrowLeft size={15} /> Oportunidades
      </button>

      <div className="opp-detail-header">
        <div className="opp-detail-title-row">
          <input
            className="opp-detail-title"
            value={opportunity.name}
            onChange={(e) => setOpportunity((prev) => ({ ...prev, name: e.target.value }))}
            onBlur={(e) => updateOpportunity({ name: e.target.value })}
          />
          {opportunity.stage === 'ganada' && (
            <span className="opp-result-badge won"><Trophy size={13} /> Ganada</span>
          )}
          {opportunity.stage === 'perdida' && (
            <span className="opp-result-badge lost"><XCircle size={13} /> Perdida</span>
          )}
        </div>
        <span className="opp-detail-client">{opportunity.client_name}</span>
      </div>

      {opportunity.stage === 'ganada' && opportunity.project && (
        <button className="opp-project-link" onClick={() => navigate(`/project/${opportunity.project}`)}>
          <ExternalLink size={13} /> Ver proyecto creado
        </button>
      )}
      {opportunity.stage === 'perdida' && opportunity.lost_reason && (
        <div className="opp-lost-reason">Motivo: {opportunity.lost_reason}</div>
      )}

      <div className="opp-detail-fields">
        <div className="opp-field">
          <label>Etapa</label>
          {isOpen ? (
            <select value={opportunity.stage} onChange={(e) => updateOpportunity({ stage: e.target.value })}>
              {OPEN_STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          ) : (
            <span>{opportunity.stage_display}</span>
          )}
        </div>
        <div className="opp-field">
          <label>Monto estimado</label>
          <input
            type="number"
            disabled={!isOpen}
            defaultValue={opportunity.estimated_amount ?? ''}
            onBlur={(e) => updateOpportunity({ estimated_amount: e.target.value || null })}
          />
        </div>
        <div className="opp-field">
          <label>Mes de cierre esperado</label>
          <MonthSelect
            disabled={!isOpen}
            value={opportunity.expected_close_date}
            onChange={(date) => updateOpportunity({ expected_close_date: date })}
          />
        </div>
        <div className="opp-field">
          <label>Dueño</label>
          <select
            disabled={!isOpen}
            value={opportunity.owner ?? ''}
            onChange={(e) => updateOpportunity({ owner: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Sin asignar</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
        </div>
      </div>

      <div className="opp-field opp-description">
        <label>Descripción</label>
        <textarea
          rows={2}
          disabled={!isOpen}
          defaultValue={opportunity.description}
          onBlur={(e) => updateOpportunity({ description: e.target.value })}
          placeholder="Detalles del negocio..."
        />
      </div>

      {isOpen && (
        <div className="opp-actions">
          <button className="btn btn-primary" onClick={() => setModal({ type: 'won' })}>
            <Trophy size={14} /> Marcar como Ganada
          </button>
          <button className="btn btn-secondary" onClick={() => setModal({ type: 'lost' })}>
            <XCircle size={14} /> Marcar como Perdida
          </button>
        </div>
      )}

      <div className="opp-section">
        <div className="opp-section-header">
          <h2><FileText size={15} /> Cotizaciones</h2>
          <button className="opp-add-btn" onClick={() => setModal({ type: 'quote' })}>
            <Plus size={13} /> Nueva cotización
          </button>
        </div>
        {opportunity.quotes.length === 0 ? (
          <div className="opp-empty-block">Sin cotizaciones todavía</div>
        ) : (
          <div className="opp-quotes-list">
            {opportunity.quotes.map((q) => (
              <QuoteCard key={q.id} quote={q} onDelete={() => deleteQuote(q)} />
            ))}
          </div>
        )}
      </div>

      <div className="opp-section">
        <h2>Tareas</h2>
        <div className="opp-tasks-list">
          {tasks.map((task) => (
            <div key={task.id} className={`task-row ${task.status === 'completed' ? 'completed' : ''}`}>
              <button
                className={`task-checkbox ${task.status === 'completed' ? 'checked' : ''}`}
                onClick={() => toggleTask(task)}
              >
                {task.status === 'completed' && <Check size={12} />}
              </button>
              <span className="task-title" style={{ flex: 1 }}>{task.title}</span>
              <select
                className="opp-task-assignee"
                value={task.assignee ?? ''}
                onChange={(e) => assignTask(task.id, e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Sin asignar</option>
                {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
              </select>
              <button className="task-delete" onClick={() => deleteTask(task.id)}>
                <Trash2 size={13} />
              </button>
            </div>
          ))}

          <div className="task-row new-task-row">
            <div className="task-checkbox" />
            <input
              ref={newTaskRef}
              className="new-task-input"
              placeholder="Escribe el nombre de la tarea..."
              value={newTaskTitle}
              onChange={(e) => setNewTaskTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') addTask() }}
              onBlur={() => { if (newTaskTitle.trim()) addTask() }}
            />
          </div>

          {tasks.length === 0 && (
            <div className="opp-empty-block">Todavía no hay tareas en esta oportunidad</div>
          )}
        </div>
      </div>

      <div className="opp-section">
        <div className="opp-section-header">
          <h2><Activity size={15} /> Bitácora</h2>
        </div>
        <ActivityComposer onSubmit={addActivity} />
        <ActivityTimeline activities={activities} onDelete={deleteActivity} />
      </div>

      {modal?.type === 'complete' && (
        <CompleteTaskModal
          taskTitle={modal.task.title}
          onClose={() => setModal(null)}
          onConfirm={async (note) => {
            await applyTaskStatus(modal.task, 'completed', note)
            setModal(null)
          }}
        />
      )}
      {modal?.type === 'won' && (
        <MarkWonModal teams={teams} onClose={() => setModal(null)} onConfirm={markWon} />
      )}
      {modal?.type === 'lost' && (
        <MarkLostModal onClose={() => setModal(null)} onConfirm={markLost} />
      )}
      {modal?.type === 'quote' && (
        <QuoteFormModal products={products} onClose={() => setModal(null)} onSaved={addQuote} />
      )}
    </div>
  )
}

function ActivityComposer({ onSubmit }) {
  const [kind, setKind] = useState('note')
  const [body, setBody] = useState('')
  const [saving, setSaving] = useState(false)

  const active = ACTIVITY_KINDS.find((k) => k.value === kind)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!body.trim() || saving) return
    setSaving(true)
    try {
      await onSubmit(kind, body.trim())
      setBody('')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="activity-composer" onSubmit={handleSubmit}>
      <div className="activity-kind-tabs">
        {ACTIVITY_KINDS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            className={`activity-kind-tab ${kind === value ? 'active' : ''}`}
            onClick={() => setKind(value)}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>
      <textarea
        rows={2}
        value={body}
        placeholder={active.placeholder}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          // Enter sends; Shift+Enter keeps writing.
          if (e.key === 'Enter' && !e.shiftKey) handleSubmit(e)
        }}
      />
      <div className="activity-composer-actions">
        <button type="submit" className="btn btn-primary" disabled={!body.trim() || saving}>
          {saving ? 'Guardando...' : `Registrar ${active.label.toLowerCase()}`}
        </button>
      </div>
    </form>
  )
}

function ActivityTimeline({ activities, onDelete }) {
  if (activities.length === 0) {
    return <div className="opp-empty-block">Sin actividad registrada todavía</div>
  }

  return (
    <div className="activity-timeline">
      {activities.map((activity) => {
        const Icon = ACTIVITY_ICONS[activity.kind] ?? MessageSquare
        return (
          <div key={activity.id} className={`activity-item ${activity.is_system ? 'system' : ''}`}>
            <div className={`activity-icon ${activity.kind}`}><Icon size={13} /></div>
            <div className="activity-body">
              <div className="activity-meta">
                <strong>{activity.kind_display}</strong>
                {activity.author_name && <span>· {activity.author_name}</span>}
                <span className="activity-time">{formatDateTime(activity.occurred_at)}</span>
                {!activity.is_system && (
                  <button className="activity-delete" onClick={() => onDelete(activity)}>
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
              {activity.is_system && activity.to_stage && (
                <div className="activity-stage-move">
                  {activity.from_stage_display ?? '—'} <ArrowRight size={12} /> {activity.to_stage_display}
                </div>
              )}
              {activity.body && <p className="activity-text">{activity.body}</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function QuoteCard({ quote, onDelete }) {
  const items = quote.items || []
  const [expanded, setExpanded] = useState(false)

  const formatDate = (value) =>
    value ? new Date(`${value}T00:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

  return (
    <div className="opp-quote-card">
      <div
        className={`opp-quote-row ${items.length ? 'expandable' : ''}`}
        onClick={() => items.length && setExpanded((v) => !v)}
      >
        {items.length > 0 && (
          <ChevronRight size={14} className={`opp-quote-chevron ${expanded ? 'open' : ''}`} />
        )}
        <span className="opp-quote-number">N° {quote.number}</span>
        <span className={`quote-status-badge ${quote.status}`}>{QUOTE_STATUS_LABELS[quote.status]}</span>
        <span className="opp-quote-amount">{formatMoney(quote.total_amount)}</span>
        {items.length > 0 && (
          <span className="opp-quote-count">{items.length} {items.length === 1 ? 'ítem' : 'ítems'}</span>
        )}
        {quote.is_expired && <span className="opp-quote-expired">Vencida</span>}
        <span className="opp-quote-date">{formatDate(quote.issue_date)}</span>
        {quote.notes && <span className="opp-quote-notes">{quote.notes}</span>}
        <button
          className="opp-quote-delete"
          title="Eliminar cotización"
          onClick={(e) => { e.stopPropagation(); onDelete() }}
        >
          <Trash2 size={13} />
        </button>
      </div>

      {expanded && (
        <div className="opp-quote-detail">
          <div className="quote-items-head">
            <span>Descripción</span>
            <span>Cant.</span>
            <span>Precio unitario</span>
            <span>Desc. %</span>
            <span>Subtotal</span>
          </div>
          {items.map((item) => (
            <div key={item.id} className="quote-detail-row">
              <span>{item.description}</span>
              <span>{Number(item.quantity)}</span>
              <span>{formatMoney(item.unit_price)}</span>
              <span>{Number(item.discount_percent) ? `${Number(item.discount_percent)}%` : '—'}</span>
              <span>{formatMoney(item.subtotal)}</span>
            </div>
          ))}
          <div className="quote-detail-totals">
            <div className="quote-total-line">
              <span>Neto</span><span>{formatMoney(quote.subtotal)}</span>
            </div>
            <div className="quote-total-line">
              <span>IVA {Number(quote.tax_rate)}%</span><span>{formatMoney(quote.tax_amount)}</span>
            </div>
            <div className="quote-total-line grand">
              <span>Total</span><strong>{formatMoney(quote.total_amount)}</strong>
            </div>
          </div>
          <div className="quote-detail-validity">
            Válida hasta: {formatDate(quote.valid_until)}
          </div>
        </div>
      )}
    </div>
  )
}

const emptyItem = () => ({ product: null, description: '', quantity: '1', unit_price: '', discount_percent: '' })

const itemSubtotal = (item) => {
  const gross = (Number(item.quantity) || 0) * (Number(item.unit_price) || 0)
  return gross - gross * (Number(item.discount_percent) || 0) / 100
}

const today = () => new Date().toISOString().slice(0, 10)

function QuoteFormModal({ products = [], onClose, onSaved }) {
  const [status, setStatus] = useState('draft')
  const [items, setItems] = useState([emptyItem()])
  const [notes, setNotes] = useState('')
  const [taxRate, setTaxRate] = useState('19')
  const [issueDate, setIssueDate] = useState(today())
  const [validUntil, setValidUntil] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Mirrors what the server will compute, so the figures never disagree.
  const subtotal = items.reduce((sum, item) => sum + itemSubtotal(item), 0)
  const taxAmount = subtotal * (Number(taxRate) || 0) / 100
  const total = subtotal + taxAmount

  const updateItem = (index, field, value) =>
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, [field]: value } : item)))

  const addItem = () => setItems((prev) => [...prev, emptyItem()])

  // Picking from the catalog copies the price in — the quote keeps its own
  // snapshot, so later catalog changes never rewrite an existing quote.
  const addFromCatalog = (productId) => {
    const product = products.find((p) => String(p.id) === productId)
    if (!product) return
    const row = {
      product: product.id,
      description: product.name,
      unit: product.unit || 'unidad',
      quantity: '1',
      unit_price: String(product.unit_price ?? ''),
      discount_percent: '',
    }
    setItems((prev) => {
      const last = prev[prev.length - 1]
      const lastIsBlank = last && !last.description.trim() && !last.unit_price
      return lastIsBlank ? [...prev.slice(0, -1), row] : [...prev, row]
    })
  }

  const removeItem = (index) => setItems((prev) => prev.filter((_, i) => i !== index))

  const handleSubmit = async (e) => {
    e.preventDefault()
    const filled = items.filter((item) => item.description.trim())
    if (!filled.length) {
      setError('Agrega al menos un producto con descripción')
      return
    }
    if (filled.some((item) => !(Number(item.quantity) > 0))) {
      setError('La cantidad de cada producto debe ser mayor que cero')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSaved({
        status,
        notes,
        tax_rate: Number(taxRate) || 0,
        issue_date: issueDate,
        valid_until: validUntil || null,
        items: filled.map((item) => ({
          product: item.product ?? null,
          description: item.description.trim(),
          unit: item.unit || 'unidad',
          quantity: Number(item.quantity),
          unit_price: Number(item.unit_price) || 0,
          discount_percent: Number(item.discount_percent) || 0,
        })),
      })
      onClose()
    } catch (err) {
      const data = err.response?.data
      setError(
        data?.valid_until?.[0] || data?.items?.[0] || data?.tax_rate?.[0]
        || 'Error al crear la cotización'
      )
      setSaving(false)
    }
  }

  return (
    <Modal title="Nueva cotización" onClose={onClose} className="modal-wide">
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="modal-field">
          <label>Productos / servicios</label>
          <div className="quote-items">
            <div className="quote-items-head">
              <span>Descripción</span>
              <span>Cant.</span>
              <span>Precio unitario</span>
              <span>Desc. %</span>
              <span>Subtotal</span>
              <span></span>
            </div>
            {items.map((item, index) => (
              <div key={index} className="quote-item-row">
                <input
                  value={item.description}
                  onChange={(e) => updateItem(index, 'description', e.target.value)}
                  placeholder="Ej: Bomba centrífuga 5 HP"
                  autoFocus={index === 0}
                />
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={item.quantity}
                  onChange={(e) => updateItem(index, 'quantity', e.target.value)}
                />
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={item.unit_price}
                  onChange={(e) => updateItem(index, 'unit_price', e.target.value)}
                  placeholder="0"
                />
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="any"
                  value={item.discount_percent}
                  onChange={(e) => updateItem(index, 'discount_percent', e.target.value)}
                  placeholder="0"
                />
                <span className="quote-item-subtotal">{formatMoney(itemSubtotal(item))}</span>
                <button
                  type="button"
                  className="quote-item-remove"
                  title="Quitar"
                  disabled={items.length === 1}
                  onClick={() => removeItem(index)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
          <div className="quote-items-actions">
            <button type="button" className="field-link" onClick={addItem}>
              <Plus size={12} /> Agregar línea
            </button>
            {products.length > 0 && (
              <select
                className="quote-catalog-picker"
                value=""
                onChange={(e) => { addFromCatalog(e.target.value); e.target.value = '' }}
              >
                <option value="">Agregar del catálogo...</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku ? `${p.sku} — ` : ''}{p.name} ({formatMoney(p.unit_price)})
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div className="quote-totals">
          <div className="quote-total-line">
            <span>Neto</span>
            <span>{formatMoney(subtotal)}</span>
          </div>
          <div className="quote-total-line">
            <span>
              IVA
              <input
                className="quote-tax-input"
                type="number"
                min="0"
                max="100"
                step="any"
                value={taxRate}
                onChange={(e) => setTaxRate(e.target.value)}
              />
              %
            </span>
            <span>{formatMoney(taxAmount)}</span>
          </div>
          <div className="quote-total-line grand">
            <span>Total</span>
            <strong>{formatMoney(total)}</strong>
          </div>
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Fecha de emisión</label>
            <input type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
          </div>
          <div className="modal-field">
            <label>Válida hasta</label>
            <input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
          </div>
          <div className="modal-field">
            <label>Estado</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {Object.entries(QUOTE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>

        <div className="modal-field">
          <label>Notas</label>
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Condiciones, plazos de entrega..." />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Crear cotización'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
