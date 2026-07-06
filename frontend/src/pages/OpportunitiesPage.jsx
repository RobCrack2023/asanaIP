import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { TrendingUp, Trash2 } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import './OpportunitiesPage.css'

const STAGE_CONFIG = {
  prospecto: { label: 'Prospecto', color: '#9ca0a5' },
  cotizacion_enviada: { label: 'Cotización enviada', color: '#4573d2' },
  negociacion: { label: 'Negociación', color: '#fd9a00' },
  ganada: { label: 'Ganada', color: '#5da283' },
  perdida: { label: 'Perdida', color: '#e8384f' },
}

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState([])
  const [clients, setClients] = useState([])
  const [stageFilter, setStageFilter] = useState('all')
  const [modal, setModal] = useState(null)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const clientFilter = searchParams.get('client')

  const load = () => {
    api.get('/opportunities/').then((res) => setOpportunities(res.data))
    api.get('/clients/').then((res) => setClients(res.data))
  }

  useEffect(() => { load() }, [])

  const filtered = opportunities
    .filter((o) => (clientFilter ? String(o.client) === clientFilter : true))
    .filter((o) => (stageFilter === 'all' ? true : o.stage === stageFilter))

  const deleteOpportunity = async (id) => {
    if (!confirm('¿Eliminar esta oportunidad? Se perderá el historial de tareas y cotizaciones asociadas.')) return
    await api.delete(`/opportunities/${id}/`)
    load()
  }

  const formatMoney = (amount) => {
    if (amount == null) return '—'
    return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(amount)
  }

  return (
    <div className="opps-page">
      <div className="opps-header">
        <div>
          <h1>Oportunidades</h1>
          <p>{filtered.length} oportunidades{clientFilter && ' de este cliente'}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ type: 'create' })}>
          <TrendingUp size={15} />
          Nueva oportunidad
        </button>
      </div>

      <div className="opps-tabs">
        <button className={`opps-tab ${stageFilter === 'all' ? 'active' : ''}`} onClick={() => setStageFilter('all')}>
          Todas
        </button>
        {Object.entries(STAGE_CONFIG).map(([key, conf]) => (
          <button key={key} className={`opps-tab ${stageFilter === key ? 'active' : ''}`} onClick={() => setStageFilter(key)}>
            {conf.label}
          </button>
        ))}
      </div>

      <div className="opps-table">
        <div className="opps-table-header">
          <span className="ot-col-name">Oportunidad</span>
          <span className="ot-col-client">Cliente</span>
          <span className="ot-col-stage">Etapa</span>
          <span className="ot-col-amount">Monto</span>
          <span className="ot-col-close">Cierre esperado</span>
          <span className="ot-col-actions"></span>
        </div>

        {filtered.map((opp) => {
          const stageConf = STAGE_CONFIG[opp.stage]
          return (
            <div key={opp.id} className="opps-table-row" onClick={() => navigate(`/opportunities/${opp.id}`)}>
              <span className="ot-col-name">{opp.name}</span>
              <span className="ot-col-client">{opp.client_name}</span>
              <span className="ot-col-stage">
                <span className="opp-stage-badge" style={{ background: stageConf.color + '22', color: stageConf.color }}>
                  {stageConf.label}
                </span>
              </span>
              <span className="ot-col-amount">{formatMoney(opp.estimated_amount)}</span>
              <span className="ot-col-close">
                {opp.expected_close_date
                  ? new Date(opp.expected_close_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })
                  : '—'}
              </span>
              <div className="ot-col-actions">
                <button className="ot-action-btn danger" title="Eliminar" onClick={(e) => { e.stopPropagation(); deleteOpportunity(opp.id) }}>
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          )
        })}

        {filtered.length === 0 && (
          <div className="opps-empty">No hay oportunidades en esta vista</div>
        )}
      </div>

      {modal?.type === 'create' && (
        <OpportunityFormModal
          clients={clients}
          defaultClientId={clientFilter}
          onClose={() => setModal(null)}
          onSaved={(opp) => { load(); navigate(`/opportunities/${opp.id}`) }}
        />
      )}
    </div>
  )
}

function OpportunityFormModal({ clients, defaultClientId, onClose, onSaved }) {
  const [form, setForm] = useState({
    client: defaultClientId || '',
    name: '',
    description: '',
    estimated_amount: '',
    expected_close_date: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.client) {
      setError('Nombre y cliente son obligatorios')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = {
        ...form,
        client: Number(form.client),
        estimated_amount: form.estimated_amount || null,
        expected_close_date: form.expected_close_date || null,
      }
      const res = await api.post('/opportunities/', payload)
      onSaved(res.data)
    } catch (err) {
      setError('Error al crear la oportunidad')
      setSaving(false)
    }
  }

  return (
    <Modal title="Nueva oportunidad" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="modal-field">
          <label>Cliente *</label>
          <select value={form.client} onChange={(e) => handleChange('client', e.target.value)} required autoFocus>
            <option value="">Seleccionar cliente...</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>

        <div className="modal-field">
          <label>Nombre de la oportunidad *</label>
          <input value={form.name} onChange={(e) => handleChange('name', e.target.value)} placeholder="Ej: Implementación ERP - Cliente XYZ" required />
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Monto estimado</label>
            <input type="number" value={form.estimated_amount} onChange={(e) => handleChange('estimated_amount', e.target.value)} placeholder="0" />
          </div>
          <div className="modal-field">
            <label>Fecha de cierre esperada</label>
            <input type="date" value={form.expected_close_date} onChange={(e) => handleChange('expected_close_date', e.target.value)} />
          </div>
        </div>

        <div className="modal-field">
          <label>Descripción</label>
          <textarea rows={3} value={form.description} onChange={(e) => handleChange('description', e.target.value)} placeholder="Detalles del negocio..." />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Creando...' : 'Crear oportunidad'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
