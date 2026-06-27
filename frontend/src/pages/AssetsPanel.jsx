import { useState, useEffect, useRef } from 'react'
import {
  Upload, Link2, FileText, Image, File, Mail, Trash2, Download,
  X, ExternalLink, FileSpreadsheet, Presentation, Filter,
} from 'lucide-react'
import api from '../api'
import './AssetsPanel.css'

const CATEGORY_ICONS = {
  image: Image,
  pdf: FileText,
  word: FileText,
  excel: FileSpreadsheet,
  powerpoint: Presentation,
  email: Mail,
  link: Link2,
  other: File,
}

const CATEGORY_LABELS = {
  image: 'Imagen',
  pdf: 'PDF',
  word: 'Word',
  excel: 'Excel',
  powerpoint: 'PowerPoint',
  email: 'Correo',
  link: 'Enlace',
  other: 'Archivo',
}

const CATEGORY_COLORS = {
  image: '#5da283',
  pdf: '#e8384f',
  word: '#4573d2',
  excel: '#2ea44f',
  powerpoint: '#fd9a00',
  email: '#7c3aed',
  link: '#4ecbc4',
  other: '#9ca0a5',
}

export default function AssetsPanel({ projectId }) {
  const [assets, setAssets] = useState([])
  const [filter, setFilter] = useState('all')
  const [addingLink, setAddingLink] = useState(false)
  const [linkUrl, setLinkUrl] = useState('')
  const [linkName, setLinkName] = useState('')
  const [emlViewer, setEmlViewer] = useState(null)
  const fileInputRef = useRef(null)

  const load = () => {
    api.get(`/assets/?project=${projectId}`).then((res) => setAssets(res.data))
  }

  useEffect(() => { load() }, [projectId])

  const uploadFile = async (e) => {
    const files = e.target.files
    if (!files.length) return

    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('name', file.name)
      formData.append('project', projectId)
      formData.append('asset_type', file.name.endsWith('.eml') ? 'email' : 'file')
      await api.post('/assets/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    }
    e.target.value = ''
    load()
  }

  const addLink = async () => {
    if (!linkUrl.trim()) return
    await api.post('/assets/', {
      project: projectId,
      asset_type: 'link',
      name: linkName.trim() || linkUrl,
      url: linkUrl,
    })
    setLinkUrl('')
    setLinkName('')
    setAddingLink(false)
    load()
  }

  const deleteAsset = async (id) => {
    await api.delete(`/assets/${id}/`)
    load()
  }

  const viewEml = async (asset) => {
    const res = await api.get(`/assets/${asset.id}/parse_eml/`)
    setEmlViewer({ ...res.data, assetId: asset.id, assetName: asset.name })
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1048576).toFixed(1)} MB`
  }

  const filtered = filter === 'all'
    ? assets
    : assets.filter((a) => a.category === filter)

  const categories = [...new Set(assets.map((a) => a.category))]

  return (
    <div className="assets-panel">
      <div className="assets-toolbar">
        <button className="assets-upload-btn" onClick={() => fileInputRef.current?.click()}>
          <Upload size={14} /> Subir archivo
        </button>
        <button className="assets-link-btn" onClick={() => setAddingLink(true)}>
          <Link2 size={14} /> Agregar enlace
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={uploadFile}
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp,.svg,.eml,.txt,.csv,.zip,.rar"
        />

        {categories.length > 1 && (
          <div className="assets-filters">
            <Filter size={13} />
            <button className={`assets-filter ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
              Todos ({assets.length})
            </button>
            {categories.map((cat) => {
              const count = assets.filter((a) => a.category === cat).length
              return (
                <button key={cat} className={`assets-filter ${filter === cat ? 'active' : ''}`} onClick={() => setFilter(cat)}>
                  {CATEGORY_LABELS[cat] || cat} ({count})
                </button>
              )
            })}
          </div>
        )}
      </div>

      {addingLink && (
        <div className="assets-link-form">
          <input
            placeholder="https://..."
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            autoFocus
          />
          <input
            placeholder="Nombre del enlace (opcional)"
            value={linkName}
            onChange={(e) => setLinkName(e.target.value)}
          />
          <div className="assets-link-actions">
            <button className="btn btn-primary btn-sm" onClick={addLink} disabled={!linkUrl.trim()}>Agregar</button>
            <button className="btn btn-secondary btn-sm" onClick={() => setAddingLink(false)}>Cancelar</button>
          </div>
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="assets-empty">
          {assets.length === 0
            ? 'No hay assets en este proyecto. Subí archivos o agregá enlaces.'
            : 'No hay assets en esta categoría.'}
        </div>
      ) : (
        <div className="assets-grid">
          {filtered.map((asset) => {
            const Icon = CATEGORY_ICONS[asset.category] || File
            const color = CATEGORY_COLORS[asset.category] || '#9ca0a5'
            return (
              <div key={asset.id} className="asset-card">
                <div className="asset-icon" style={{ background: color + '18', color }}>
                  <Icon size={22} />
                </div>
                <div className="asset-info">
                  <span className="asset-name" title={asset.name}>{asset.name}</span>
                  <span className="asset-meta">
                    {CATEGORY_LABELS[asset.category]}
                    {asset.file_size > 0 && ` · ${formatSize(asset.file_size)}`}
                    {asset.uploaded_by_name && ` · ${asset.uploaded_by_name}`}
                  </span>
                </div>
                <div className="asset-actions">
                  {asset.category === 'email' && (
                    <button className="asset-action-btn" title="Ver correo" onClick={() => viewEml(asset)}>
                      <Mail size={14} />
                    </button>
                  )}
                  {asset.asset_type === 'link' ? (
                    <a className="asset-action-btn" href={asset.url} target="_blank" rel="noopener noreferrer" title="Abrir enlace">
                      <ExternalLink size={14} />
                    </a>
                  ) : asset.file ? (
                    <a className="asset-action-btn" href={asset.file} download title="Descargar">
                      <Download size={14} />
                    </a>
                  ) : null}
                  <button className="asset-action-btn danger" title="Eliminar" onClick={() => deleteAsset(asset.id)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {emlViewer && (
        <div className="eml-overlay" onClick={(e) => { if (e.target === e.currentTarget) setEmlViewer(null) }}>
          <div className="eml-viewer">
            <div className="eml-header">
              <Mail size={18} />
              <span className="eml-subject">{emlViewer.subject || '(Sin asunto)'}</span>
              <button className="icon-btn" onClick={() => setEmlViewer(null)}><X size={18} /></button>
            </div>
            <div className="eml-fields">
              <div className="eml-field">
                <span className="eml-label">De:</span>
                <span>{emlViewer.from}</span>
              </div>
              <div className="eml-field">
                <span className="eml-label">Para:</span>
                <span>{emlViewer.to}</span>
              </div>
              {emlViewer.cc && (
                <div className="eml-field">
                  <span className="eml-label">CC:</span>
                  <span>{emlViewer.cc}</span>
                </div>
              )}
              <div className="eml-field">
                <span className="eml-label">Fecha:</span>
                <span>{emlViewer.date}</span>
              </div>
            </div>
            {emlViewer.attachments?.length > 0 && (
              <div className="eml-attachments">
                <span className="eml-label">Adjuntos:</span>
                {emlViewer.attachments.map((att, i) => (
                  <a
                    key={i}
                    className="eml-attachment-badge clickable"
                    href={`/api/assets/${emlViewer.assetId}/eml_attachment/${att.index}/`}
                    download={att.filename}
                    title="Descargar adjunto"
                  >
                    <Download size={12} /> {att.filename} ({formatSize(att.size)})
                  </a>
                ))}
              </div>
            )}
            <div className="eml-body">
              {emlViewer.body_html ? (
                <iframe
                  srcDoc={emlViewer.body_html}
                  className="eml-iframe"
                  sandbox="allow-same-origin"
                  title="Email content"
                />
              ) : (
                <pre className="eml-text">{emlViewer.body_text || '(Sin contenido)'}</pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
