import { useState } from 'react'
import api from '../api'
import Modal from './Modal'
import './ClientFormModal.css'

export default function ClientFormModal({ client, stacked, onClose, onSaved }) {
  const isEdit = !!client
  const [form, setForm] = useState({
    name: client?.name || '',
    contact_name: client?.contact_name || '',
    email: client?.email || '',
    phone: client?.phone || '',
    notes: client?.notes || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre del cliente es obligatorio')
      return
    }
    setSaving(true)
    setError('')
    try {
      const res = isEdit
        ? await api.patch(`/clients/${client.id}/`, form)
        : await api.post('/clients/', form)
      onSaved(res.data)
      onClose()
    } catch (err) {
      setError('Error al guardar el cliente')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={isEdit ? 'Editar cliente' : 'Nuevo cliente'}
      onClose={onClose}
      className={stacked ? 'modal-stacked' : ''}
    >
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="modal-field">
          <label>Nombre *</label>
          <input value={form.name} onChange={(e) => handleChange('name', e.target.value)} placeholder="Nombre de la empresa" autoFocus required />
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Contacto</label>
            <input value={form.contact_name} onChange={(e) => handleChange('contact_name', e.target.value)} placeholder="Nombre del contacto" />
          </div>
          <div className="modal-field">
            <label>Email</label>
            <input type="email" value={form.email} onChange={(e) => handleChange('email', e.target.value)} placeholder="correo@ejemplo.com" />
          </div>
        </div>

        <div className="modal-field">
          <label>Teléfono</label>
          <input value={form.phone} onChange={(e) => handleChange('phone', e.target.value)} placeholder="+56 9 1234 5678" />
        </div>

        <div className="modal-field">
          <label>Notas</label>
          <textarea rows={3} value={form.notes} onChange={(e) => handleChange('notes', e.target.value)} placeholder="Notas internas..." />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : isEdit ? 'Guardar cambios' : 'Crear cliente'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
