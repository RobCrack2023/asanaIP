import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Check, Trash2, Trophy, XCircle, FileText, Plus, ExternalLink,
} from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import '../pages/ProjectView.css'
import './OpportunityDetailPage.css'

const STAGE_OPTIONS = [
  { value: 'prospecto', label: 'Prospecto' },
  { value: 'cotizacion_enviada', label: 'Cotización enviada' },
  { value: 'negociacion', label: 'Negociación' },
]

const QUOTE_STATUS_LABELS = {
  draft: 'Borrador',
  sent: 'Enviada',
  approved: 'Aprobada',
  rejected: 'Rechazada',
}

export default function OpportunityDetailPage() {
  const { opportunityId } = useParams()
  const navigate = useNavigate()
  const [opportunity, setOpportunity] = useState(null)
  const [tasks, setTasks] = useState([])
  const [users, setUsers] = useState([])
  const [teams, setTeams] = useState([])
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [modal, setModal] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const newTaskRef = useRef(null)

  const load = () => {
    setLoadError(null)
    api.get(`/opportunities/${opportunityId}/`)
      .then((res) => setOpportunity(res.data))
      .catch(() => setLoadError('No tenés acceso a esta oportunidad o no existe.'))
    api.get(`/tasks/?opportunity=${opportunityId}`).then((res) => setTasks(res.data))
  }

  useEffect(() => {
    load()
    api.get('/users/').then((res) => setUsers(res.data))
    api.get('/teams/').then((res) => setTeams(res.data))
  }, [opportunityId])

  const updateOpportunity = async (data) => {
    setOpportunity((prev) => ({ ...prev, ...data }))
    await api.patch(`/opportunities/${opportunityId}/`, data)
  }

  const addTask = async () => {
    if (!newTaskTitle.trim()) return
    const title = newTaskTitle
    setNewTaskTitle('')
    const res = await api.post('/tasks/', { title, opportunity: Number(opportunityId) })
    setTasks((prev) => [...prev, res.data])
  }

  const toggleTask = async (task) => {
    const newStatus = task.status === 'completed' ? 'pending' : 'completed'
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: newStatus } : t)))
    await api.patch(`/tasks/${task.id}/`, { status: newStatus })
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

  const markWon = async (teamId) => {
    const res = await api.post(`/opportunities/${opportunityId}/mark_won/`, { team_id: teamId })
    navigate(`/project/${res.data.project}`)
  }

  const markLost = async (reason) => {
    const res = await api.post(`/opportunities/${opportunityId}/mark_lost/`, { reason })
    setOpportunity(res.data)
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
              {STAGE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
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
          <label>Fecha de cierre esperada</label>
          <input
            type="date"
            disabled={!isOpen}
            defaultValue={opportunity.expected_close_date || ''}
            onBlur={(e) => updateOpportunity({ expected_close_date: e.target.value || null })}
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
              <div key={q.id} className="opp-quote-row">
                <span className={`quote-status-badge ${q.status}`}>{QUOTE_STATUS_LABELS[q.status]}</span>
                <span className="opp-quote-amount">
                  {new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(q.total_amount)}
                </span>
                <span className="opp-quote-date">
                  {new Date(q.created_at).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })}
                </span>
                {q.notes && <span className="opp-quote-notes">{q.notes}</span>}
              </div>
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

      {modal?.type === 'won' && (
        <MarkWonModal teams={teams} onClose={() => setModal(null)} onConfirm={markWon} />
      )}
      {modal?.type === 'lost' && (
        <MarkLostModal onClose={() => setModal(null)} onConfirm={markLost} />
      )}
      {modal?.type === 'quote' && (
        <QuoteFormModal onClose={() => setModal(null)} onSaved={addQuote} />
      )}
    </div>
  )
}

function MarkWonModal({ teams, onClose, onConfirm }) {
  const [teamId, setTeamId] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!teamId) return
    setSaving(true)
    await onConfirm(teamId)
  }

  return (
    <Modal title="Marcar oportunidad como Ganada" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <p className="opp-modal-hint">Se creará un Proyecto nuevo y las tareas de esta oportunidad se moverán ahí. ¿A qué equipo pertenece?</p>
        <div className="modal-field">
          <label>Equipo *</label>
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)} required autoFocus>
            <option value="">Seleccionar equipo...</option>
            {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={!teamId || saving}>
            {saving ? 'Creando proyecto...' : 'Confirmar y crear proyecto'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function MarkLostModal({ onClose, onConfirm }) {
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    await onConfirm(reason)
    onClose()
  }

  return (
    <Modal title="Marcar oportunidad como Perdida" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="modal-field">
          <label>Motivo</label>
          <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="¿Por qué se perdió el negocio?" autoFocus />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Confirmar'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function QuoteFormModal({ onClose, onSaved }) {
  const [status, setStatus] = useState('draft')
  const [totalAmount, setTotalAmount] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    await onSaved({ status, total_amount: totalAmount || 0, notes })
    onClose()
  }

  return (
    <Modal title="Nueva cotización" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="modal-field">
            <label>Estado</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {Object.entries(QUOTE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="modal-field">
            <label>Monto total</label>
            <input type="number" value={totalAmount} onChange={(e) => setTotalAmount(e.target.value)} placeholder="0" autoFocus />
          </div>
        </div>
        <div className="modal-field">
          <label>Notas</label>
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Detalle de la cotización..." />
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
