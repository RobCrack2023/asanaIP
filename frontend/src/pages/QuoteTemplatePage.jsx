import { useState, useEffect, useMemo } from 'react'
import { FileText, Save, Image as ImageIcon, Trash2, ExternalLink } from 'lucide-react'
import api from '../api'
import './QuoteTemplatePage.css'

// Shown when the company has no quotes yet, so the layout can still be
// designed on the day the account is opened.
const SAMPLE_QUOTE = {
  number: 1,
  issue_date: new Date().toISOString().slice(0, 10),
  valid_until: null,
  tax_rate: '19.00',
  display_currency: 'CLP',
  display_rate: '1',
  notes: 'Ejemplo: observaciones escritas al armar la cotización.',
  client_name: 'Cliente de ejemplo SpA',
  client_contact: 'Departamento de Compras',
  client_email: 'compras@ejemplo.cl',
  client_phone: '+56 9 0000 0000',
  opportunity_name: 'Proyecto de ejemplo',
  owner_name: '',
  items: [
    { id: 1, description: 'Equipo importado de ejemplo', unit: 'unidad', quantity: '1.00',
      unit_price: '1200000.00', discount_percent: '0.00', subtotal: '1200000.00' },
    { id: 2, description: 'Accesorio nacional de ejemplo', unit: 'unidad', quantity: '2.00',
      unit_price: '95000.00', discount_percent: '10.00', subtotal: '171000.00' },
  ],
  subtotal: '1371000.00',
  tax_amount: '260490.00',
  total_amount: '1631490.00',
}

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

const formatDate = (value) => {
  if (!value) return '—'
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return `${day} de ${MONTHS[month - 1]} de ${year}`
}

// Mirrors format_money in core/quote_pdf.py: amounts are stored in pesos and
// shown at the rate the quote was stamped with.
const money = (amount, currency, rate) => {
  const value = Number(amount || 0) / (Number(rate) || 1)
  if (currency === 'CLP') {
    return `$ ${value.toLocaleString('es-CL', { maximumFractionDigits: 0 })}`
  }
  return `${currency} ${value.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const quantity = (value) => {
  const number = Number(value || 0)
  return Number.isInteger(number) ? String(number) : number.toLocaleString('es-CL')
}

// The editable fields, with what they hold before anyone touches them. The
// logo lives outside this object: it travels as a file, not as a value.
const EMPTY = {
  company_name: '', tax_id: '', address: '', phone: '', email: '', website: '',
  accent_color: '#2D5F8A', document_title: 'COTIZACIÓN',
  show_item_number: true, show_unit: true, show_discount: true, show_quote_notes: false,
  intro_text: '', terms: '', footer_text: '', signature_name: '', signature_title: '',
}

/** The document exactly as the client receives it — the PDF, in HTML. */
function QuotePreview({ template, quote, logoUrl }) {
  const { display_currency: currency, display_rate: rate } = quote
  const accent = template.accent_color || '#2D5F8A'

  return (
    <div className="qt-doc">
      <div className="qt-doc-letterhead">
        <div className="qt-doc-logo">
          {logoUrl
            ? <img src={logoUrl} alt="" />
            : <span className="qt-doc-logo-empty"><ImageIcon size={14} /> Sin logo</span>}
        </div>
        <div className="qt-doc-company">
          <strong>{template.company_name || 'Razón social'}</strong>
          {template.tax_id && <span>RUT {template.tax_id}</span>}
          {template.address && <span>{template.address}</span>}
          {template.phone && <span>{template.phone}</span>}
          {template.email && <span>{template.email}</span>}
          {template.website && <span>{template.website}</span>}
        </div>
      </div>

      <div className="qt-doc-band" style={{ background: accent }}>
        <span className="qt-doc-band-title">{template.document_title || 'COTIZACIÓN'}</span>
        <div className="qt-doc-band-meta">
          <span>N° {quote.number ?? '—'}</span>
          <span>Fecha: {formatDate(quote.issue_date)}</span>
          {quote.valid_until && <span>Válida hasta: {formatDate(quote.valid_until)}</span>}
        </div>
      </div>

      <div className="qt-doc-parties">
        <div>
          <strong>{quote.client_name}</strong>
          {quote.client_contact && <span>{quote.client_contact}</span>}
          {quote.client_email && <span>{quote.client_email}</span>}
          {quote.client_phone && <span>{quote.client_phone}</span>}
        </div>
        <div>
          {quote.opportunity_name && <span><b>Referencia:</b> {quote.opportunity_name}</span>}
          {quote.owner_name && <span><b>Preparado por:</b> {quote.owner_name}</span>}
        </div>
      </div>

      {template.intro_text && <p className="qt-doc-intro">{template.intro_text}</p>}

      <table className="qt-doc-table">
        <thead>
          <tr style={{ background: accent }}>
            {template.show_item_number && <th className="c">N°</th>}
            <th>Descripción</th>
            {template.show_unit && <th className="c">Unidad</th>}
            <th className="c">Cant.</th>
            <th className="r">P. unitario</th>
            {template.show_discount && <th className="c">Desc.</th>}
            <th className="r">Subtotal</th>
          </tr>
        </thead>
        <tbody>
          {quote.items.map((item, index) => (
            <tr key={item.id}>
              {template.show_item_number && <td className="c">{index + 1}</td>}
              <td>{item.description}</td>
              {template.show_unit && <td className="c">{item.unit || '—'}</td>}
              <td className="c">{quantity(item.quantity)}</td>
              <td className="r">{money(item.unit_price, currency, rate)}</td>
              {template.show_discount && (
                <td className="c">
                  {Number(item.discount_percent) ? `${Number(item.discount_percent)}%` : '—'}
                </td>
              )}
              <td className="r">{money(item.subtotal, currency, rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="qt-doc-totals">
        <div><span>Neto</span><span>{money(quote.subtotal, currency, rate)}</span></div>
        <div><span>IVA {Number(quote.tax_rate)}%</span><span>{money(quote.tax_amount, currency, rate)}</span></div>
        <div className="grand" style={{ borderTopColor: accent }}>
          <span>TOTAL</span><span>{money(quote.total_amount, currency, rate)}</span>
        </div>
      </div>

      {currency !== 'CLP' && (
        <p className="qt-doc-note">
          Valores expresados en {currency} al tipo de cambio de la fecha de emisión.
        </p>
      )}

      {template.show_quote_notes && quote.notes && (
        <div className="qt-doc-section">
          <h4 style={{ color: accent }}>Observaciones</h4>
          <p>{quote.notes}</p>
        </div>
      )}

      {template.terms && (
        <div className="qt-doc-section">
          <h4 style={{ color: accent }}>Condiciones comerciales</h4>
          <p className="qt-doc-terms">{template.terms}</p>
        </div>
      )}

      <div className="qt-doc-signature">
        <div className="qt-doc-rule" />
        {template.signature_name && <strong>{template.signature_name}</strong>}
        {template.signature_title && <span>{template.signature_title}</span>}
        {template.company_name && <span>{template.company_name}</span>}
      </div>

      <div className="qt-doc-footer" style={{ borderTopColor: accent }}>
        <span>{template.footer_text}</span>
        <span>Página 1</span>
      </div>
    </div>
  )
}

/**
 * Where the company designs the document its clients receive.
 *
 * The preview is fed by /quotes/{id}/client-view/, the same payload the PDF is
 * built from, so what is on screen is what leaves the company — cost and
 * margin are not in the data at all, not merely hidden here.
 */
export default function QuoteTemplatePage({ user }) {
  const [template, setTemplate] = useState(EMPTY)
  const [savedLogo, setSavedLogo] = useState(null)
  const [logoFile, setLogoFile] = useState(null)
  const [clearLogo, setClearLogo] = useState(false)
  const [preview, setPreview] = useState(null)
  const [previewQuoteId, setPreviewQuoteId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const canEdit = user.is_staff || user.is_super_admin

  useEffect(() => {
    api.get('/quote-template/').then((res) => {
      setTemplate(Object.fromEntries(
        Object.keys(EMPTY).map((field) => [field, res.data[field] ?? EMPTY[field]])
      ))
      setSavedLogo(res.data.logo)
    })

    // Preview against a real document when there is one.
    api.get('/quotes/').then((res) => {
      const latest = res.data[0]
      if (!latest) return
      setPreviewQuoteId(latest.id)
      api.get(`/quotes/${latest.id}/client-view/`).then((r) => setPreview(r.data.quote))
    })
  }, [])

  const logoUrl = useMemo(() => {
    if (clearLogo) return null
    if (logoFile) return URL.createObjectURL(logoFile)
    return savedLogo
  }, [logoFile, savedLogo, clearLogo])

  const set = (field, value) => {
    setTemplate((prev) => ({ ...prev, [field]: value }))
    setSaved(false)
  }

  const save = async () => {
    setSaving(true)
    setError('')
    try {
      let payload = template
      let config
      // A picked file has to travel as multipart; everything else is plain JSON.
      if (logoFile || clearLogo) {
        const form = new FormData()
        Object.entries(template).forEach(([key, value]) => form.append(key, value ?? ''))
        form.append('logo', logoFile ?? '')
        payload = form
        config = { headers: { 'Content-Type': 'multipart/form-data' } }
      }
      const res = await api.patch('/quote-template/', payload, config)
      setSavedLogo(res.data.logo)
      setLogoFile(null)
      setClearLogo(false)
      setSaved(true)
    } catch (err) {
      const data = err.response?.data
      setError(data?.accent_color?.[0] || data?.document_title?.[0] || data?.error
        || 'No se pudo guardar la plantilla.')
    } finally {
      setSaving(false)
    }
  }

  const quote = preview ?? SAMPLE_QUOTE

  return (
    <div className="quote-template-page">
      <div className="qt-header">
        <div>
          <h1><FileText size={20} /> Plantilla de cotización</h1>
          <p>El documento que recibe el cliente. Costos, márgenes y utilidad no viajan en él.</p>
        </div>
        {canEdit && (
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            <Save size={14} /> {saving ? 'Guardando...' : saved ? 'Guardado' : 'Guardar plantilla'}
          </button>
        )}
      </div>

      {error && <div className="form-error">{error}</div>}
      {!canEdit && (
        <div className="qt-readonly">
          Solo un administrador puede modificar la plantilla. Puedes revisarla y descargar el PDF.
        </div>
      )}

      <div className="qt-layout">
        <div className="qt-form">
          <section>
            <h3>Identidad</h3>
            <div className="qt-logo-row">
              <div className="qt-logo-box">
                {logoUrl ? <img src={logoUrl} alt="Logo" /> : <ImageIcon size={22} />}
              </div>
              <div className="qt-logo-actions">
                <label className="btn btn-secondary">
                  Subir logo
                  <input type="file" accept="image/*" hidden disabled={!canEdit}
                         onChange={(e) => {
                           setLogoFile(e.target.files[0] ?? null)
                           setClearLogo(false)
                           setSaved(false)
                         }} />
                </label>
                {logoUrl && canEdit && (
                  <button className="qt-logo-clear"
                          onClick={() => { setLogoFile(null); setClearLogo(true); setSaved(false) }}>
                    <Trash2 size={13} /> Quitar
                  </button>
                )}
                <span className="qt-hint">PNG o JPG, fondo transparente de preferencia.</span>
              </div>
            </div>

            <div className="modal-field">
              <label>Razón social</label>
              <input value={template.company_name} disabled={!canEdit}
                     onChange={(e) => set('company_name', e.target.value)} />
            </div>
            <div className="form-row">
              <div className="modal-field">
                <label>RUT</label>
                <input value={template.tax_id} disabled={!canEdit}
                       onChange={(e) => set('tax_id', e.target.value)} placeholder="76.543.210-K" />
              </div>
              <div className="modal-field">
                <label>Teléfono</label>
                <input value={template.phone} disabled={!canEdit}
                       onChange={(e) => set('phone', e.target.value)} />
              </div>
            </div>
            <div className="modal-field">
              <label>Dirección</label>
              <input value={template.address} disabled={!canEdit}
                     onChange={(e) => set('address', e.target.value)} />
            </div>
            <div className="form-row">
              <div className="modal-field">
                <label>Correo</label>
                <input value={template.email} disabled={!canEdit}
                       onChange={(e) => set('email', e.target.value)} />
              </div>
              <div className="modal-field">
                <label>Sitio web</label>
                <input value={template.website} disabled={!canEdit}
                       onChange={(e) => set('website', e.target.value)} />
              </div>
            </div>
          </section>

          <section>
            <h3>Apariencia</h3>
            <div className="form-row">
              <div className="modal-field">
                <label>Título del documento</label>
                <input value={template.document_title} disabled={!canEdit}
                       onChange={(e) => set('document_title', e.target.value)} />
              </div>
              <div className="modal-field">
                <label>Color</label>
                <div className="qt-color">
                  <input type="color" value={template.accent_color} disabled={!canEdit}
                         onChange={(e) => set('accent_color', e.target.value.toUpperCase())} />
                  <input value={template.accent_color} disabled={!canEdit}
                         onChange={(e) => set('accent_color', e.target.value.toUpperCase())} />
                </div>
              </div>
            </div>
          </section>

          <section>
            <h3>Columnas de la tabla</h3>
            <p className="qt-hint">
              Precio unitario y subtotal son fijos. El costo y el margen no son una
              opción: no forman parte del documento.
            </p>
            {[
              ['show_item_number', 'Numerar los ítems'],
              ['show_unit', 'Mostrar la unidad'],
              ['show_discount', 'Mostrar el descuento por línea'],
            ].map(([field, label]) => (
              <label key={field} className="qt-check">
                <input type="checkbox" checked={template[field]} disabled={!canEdit}
                       onChange={(e) => set(field, e.target.checked)} />
                <span>{label}</span>
              </label>
            ))}
          </section>

          <section>
            <h3>Textos</h3>
            <div className="modal-field">
              <label>Presentación</label>
              <textarea rows={4} value={template.intro_text} disabled={!canEdit}
                        placeholder="Estimados señores: de acuerdo a lo solicitado..."
                        onChange={(e) => set('intro_text', e.target.value)} />
            </div>
            <div className="modal-field">
              <label>Condiciones comerciales</label>
              <textarea rows={6} value={template.terms} disabled={!canEdit}
                        placeholder={'• Plazo de entrega...\n• Forma de pago...\n• Garantía...'}
                        onChange={(e) => set('terms', e.target.value)} />
            </div>
            <label className="qt-check">
              <input type="checkbox" checked={template.show_quote_notes} disabled={!canEdit}
                     onChange={(e) => set('show_quote_notes', e.target.checked)} />
              <span>
                Imprimir las observaciones de cada cotización
                <em>Ese campo lo escribe quien arma el trato y puede tener notas internas.</em>
              </span>
            </label>
            <div className="form-row">
              <div className="modal-field">
                <label>Firma — nombre</label>
                <input value={template.signature_name} disabled={!canEdit}
                       onChange={(e) => set('signature_name', e.target.value)} />
              </div>
              <div className="modal-field">
                <label>Firma — cargo</label>
                <input value={template.signature_title} disabled={!canEdit}
                       onChange={(e) => set('signature_title', e.target.value)} />
              </div>
            </div>
            <div className="modal-field">
              <label>Pie de página</label>
              <input value={template.footer_text} disabled={!canEdit}
                     onChange={(e) => set('footer_text', e.target.value)} />
            </div>
          </section>
        </div>

        <div className="qt-preview">
          <div className="qt-preview-bar">
            <span>
              Vista previa
              {preview ? ` — cotización N° ${preview.number}` : ' — datos de ejemplo'}
            </span>
            {previewQuoteId && (
              <a className="qt-preview-link" href={`/api/quotes/${previewQuoteId}/pdf/`}
                 target="_blank" rel="noreferrer">
                <ExternalLink size={12} /> Ver PDF
              </a>
            )}
          </div>
          <div className="qt-preview-paper">
            <QuotePreview template={template} quote={quote} logoUrl={logoUrl} />
          </div>
        </div>
      </div>
    </div>
  )
}
