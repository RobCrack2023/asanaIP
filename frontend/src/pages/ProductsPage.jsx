import { useState, useEffect } from 'react'
import { Package, Edit2, Trash2, Search, History, RefreshCw, Coins, AlertTriangle } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import ExchangeRatesModal from '../components/ExchangeRatesModal'
import { formatMoney } from '../stages'
import { CATEGORIES, categoryColor, categoryShort } from '../categories'
import { formatDateTime } from '../dates'
import './ProductsPage.css'

// Margin the way the evaluación sheets state it: markup over cost, so 1.8
// means the item sells for 2.8 times what it cost.
const formatMargin = (margin) =>
  margin == null ? '—' : `${(Number(margin) * 100).toFixed(0)}%`

const CURRENCIES = ['CLP', 'USD', 'EUR', 'UF']

// DDP means the supplier delivers duty paid, so there is nothing to add on
// top — the multiplier only applies under the other terms.
const INCOTERMS = ['DDP', 'DAP', 'CIF', 'FOB', 'EXW']

const formatAmount = (amount, currency) =>
  currency === 'CLP'
    ? formatMoney(amount)
    : `${currency} ${Number(amount || 0).toLocaleString('es-CL', { maximumFractionDigits: 2 })}`

export default function ProductsPage() {
  const [products, setProducts] = useState([])
  const [rates, setRates] = useState(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [modal, setModal] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = () => {
    api.get('/products/').then((res) => setProducts(res.data))
    api.get('/exchange-rates/current/').then((res) => setRates(res.data))
  }

  useEffect(() => { load() }, [])

  const staleCount = products.filter((p) => p.cost_is_stale).length

  const refreshCosts = async () => {
    setRefreshing(true)
    try {
      await api.post('/products/refresh_costs/', {})
      load()
    } finally {
      setRefreshing(false)
    }
  }

  const filtered = products.filter((p) => {
    if (category && p.category !== category) return false
    const term = search.toLowerCase()
    return p.name.toLowerCase().includes(term)
      || p.sku?.toLowerCase().includes(term)
      || p.description?.toLowerCase().includes(term)
  })

  const deleteProduct = async (product) => {
    if (!confirm(`¿Eliminar "${product.name}" del catálogo? Las cotizaciones ya emitidas no se modifican.`)) return
    await api.delete(`/products/${product.id}/`)
    load()
  }

  const toggleActive = async (product) => {
    await api.patch(`/products/${product.id}/`, { is_active: !product.is_active })
    load()
  }

  return (
    <div className="products-page">
      <div className="products-header">
        <div>
          <h1>Productos</h1>
          <p>{products.length} productos en el catálogo</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ type: 'create' })}>
          <Package size={15} />
          Nuevo producto
        </button>
      </div>

      <div className="products-toolbar">
        <div className="search-box">
          <Search size={15} />
          <input
            placeholder="Buscar por nombre, código, descripción..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          className="products-category-filter"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">Todas las categorías</option>
          {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>

        <button className="rates-chip" onClick={() => setModal({ type: 'rates' })}>
          <Coins size={13} />
          {rates
            ? `UF ${Number(rates.uf).toLocaleString('es-CL')} · USD ${Number(rates.usd).toLocaleString('es-CL')} · EUR ${Number(rates.eur).toLocaleString('es-CL')}`
            : 'Cargar tipos de cambio'}
        </button>
      </div>

      {staleCount > 0 && (
        <div className="stale-costs-banner">
          <AlertTriangle size={14} />
          <span>
            {staleCount} {staleCount === 1 ? 'producto tiene' : 'productos tienen'} el costo
            calculado con un tipo de cambio anterior.
          </span>
          <button className="btn btn-primary" onClick={refreshCosts} disabled={refreshing}>
            <RefreshCw size={13} />
            {refreshing ? 'Actualizando...' : 'Actualizar costos'}
          </button>
        </div>
      )}

      <div className="products-table">
        <div className="products-table-header">
          <span className="pt-col-sku">Código</span>
          <span className="pt-col-name">Producto</span>
          <span className="pt-col-unit">Unidad</span>
          <span className="pt-col-supplier">Proveedor</span>
          <span className="pt-col-money">Costo</span>
          <span className="pt-col-money">Precio</span>
          <span className="pt-col-margin">Margen</span>
          <span className="pt-col-actions"></span>
        </div>

        {filtered.map((product) => (
          <div key={product.id} className={`products-table-row ${product.is_active ? '' : 'inactive'}`}>
            <span className="pt-col-sku">{product.sku || '—'}</span>
            <div className="pt-col-name">
              <span className="pt-name">
                {product.name}
                <span className="pt-category" style={{ background: categoryColor(product.category) }}>
                  {categoryShort(product.category)}
                </span>
              </span>
              {product.description && <span className="pt-description">{product.description}</span>}
            </div>
            <span className="pt-col-unit">{product.unit || '—'}</span>
            <span className="pt-col-supplier">{product.supplier || '—'}</span>
            <span className="pt-col-money cost">
              {formatMoney(product.cost)}
              {product.currency !== 'CLP' && (
                <span className={`pt-origin ${product.cost_is_stale ? 'stale' : ''}`}>
                  {formatAmount(product.cost_amount, product.currency)}
                  {product.incoterm !== 'DDP' && ` ·${product.incoterm}`}
                </span>
              )}
            </span>
            <span className="pt-col-money">{formatMoney(product.unit_price)}</span>
            <span className={`pt-col-margin ${product.margin == null ? 'unset' : ''}`}>
              {formatMargin(product.margin)}
            </span>
            <div className="pt-col-actions">
              <button
                className="pt-action-btn"
                title={product.is_active ? 'Desactivar' : 'Activar'}
                onClick={() => toggleActive(product)}
              >
                {product.is_active ? 'Activo' : 'Inactivo'}
              </button>
              <button
                className="pt-action-btn"
                title="Historial de precios"
                onClick={() => setModal({ type: 'history', product })}
              >
                <History size={14} />
              </button>
              <button className="pt-action-btn" title="Editar" onClick={() => setModal({ type: 'edit', product })}>
                <Edit2 size={14} />
              </button>
              <button className="pt-action-btn danger" title="Eliminar" onClick={() => deleteProduct(product)}>
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="products-empty">
            {products.length === 0 ? 'Aún no hay productos en el catálogo' : 'No se encontraron productos'}
          </div>
        )}
      </div>

      {modal?.type === 'create' && (
        <ProductFormModal rates={rates} onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'edit' && (
        <ProductFormModal rates={rates} product={modal.product} onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'history' && (
        <PriceHistoryModal product={modal.product} onClose={() => setModal(null)} />
      )}
      {modal?.type === 'rates' && (
        <ExchangeRatesModal onClose={() => setModal(null)} onSaved={load} />
      )}
    </div>
  )
}

function ProductFormModal({ product, rates, onClose, onSaved }) {
  const isEdit = !!product
  const [form, setForm] = useState({
    name: product?.name || '',
    sku: product?.sku || '',
    description: product?.description || '',
    unit: product?.unit || 'unidad',
    category: product?.category || 'equipo',
    currency: product?.currency || 'CLP',
    cost_amount: product?.cost_amount ?? '',
    incoterm: product?.incoterm || 'DDP',
    import_multiplier: product?.import_multiplier ?? '1',
    // Stored as a fraction; shown as a percentage.
    default_margin: product ? String(Number(product.default_margin) * 100) : '',
    supplier: product?.supplier || '',
    lead_time_days: product?.lead_time_days ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  // Mirror the server's conversion so the peso cost is visible while typing.
  const rate = form.currency === 'CLP' ? 1 : Number(rates?.[form.currency.toLowerCase()]) || 0
  const multiplier = form.incoterm === 'DDP' ? 1 : Number(form.import_multiplier) || 1
  const cost = (Number(form.cost_amount) || 0) * rate * multiplier
  const liveMargin = (Number(form.default_margin) || 0) / 100
  const price = cost * (1 + liveMargin)
  const missingRate = form.currency !== 'CLP' && !rate

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre del producto es obligatorio')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = {
        ...form,
        cost_amount: form.cost_amount || 0,
        import_multiplier: form.import_multiplier || 1,
        default_margin: (Number(form.default_margin) || 0) / 100,
        lead_time_days: form.lead_time_days === '' ? null : Number(form.lead_time_days),
      }
      if (isEdit) {
        await api.patch(`/products/${product.id}/`, payload)
      } else {
        await api.post('/products/', payload)
      }
      onSaved()
      onClose()
    } catch (err) {
      const data = err.response?.data
      setError(data?.sku?.[0] || data?.currency?.[0] || data?.cost_amount?.[0]
        || data?.import_multiplier?.[0] || data?.default_margin?.[0]
        || 'Error al guardar el producto')
      setSaving(false)
    }
  }

  return (
    <Modal title={isEdit ? 'Editar producto' : 'Nuevo producto'} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="modal-field">
          <label>Nombre *</label>
          <input value={form.name} onChange={(e) => handleChange('name', e.target.value)} placeholder="Ej: Bomba centrífuga 5 HP" autoFocus required />
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Código</label>
            <input value={form.sku} onChange={(e) => handleChange('sku', e.target.value)} placeholder="Opcional" />
          </div>
          <div className="modal-field">
            <label>Unidad</label>
            <input value={form.unit} onChange={(e) => handleChange('unit', e.target.value)} placeholder="unidad, m, hr..." />
          </div>
        </div>

        <div className="modal-field">
          <label>Categoría</label>
          <select value={form.category} onChange={(e) => handleChange('category', e.target.value)}>
            {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
          <span className="field-hint">
            Un gasto operacional, un flete o la prevención son fichas de catálogo como
            cualquier equipo: se cotizan con su propio margen.
          </span>
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Moneda</label>
            <select value={form.currency} onChange={(e) => handleChange('currency', e.target.value)}>
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="modal-field">
            <label>Costo del proveedor</label>
            <input type="number" min="0" step="any" value={form.cost_amount} onChange={(e) => handleChange('cost_amount', e.target.value)} placeholder="0" />
          </div>
          <div className="modal-field">
            <label>Margen %</label>
            <input type="number" step="any" value={form.default_margin} onChange={(e) => handleChange('default_margin', e.target.value)} placeholder="30" />
          </div>
        </div>

        {form.currency !== 'CLP' && (
          <div className="form-row">
            <div className="modal-field">
              <label>Incoterm</label>
              <select value={form.incoterm} onChange={(e) => handleChange('incoterm', e.target.value)}>
                {INCOTERMS.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div className="modal-field">
              <label>Multiplicador importación</label>
              <input
                type="number"
                min="0"
                step="any"
                disabled={form.incoterm === 'DDP'}
                value={form.import_multiplier}
                onChange={(e) => handleChange('import_multiplier', e.target.value)}
                placeholder="1"
              />
              {form.incoterm === 'DDP' && (
                <span className="field-hint">DDP ya incluye flete y aranceles</span>
              )}
            </div>
          </div>
        )}

        {missingRate && (
          <div className="form-error">
            No hay un valor de {form.currency} cargado. Registra el tipo de cambio antes de costear en esta moneda.
          </div>
        )}

        <div className="product-margin-preview">
          <span>Costo {formatMoney(cost)} · margen {formatMargin(liveMargin)} →</span>
          <strong>{formatMoney(price)}</strong>
          <span className="product-margin-profit">
            precio sugerido · utilidad {formatMoney(price - cost)}
          </span>
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Proveedor</label>
            <input value={form.supplier} onChange={(e) => handleChange('supplier', e.target.value)} placeholder="Ej: Prodalam" />
          </div>
          <div className="modal-field">
            <label>Plazo de entrega (días)</label>
            <input type="number" min="0" value={form.lead_time_days} onChange={(e) => handleChange('lead_time_days', e.target.value)} placeholder="30" />
          </div>
        </div>

        <div className="modal-field">
          <label>Descripción</label>
          <textarea rows={2} value={form.description} onChange={(e) => handleChange('description', e.target.value)} placeholder="Detalle técnico, alcance..." />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : isEdit ? 'Guardar cambios' : 'Crear producto'}
          </button>
        </div>
      </form>
    </Modal>
  )
}


function PriceHistoryModal({ product, onClose }) {
  const [entries, setEntries] = useState(null)

  useEffect(() => {
    api.get(`/products/${product.id}/price_history/`).then((res) => setEntries(res.data))
  }, [product.id])

  // Entries arrive newest first; the delta compares each one with the entry
  // that preceded it in time, which sits one position later in the list.
  const costDelta = (index) => {
    if (!entries || index >= entries.length - 1) return null
    const previous = Number(entries[index + 1].cost)
    if (!previous) return null
    return (Number(entries[index].cost) - previous) / previous
  }

  return (
    <Modal title={`Historial de precios — ${product.name}`} onClose={onClose} className="modal-wide">
      {entries === null && <div className="products-empty">Cargando...</div>}

      {entries?.length === 0 && (
        <div className="products-empty">Sin cambios registrados todavía</div>
      )}

      {entries?.length > 0 && (
        <div className="price-history">
          <div className="price-history-head">
            <span>Fecha</span>
            <span>Costo</span>
            <span>Var.</span>
            <span>Precio</span>
            <span>Margen</span>
            <span>Proveedor</span>
            <span>Registró</span>
          </div>
          {entries.map((entry, index) => {
            const delta = costDelta(index)
            return (
              <div key={entry.id} className="price-history-row">
                <span className="ph-date">{formatDateTime(entry.recorded_at)}</span>
                <span>{formatMoney(entry.cost)}</span>
                <span className={`ph-delta ${delta > 0 ? 'up' : delta < 0 ? 'down' : ''}`}>
                  {delta == null ? '—' : `${delta > 0 ? '+' : ''}${(delta * 100).toFixed(1)}%`}
                </span>
                <span>{formatMoney(entry.unit_price)}</span>
                <span>{formatMargin(entry.margin)}</span>
                <span className="ph-supplier">{entry.supplier || '—'}</span>
                <span className="ph-author">{entry.recorded_by_name || '—'}</span>
              </div>
            )
          })}
          {entries.some((e) => e.note) && (
            <div className="price-history-notes">
              {entries.filter((e) => e.note).map((e) => (
                <div key={e.id}>{formatDateTime(e.recorded_at)} — {e.note}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="modal-actions">
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cerrar</button>
      </div>
    </Modal>
  )
}
