import { useState } from 'react'
import Modal from './Modal'

export default function CompleteTaskModal({ taskTitle, onClose, onConfirm }) {
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    await onConfirm(note)
  }

  return (
    <Modal title="Marcar como completada" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <p className="confirm-hint">¿Confirmás que "{taskTitle}" está completada?</p>
        <div className="modal-field">
          <label>Observación (opcional)</label>
          <textarea
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="¿Algo para dejar registrado sobre cómo quedó?"
            autoFocus
          />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Marcar como completada'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
