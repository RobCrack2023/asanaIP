import { useState, useEffect } from 'react'
import { Package, Edit2, Trash2, Search } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import './ProductsPage.css'

const formatMoney = (amount) =>
  new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 })
    .format(Number(amount) || 0)

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
          <span className="pt-col-price">Precio unitario</span>
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
            <span className="pt-col-price">{formatMoney(product.unit_price)}</span>
            <div className="pt-col-actions">
              <button
                className="pt-action-btn"
                title={product.is_active ? 'Desactivar' : 'Activar'}
                onClick={() => toggleActive(product)}
              >
                {product.is_active ? 'Activo' : 'Inactivo'}
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
    unit_price: product?.unit_price ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre del producto es obligatorio')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = { ...form, unit_price: form.unit_price || 0 }
      if (isEdit) {
        await api.patch(`/products/${product.id}/`, payload)
      } else {
        await api.post('/products/', payload)
      }
      onSaved()
      onClose()
    } catch (err) {
      const data = err.response?.data
      setError(data?.sku?.[0] || data?.unit_price?.[0] || 'Error al guardar el producto')
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
          <label>Precio unitario</label>
          <input type="number" min="0" step="any" value={form.unit_price} onChange={(e) => handleChange('unit_price', e.target.value)} placeholder="0" />
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
