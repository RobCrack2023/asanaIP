import { useState, useEffect } from 'react'
import api from '../api'
import Modal from './Modal'

const today = () => new Date().toISOString().slice(0, 10)

/**
 * The three rates the evaluación sheets keep in cells, as dated rows.
 *
 * Recording a date that already exists overwrites it, so correcting a typo is
 * just retyping — no duplicate-row error to explain.
 */
export default function ExchangeRatesModal({ onClose, onSaved }) {
  const [history, setHistory] = useState([])
  const [form, setForm] = useState({ date: today(), uf: '', usd: '', eur: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/exchange-rates/').then((res) => {
      setHistory(res.data)
      const latest = res.data[0]
      // Prefill with the last known values: rates move, they rarely change shape.
      if (latest) {
        setForm({ date: today(), uf: latest.uf, usd: latest.usd, eur: latest.eur })
      }
    })
  }, [])

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const res = await api.post('/exchange-rates/', {
        date: form.date,
        uf: form.uf || 0,
        usd: form.usd || 0,
        eur: form.eur || 0,
      })
      setHistory((prev) => [res.data, ...prev.filter((r) => r.date !== res.data.date)])
      onSaved?.(res.data)
      onClose()
    } catch (err) {
      const data = err.response?.data
      setError(data?.uf?.[0] || data?.usd?.[0] || data?.eur?.[0] || 'Error al guardar los valores')
      setSaving(false)
    }
  }

  return (
    <Modal title="Tipos de cambio" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <p className="opp-modal-hint">
          Valores usados para convertir costos en moneda extranjera a pesos. Cada
          cotización guarda los que estaban vigentes al emitirse.
        </p>

        <div className="modal-field">
          <label>Fecha</label>
          <input type="date" value={form.date} onChange={(e) => handleChange('date', e.target.value)} />
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>UF</label>
            <input type="number" min="0" step="any" value={form.uf}
                   onChange={(e) => handleChange('uf', e.target.value)} placeholder="0" autoFocus />
          </div>
          <div className="modal-field">
            <label>Dólar</label>
            <input type="number" min="0" step="any" value={form.usd}
                   onChange={(e) => handleChange('usd', e.target.value)} placeholder="0" />
          </div>
          <div className="modal-field">
            <label>Euro</label>
            <input type="number" min="0" step="any" value={form.eur}
                   onChange={(e) => handleChange('eur', e.target.value)} placeholder="0" />
          </div>
        </div>

        {history.length > 0 && (
          <div className="rates-history">
            <div className="rates-history-head">
              <span>Fecha</span><span>UF</span><span>Dólar</span><span>Euro</span><span>Registró</span>
            </div>
            {history.slice(0, 8).map((rate) => (
              <div key={rate.id} className="rates-history-row">
                <span>{rate.date}</span>
                <span>{Number(rate.uf).toLocaleString('es-CL')}</span>
                <span>{Number(rate.usd).toLocaleString('es-CL')}</span>
                <span>{Number(rate.eur).toLocaleString('es-CL')}</span>
                <span className="rates-author">{rate.updated_by_name || '—'}</span>
              </div>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : 'Guardar valores'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
