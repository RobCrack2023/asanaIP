import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Lock, LockOpen } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import { formatMoney } from '../stages'
import { categoryColor } from '../categories'
import './ProjectSummaryPanel.css'

const today = () => new Date().toISOString().slice(0, 10)

const formatDate = (value) =>
  value
    ? new Date(`${value}T00:00:00`).toLocaleDateString('es', {
        day: 'numeric', month: 'short', year: 'numeric',
      })
    : '—'

const shortDate = (value) =>
  value
    ? new Date(`${value}T00:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'short' })
    : '—'

const percent = (value) => (value == null ? '—' : `${(Number(value) * 100).toFixed(1).replace('.', ',')}%`)

const units = (amount, currency) =>
  `${currency} ${Number(amount).toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const fileSize = (bytes) => {
  if (!bytes) return '—'
  return bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1e3))} KB`
}

const CATEGORY_NAMES = {
  image: 'Imagen', pdf: 'PDF', word: 'Word', excel: 'Excel',
  powerpoint: 'PowerPoint', email: 'Correo', link: 'Enlace', other: 'Archivo',
}

/**
 * The page read when the work is over: what was sold, what was done, what it
 * cost and what was left, in one place instead of scattered across the quote,
 * the expenses and the files.
 *
 * Computed from the records every time, so it cannot disagree with them. Closing
 * the project changes none of the figures; it marks the day the project stopped
 * moving, carries what was concluded, and shuts the books to new expenses.
 */
export default function ProjectSummaryPanel({ projectId }) {
  const [summary, setSummary] = useState(null)
  const [closing, setClosing] = useState(false)

  const load = useCallback(
    () => api.get(`/projects/${projectId}/summary/`).then((res) => setSummary(res.data)),
    [projectId],
  )

  useEffect(() => { load() }, [load])

  const reopen = async () => {
    if (!confirm('¿Reabrir el proyecto? Volverá a aceptar gastos; las conclusiones se conservan.')) return
    await api.post(`/projects/${projectId}/reopen/`)
    load()
  }

  if (!summary) return null

  const { project, deal, period, result, expenses, documents, tasks } = summary
  const quote = deal?.quote
  const provision = Number(result.provision)
  const hasCommission = Number(result.commission_rate) > 0
  const sold = Number(result.budget_sale) > 0

  const rows = [
    { label: 'Venta neta', quoted: result.budget_sale, real: result.budget_sale },
    { label: 'Costo', quoted: result.budget_cost, real: result.real_cost },
    { label: 'Utilidad', quoted: result.quoted_profit, real: result.real_profit },
    { label: 'Margen sobre el costo', quoted: result.quoted_margin, real: result.real_margin, isPercent: true },
    ...(hasCommission ? [{
      label: `Comisión${result.commission_to ? ` de ${result.commission_to}` : ''} (${Number(result.commission_rate)}% de la utilidad)`,
      quoted: result.budget_commission, real: result.real_commission,
    }] : []),
    { label: 'Utilidad neta', quoted: result.quoted_net_profit, real: result.real_net_profit, strong: true },
  ]

  return (
    <div className="ps-panel">
      <div className="ps-header">
        <div>
          <h2>Resumen del proyecto</h2>
          <p className={`ps-status ${project.is_closed ? 'closed' : 'open'}`}>
            {project.is_closed ? (
              <>
                <Lock size={13} /> Cerrado el {formatDate(project.closed_on)}
                {project.closed_by_name ? ` por ${project.closed_by_name}` : ''}
              </>
            ) : 'En curso'}
          </p>
        </div>
        {project.is_closed ? (
          <button className="btn btn-secondary ps-action" onClick={reopen}>
            <LockOpen size={14} /> Reabrir
          </button>
        ) : (
          <button className="btn btn-primary ps-action" onClick={() => setClosing(true)}>
            <Lock size={14} /> Cerrar proyecto
          </button>
        )}
      </div>

      {deal && (
        <section className="ps-section">
          <h3>El trato</h3>
          <dl className="ps-facts">
            <div><dt>Cliente</dt><dd>{deal.client}</dd></div>
            <div>
              <dt>Oportunidad</dt>
              <dd><Link to={`/opportunities/${deal.opportunity_id}`}>{deal.opportunity_name}</Link></dd>
            </div>
            {quote && (
              <>
                <div>
                  <dt>Cotización</dt>
                  <dd>N° {quote.number} · {quote.status_display} · {formatDate(quote.issue_date)}</dd>
                </div>
                <div>
                  <dt>Venta</dt>
                  <dd>
                    {quote.sale_in_display_currency != null
                      ? `${units(quote.sale_in_display_currency, quote.display_currency)} netos · `
                      : ''}
                    {formatMoney(result.budget_sale)}
                  </dd>
                </div>
              </>
            )}
            <div>
              <dt>Gastos registrados</dt>
              <dd>
                {period.from
                  ? `${formatDate(period.from)} al ${formatDate(period.to)} · ${period.days} ${period.days === 1 ? 'día' : 'días'}`
                  : 'Sin gastos todavía'}
              </dd>
            </div>
            <div><dt>Equipo</dt><dd>{project.area} / {project.team}</dd></div>
          </dl>
          {quote?.notes && <p className="ps-quote-notes">{quote.notes}</p>}
        </section>
      )}

      {project.description && (
        <section className="ps-section">
          <h3>Qué se hizo</h3>
          <p className="ps-text">{project.description}</p>
        </section>
      )}

      {sold ? (
        <section className="ps-section">
          <h3>Resultado</h3>
          <div className="ps-result">
            <div className="ps-result-row ps-result-head">
              <span />
              <span>Cotizado</span>
              <span>Real</span>
            </div>
            {rows.map((row) => (
              <div key={row.label} className={`ps-result-row ${row.strong ? 'strong' : ''}`}>
                <span>{row.label}</span>
                <span>{row.isPercent ? percent(row.quoted) : formatMoney(row.quoted)}</span>
                <span>{row.isPercent ? percent(row.real) : formatMoney(row.real)}</span>
              </div>
            ))}
          </div>
          {provision > 0 && (
            <p className="ps-note">
              De los {formatMoney(provision)} de gastos operacionales presupuestados se
              gastaron {formatMoney(result.extra_cost)};{' '}
              {Number(result.provision_balance) >= 0
                ? <>sobraron <strong>{formatMoney(result.provision_balance)}</strong>.</>
                : <>se excedieron en <strong>{formatMoney(Math.abs(Number(result.provision_balance)))}</strong>.</>}
            </p>
          )}
        </section>
      ) : (
        <section className="ps-section">
          <h3>Resultado</h3>
          <p className="ps-muted">
            Este proyecto no tiene un presupuesto sellado, así que no hay con qué comparar. Se
            sella al ganar la oportunidad que lo origina.
          </p>
        </section>
      )}

      <section className="ps-section">
        <h3>Gastos</h3>
        {expenses.count === 0 ? (
          <p className="ps-muted">Sin gastos registrados.</p>
        ) : (
          <div className="ps-columns">
            <div>
              <h4>Costo real por categoría</h4>
              {result.by_category.map((row) => (
                <div key={row.category} className="ps-line">
                  <span className="ps-cat">
                    <i className="cat-dot" style={{ background: categoryColor(row.category) }} />
                    {row.label}
                  </span>
                  <span>{formatMoney(row.real)}</span>
                </div>
              ))}
            </div>
            <div>
              <h4>Por día</h4>
              {expenses.by_day.map((day) => (
                <div key={day.date} className="ps-line">
                  <span>{shortDate(day.date)} <em>· {day.count} {day.count === 1 ? 'gasto' : 'gastos'}</em></span>
                  <span>{formatMoney(day.total)}</span>
                </div>
              ))}
              <div className="ps-line ps-total">
                <span>Total registrado</span>
                <span>{formatMoney(expenses.total)}</span>
              </div>
            </div>
            <div>
              <h4>Los mayores</h4>
              {expenses.largest.map((item, index) => (
                <div key={`${item.description}-${index}`} className="ps-line">
                  <span>{item.description} <em>· {shortDate(item.incurred_on)}</em></span>
                  <span>{formatMoney(item.amount)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {documents.length > 0 && (
        <section className="ps-section">
          <h3>Documentos</h3>
          {documents.map((doc) => (
            <div key={doc.id} className="ps-line">
              <span>{doc.name}</span>
              <span className="ps-muted">{CATEGORY_NAMES[doc.category] ?? 'Archivo'} · {fileSize(doc.file_size)}</span>
            </div>
          ))}
        </section>
      )}

      {tasks.total > 0 && (
        <section className="ps-section">
          <h3>Tareas</h3>
          <p className="ps-text">{tasks.completed} de {tasks.total} completadas.</p>
        </section>
      )}

      <section className="ps-section">
        <h3>Conclusiones del cierre</h3>
        {project.closing_notes
          ? <p className="ps-text">{project.closing_notes}</p>
          : <p className="ps-muted">
              {project.is_closed
                ? 'Se cerró sin conclusiones escritas.'
                : 'Se escriben al cerrar el proyecto.'}
            </p>}
      </section>

      {closing && (
        <CloseModal projectId={projectId} onClose={() => setClosing(false)} onClosed={load} />
      )}
    </div>
  )
}

function CloseModal({ projectId, onClose, onClosed }) {
  const [closedOn, setClosedOn] = useState(today())
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post(`/projects/${projectId}/close/`, { closed_on: closedOn, notes })
      onClosed()
      onClose()
    } catch (err) {
      setError(err.response?.data?.error || 'No se pudo cerrar el proyecto.')
      setSaving(false)
    }
  }

  return (
    <Modal title="Cerrar proyecto" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <p className="ps-modal-hint">
          Al cerrar, el proyecto deja de aceptar gastos. Las cifras no cambian. Si llega una
          factura tardía puedes reabrirlo.
        </p>

        <div className="modal-field">
          <label>Fecha de cierre</label>
          <input type="date" value={closedOn} onChange={(e) => setClosedOn(e.target.value)} required />
        </div>

        <div className="modal-field">
          <label>Conclusiones</label>
          <textarea rows={6} value={notes} onChange={(e) => setNotes(e.target.value)}
                    placeholder="Qué se logró, qué quedó pendiente, qué aprendió el equipo." />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Cerrando...' : 'Cerrar proyecto'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
