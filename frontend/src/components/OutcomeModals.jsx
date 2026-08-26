// Closing an opportunity always asks for something the stage alone cannot
// carry — a team to hand the project to, or a reason it was lost. Shared by
// the detail page and the pipeline board so both ask the same questions.
import { useState } from 'react'
import Modal from './Modal'

export function MarkWonModal({ teams, opportunityName, onClose, onConfirm }) {
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
        <p className="opp-modal-hint">
          Se creará un Proyecto nuevo{opportunityName ? ` para "${opportunityName}"` : ''} y las
          tareas de esta oportunidad se moverán ahí. ¿A qué equipo pertenece?
        </p>
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

export function MarkLostModal({ opportunityName, onClose, onConfirm }) {
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
        {opportunityName && <p className="opp-modal-hint">{opportunityName}</p>}
        <div className="modal-field">
          <label>Motivo</label>
          <textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="¿Por qué se perdió el negocio?"
            autoFocus
          />
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
