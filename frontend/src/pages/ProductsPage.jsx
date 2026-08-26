import { useState, useEffect } from 'react'
import { Package, Edit2, Trash2, Search, History } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import { formatMoney } from '../stages'
import { formatDateTime } from '../dates'
import './ProductsPage.css'

// Margin the way the evaluación sheets state it: markup over cost, so 1.8
// means the item sells for 2.8 times what it cost.
const formatMargin = (margin) =>
  margin == null ? '—' : `${(Number(margin) * 100).toFixed(0)}%`

export default function ProductsPage() {
  const [products, setProducts] = useState([])
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)

  const load = () => {
    api.get('/products/').then((res) => setProducts(res.data))
  }

  useEffect(() => { load() }, [])

  const filtered = products.filter((p) => {
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
      </div>

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
              <span className="pt-name">{product.name}</span>
              {product.description && <span className="pt-description">{product.description}</span>}
            </div>
            <span className="pt-col-unit">{product.unit || '—'}</span>
            <span className="pt-col-supplier">{product.supplier || '—'}</span>
            <span className="pt-col-money cost">{formatMoney(product.cost)}</span>
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
        <ProductFormModal onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'edit' && (
        <ProductFormModal product={modal.product} onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'history' && (
        <PriceHistoryModal product={modal.product} onClose={() => setModal(null)} />
      )}
    </div>
  )
}

function ProductFormModal({ product, onClose, onSaved }) {
  const isEdit = !!product
  const [form, setForm] = useState({
    name: product?.name || '',
    sku: product?.sku || '',
    description: product?.description || '',
    unit: product?.unit || 'unidad',
    cost: product?.cost ?? '',
    unit_price: product?.unit_price ?? '',
    supplier: product?.supplier || '',
    lead_time_days: product?.lead_time_days ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const cost = Number(form.cost) || 0
  const liveMargin = cost ? (Number(form.unit_price) || 0) / cost - 1 : null

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
        cost: form.cost || 0,
        unit_price: form.unit_price || 0,
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
      setError(data?.sku?.[0] || data?.cost?.[0] || data?.unit_price?.[0]
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

        <div className="form-row">
          <div className="modal-field">
            <label>Costo (CLP)</label>
            <input type="number" min="0" step="any" value={form.cost} onChange={(e) => handleChange('cost', e.target.value)} placeholder="0" />
          </div>
          <div className="modal-field">
            <label>Precio unitario</label>
            <input type="number" min="0" step="any" value={form.unit_price} onChange={(e) => handleChange('unit_price', e.target.value)} placeholder="0" />
          </div>
        </div>

        <div className="product-margin-preview">
          <span>Margen sobre costo</span>
          <strong>{formatMargin(liveMargin)}</strong>
          <span className="product-margin-profit">
            Utilidad {formatMoney((Number(form.unit_price) || 0) - (Number(form.cost) || 0))}
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
