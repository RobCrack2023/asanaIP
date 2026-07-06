import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Edit2, Trash2, Search, ArrowUpRight } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import './ClientsPage.css'

export default function ClientsPage() {
  const [clients, setClients] = useState([])
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)
  const navigate = useNavigate()

  const load = () => {
    api.get('/clients/').then((res) => setClients(res.data))
  }

  useEffect(() => { load() }, [])

  const filtered = clients.filter((c) => {
    const term = search.toLowerCase()
    return c.name.toLowerCase().includes(term)
      || c.contact_name?.toLowerCase().includes(term)
      || c.email?.toLowerCase().includes(term)
  })

  const deleteClient = async (id) => {
    if (!confirm('¿Estás seguro de eliminar este cliente? También se eliminarán sus oportunidades.')) return
    await api.delete(`/clients/${id}/`)
    load()
  }

  return (
    <div className="clients-page">
      <div className="clients-header">
        <div>
          <h1>Clientes</h1>
          <p>{clients.length} clientes registrados</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ type: 'create' })}>
          <Building2 size={15} />
          Nuevo cliente
        </button>
      </div>

      <div className="clients-toolbar">
        <div className="search-box">
          <Search size={15} />
          <input
            placeholder="Buscar por nombre, contacto, email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="clients-table">
        <div className="clients-table-header">
          <span className="ct-col-name">Cliente</span>
          <span className="ct-col-contact">Contacto</span>
          <span className="ct-col-opps">Oportunidades</span>
          <span className="ct-col-actions"></span>
        </div>

        {filtered.map((client) => (
          <div key={client.id} className="clients-table-row">
            <div className="ct-col-name">
              <div className="ct-avatar"><Building2 size={16} /></div>
              <span className="ct-name">{client.name}</span>
            </div>
            <div className="ct-col-contact">
              <span className="ct-contact-name">{client.contact_name || '—'}</span>
              <span className="ct-contact-detail">{client.email || client.phone || ''}</span>
            </div>
            <div className="ct-col-opps">
              <button className="ct-opps-link" onClick={() => navigate(`/opportunities?client=${client.id}`)}>
                {client.opportunities_count} <ArrowUpRight size={12} />
              </button>
            </div>
            <div className="ct-col-actions">
              <button className="ct-action-btn" title="Editar" onClick={() => setModal({ type: 'edit', client })}>
                <Edit2 size={14} />
              </button>
              <button className="ct-action-btn danger" title="Eliminar" onClick={() => deleteClient(client.id)}>
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="clients-empty">No se encontraron clientes</div>
        )}
      </div>

      {modal?.type === 'create' && (
        <ClientFormModal onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'edit' && (
        <ClientFormModal client={modal.client} onClose={() => setModal(null)} onSaved={load} />
      )}
    </div>
  )
}

function ClientFormModal({ client, onClose, onSaved }) {
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
      if (isEdit) {
        await api.patch(`/clients/${client.id}/`, form)
      } else {
        await api.post('/clients/', form)
      }
      onSaved()
      onClose()
    } catch (err) {
      setError('Error al guardar el cliente')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={isEdit ? 'Editar cliente' : 'Nuevo cliente'} onClose={onClose}>
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
