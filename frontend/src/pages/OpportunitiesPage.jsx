import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { TrendingUp, Trash2, Plus, LayoutGrid, List } from 'lucide-react'
import api from '../api'
import { formatMonth } from '../dates'
import { STAGE_CONFIG, STAGES, formatMoney } from '../stages'
import Modal from '../components/Modal'
import MonthSelect from '../components/MonthSelect'
import ClientFormModal from '../components/ClientFormModal'
import { MarkWonModal, MarkLostModal } from '../components/OutcomeModals'
import PipelineBoard from './PipelineBoard'
import './OpportunitiesPage.css'

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState([])
  const [clients, setClients] = useState([])
  const [teams, setTeams] = useState([])
  const [stageFilter, setStageFilter] = useState('all')
  const [view, setView] = useState('board')
  const [modal, setModal] = useState(null)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const clientFilter = searchParams.get('client')

  const load = () => {
    api.get('/opportunities/').then((res) => setOpportunities(res.data))
    api.get('/clients/').then((res) => setClients(res.data))
  }

  useEffect(() => {
    load()
    api.get('/teams/').then((res) => setTeams(res.data))
  }, [])

  const byClient = opportunities.filter((o) => (clientFilter ? String(o.client) === clientFilter : true))
  // The stage tabs belong to the list; the board already separates by stage.
  const filtered = view === 'board'
    ? byClient
    : byClient.filter((o) => (stageFilter === 'all' ? true : o.stage === stageFilter))

  const deleteOpportunity = async (id) => {
    if (!confirm('¿Eliminar esta oportunidad? Se perderá el historial de tareas y cotizaciones asociadas.')) return
    await api.delete(`/opportunities/${id}/`)
    load()
  }

  // Optimistic so the card lands where it was dropped; the reload afterwards
  // brings back whatever the server actually recorded.
  const moveToStage = async (opportunity, stage) => {
    setOpportunities((prev) => prev.map((o) => (o.id === opportunity.id ? { ...o, stage } : o)))
    try {
      await api.patch(`/opportunities/${opportunity.id}/`, { stage })
    } finally {
      load()
    }
  }

  const markWon = async (opportunity, teamId) => {
    await api.post(`/opportunities/${opportunity.id}/mark_won/`, { team_id: teamId })
    setModal(null)
    load()
  }

  const markLost = async (opportunity, reason) => {
    await api.post(`/opportunities/${opportunity.id}/mark_lost/`, { reason })
    load()
  }

  return (
    <div className="opps-page">
      <div className="opps-header">
        <div>
          <h1>Oportunidades</h1>
          <p>{filtered.length} oportunidades{clientFilter && ' de este cliente'}</p>
        </div>
        <div className="opps-header-actions">
          <div className="opps-view-toggle">
            <button
              className={`opps-view-btn ${view === 'board' ? 'active' : ''}`}
              onClick={() => setView('board')}
            >
              <LayoutGrid size={14} /> Tablero
            </button>
            <button
              className={`opps-view-btn ${view === 'list' ? 'active' : ''}`}
              onClick={() => setView('list')}
            >
              <List size={14} /> Lista
            </button>
          </div>
          <button className="btn btn-primary" onClick={() => setModal({ type: 'create' })}>
            <TrendingUp size={15} />
            Nueva oportunidad
          </button>
        </div>
      </div>

      {view === 'board' ? (
        <PipelineBoard
          opportunities={filtered}
          onMove={moveToStage}
          onRequestOutcome={(opportunity, stage) =>
            setModal({ type: stage === 'ganada' ? 'won' : 'lost', opportunity })
          }
          onOpen={(opportunity) => navigate(`/opportunities/${opportunity.id}`)}
        />
      ) : (
      <>
      <div className="opps-tabs">
        <button className={`opps-tab ${stageFilter === 'all' ? 'active' : ''}`} onClick={() => setStageFilter('all')}>
          Todas
        </button>
        {STAGES.map((stage) => (
          <button
            key={stage.value}
            className={`opps-tab ${stageFilter === stage.value ? 'active' : ''}`}
            onClick={() => setStageFilter(stage.value)}
          >
            {stage.label}
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
              <span className="ot-col-close">{formatMonth(opp.expected_close_date)}</span>
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
      </>
      )}

      {modal?.type === 'won' && (
        <MarkWonModal
          teams={teams}
          opportunityName={modal.opportunity.name}
          onClose={() => setModal(null)}
          onConfirm={(teamId) => markWon(modal.opportunity, teamId)}
        />
      )}
      {modal?.type === 'lost' && (
        <MarkLostModal
          opportunityName={modal.opportunity.name}
          onClose={() => setModal(null)}
          onConfirm={(reason) => markLost(modal.opportunity, reason)}
        />
      )}

      {modal?.type === 'create' && (
        <OpportunityFormModal
          clients={clients}
          defaultClientId={clientFilter}
          onClientCreated={(client) =>
            setClients((prev) => [...prev, client].sort((a, b) => a.name.localeCompare(b.name)))
          }
          onClose={() => setModal(null)}
          onSaved={(opp) => { load(); navigate(`/opportunities/${opp.id}`) }}
        />
      )}
    </div>
  )
}

function OpportunityFormModal({ clients, defaultClientId, onClientCreated, onClose, onSaved }) {
  const [form, setForm] = useState({
    client: defaultClientId || '',
    name: '',
    description: '',
    estimated_amount: '',
    expected_close_date: null,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [creatingClient, setCreatingClient] = useState(false)

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
        expected_close_date: form.expected_close_date,
      }
      const res = await api.post('/opportunities/', payload)
      onSaved(res.data)
    } catch (err) {
      setError('Error al crear la oportunidad')
      setSaving(false)
    }
  }

  return (
    <>
      <Modal title="Nueva oportunidad" onClose={onClose}>
        <form onSubmit={handleSubmit}>
          {error && <div className="form-error">{error}</div>}

          <div className="modal-field">
            <div className="modal-field-label-row">
              <label>Cliente *</label>
              <button type="button" className="field-link" onClick={() => setCreatingClient(true)}>
                <Plus size={12} />
                Nuevo cliente
              </button>
            </div>
            <select value={form.client} onChange={(e) => handleChange('client', e.target.value)} required autoFocus>
              <option value="">
                {clients.length ? 'Seleccionar cliente...' : 'Aún no hay clientes — crea uno'}
              </option>
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
              <label>Mes de cierre esperado</label>
              <MonthSelect
                value={form.expected_close_date}
                onChange={(date) => handleChange('expected_close_date', date)}
              />
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

      {creatingClient && (
        <ClientFormModal
          stacked
          onClose={() => setCreatingClient(false)}
          onSaved={(client) => {
            onClientCreated(client)
            handleChange('client', String(client.id))
          }}
        />
      )}
    </>
  )
}
