import { useState, useEffect } from 'react'
import { Building2, Users, FolderOpen, Plus, Edit2, Power, Trash2, ChevronDown, ChevronRight, LogOut, Shield } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import './SuperAdminPage.css'

export default function SuperAdminPage({ user, onLogout }) {
  const [orgs, setOrgs] = useState([])
  const [plans, setPlans] = useState([])
  const [expandedOrg, setExpandedOrg] = useState(null)
  const [orgUsers, setOrgUsers] = useState({})
  const [modal, setModal] = useState(null)

  const load = () => {
    api.get('/organizations/').then((res) => setOrgs(res.data))
    api.get('/plans/').then((res) => setPlans(res.data))
  }

  useEffect(() => { load() }, [])

  const toggleOrg = async (orgId) => {
    if (expandedOrg === orgId) {
      setExpandedOrg(null)
      return
    }
    setExpandedOrg(orgId)
    if (!orgUsers[orgId]) {
      const res = await api.get(`/organizations/${orgId}/users/`)
      setOrgUsers((prev) => ({ ...prev, [orgId]: res.data }))
    }
  }

  const toggleActive = async (orgId) => {
    await api.post(`/organizations/${orgId}/toggle_active/`)
    load()
  }

  const deleteOrg = async (orgId) => {
    if (!confirm('¿Eliminar esta empresa y todos sus datos?')) return
    await api.delete(`/organizations/${orgId}/`)
    load()
  }

  const totalUsers = orgs.reduce((sum, o) => sum + (o.users_count || 0), 0)
  const totalProjects = orgs.reduce((sum, o) => sum + (o.projects_count || 0), 0)

  return (
    <div className="sa-layout">
      <div className="sa-topbar">
        <div className="sa-topbar-brand">
          <div className="sa-topbar-logo">IP</div>
          <span className="sa-topbar-title">AsanaIP</span>
          <span className="sa-topbar-badge"><Shield size={12} /> Super Admin</span>
        </div>
        <div className="sa-topbar-user">
          <span>{user?.full_name || 'Admin'}</span>
          <button className="sa-logout-btn" onClick={onLogout} title="Cerrar sesión">
            <LogOut size={16} />
          </button>
        </div>
      </div>

      <div className="sa-page">
        <div className="sa-header">
          <div>
            <h1>Panel de Administración</h1>
            <p>Gestión de empresas y planes</p>
          </div>
          <button className="btn btn-primary" onClick={() => setModal({ type: 'org' })}>
            <Plus size={15} /> Nueva empresa
          </button>
        </div>

      <div className="sa-stats">
        <div className="sa-stat">
          <Building2 size={22} />
          <div>
            <span className="sa-stat-num">{orgs.length}</span>
            <span className="sa-stat-label">Empresas</span>
          </div>
        </div>
        <div className="sa-stat">
          <Users size={22} />
          <div>
            <span className="sa-stat-num">{totalUsers}</span>
            <span className="sa-stat-label">Usuarios totales</span>
          </div>
        </div>
        <div className="sa-stat">
          <FolderOpen size={22} />
          <div>
            <span className="sa-stat-num">{totalProjects}</span>
            <span className="sa-stat-label">Proyectos totales</span>
          </div>
        </div>
      </div>

      <div className="sa-section">
        <h2>Empresas</h2>
        <div className="sa-orgs">
          {orgs.map((org) => (
            <div key={org.id} className={`sa-org-card ${!org.is_active ? 'inactive' : ''}`}>
              <div className="sa-org-row" onClick={() => toggleOrg(org.id)}>
                <span className="sa-org-expand">
                  {expandedOrg === org.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </span>
                <div className="sa-org-info">
                  <span className="sa-org-name">{org.name}</span>
                  <span className="sa-org-slug">/{org.slug}</span>
                </div>
                <span className="sa-org-plan">{org.plan_name || 'Sin plan'}</span>
                <span className="sa-org-users">
                  <Users size={13} /> {org.users_count}/{org.max_users}
                </span>
                <span className="sa-org-projects">
                  <FolderOpen size={13} /> {org.projects_count}
                </span>
                <span className={`sa-org-status ${org.is_active ? 'active' : 'off'}`}>
                  {org.is_active ? 'Activa' : 'Inactiva'}
                </span>
                <div className="sa-org-actions" onClick={(e) => e.stopPropagation()}>
                  <button className="sa-action" title="Editar" onClick={() => setModal({ type: 'org', org })}>
                    <Edit2 size={14} />
                  </button>
                  <button className="sa-action" title={org.is_active ? 'Desactivar' : 'Activar'} onClick={() => toggleActive(org.id)}>
                    <Power size={14} />
                  </button>
                  <button className="sa-action danger" title="Eliminar" onClick={() => deleteOrg(org.id)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {expandedOrg === org.id && (
                <div className="sa-org-detail">
                  <div className="sa-org-detail-header">
                    <span>Usuarios de {org.name}</span>
                    <button className="btn btn-primary btn-sm" onClick={() => setModal({ type: 'user', orgId: org.id, orgName: org.name, maxUsers: org.max_users, currentUsers: org.users_count })}>
                      <Plus size={12} /> Agregar usuario
                    </button>
                  </div>
                  {orgUsers[org.id]?.length > 0 ? (
                    <div className="sa-users-list">
                      {orgUsers[org.id].map((u) => (
                        <div key={u.id} className="sa-user-row">
                          <span className="sa-user-avatar">{(u.first_name?.[0] || u.username[0]).toUpperCase()}</span>
                          <div className="sa-user-info">
                            <span>{u.full_name}</span>
                            <span className="sa-user-meta">@{u.username} · {u.job_title || 'Sin cargo'}</span>
                          </div>
                          {u.is_staff && <span className="sa-badge admin">Admin</span>}
                          <span className={`sa-badge ${u.is_active ? 'active' : 'off'}`}>
                            {u.is_active ? 'Activo' : 'Inactivo'}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="sa-empty">Sin usuarios</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {modal?.type === 'org' && (
        <OrgFormModal org={modal.org} plans={plans} onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'user' && (
        <AddUserModal orgId={modal.orgId} orgName={modal.orgName} maxUsers={modal.maxUsers} currentUsers={modal.currentUsers} onClose={() => setModal(null)} onSaved={() => { load(); setOrgUsers({}); setExpandedOrg(modal.orgId) }} />
      )}
      </div>
    </div>
  )
}

function OrgFormModal({ org, plans, onClose, onSaved }) {
  const isEdit = !!org
  const [form, setForm] = useState({
    name: org?.name || '',
    slug: org?.slug || '',
    plan: org?.plan || '',
    max_users: org?.max_users || 10,
    is_active: org?.is_active ?? true,
  })
  const [saving, setSaving] = useState(false)

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const autoSlug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    const payload = { ...form, slug: form.slug || autoSlug(form.name), plan: form.plan || null }
    if (isEdit) {
      await api.patch(`/organizations/${org.id}/`, payload)
    } else {
      await api.post('/organizations/', payload)
    }
    onSaved()
    onClose()
  }

  return (
    <Modal title={isEdit ? 'Editar empresa' : 'Nueva empresa'} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="modal-field">
            <label>Nombre</label>
            <input value={form.name} onChange={(e) => { handleChange('name', e.target.value); if (!isEdit) handleChange('slug', autoSlug(e.target.value)) }} placeholder="Nombre de la empresa" autoFocus required />
          </div>
          <div className="modal-field">
            <label>Slug</label>
            <input value={form.slug} onChange={(e) => handleChange('slug', e.target.value)} placeholder="mi-empresa" required />
          </div>
        </div>
        <div className="form-row">
          <div className="modal-field">
            <label>Plan</label>
            <select value={form.plan} onChange={(e) => handleChange('plan', e.target.value)}>
              <option value="">Sin plan</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.name} (máx {p.max_users} usuarios)</option>)}
            </select>
          </div>
          <div className="modal-field">
            <label>Máximo de usuarios</label>
            <input type="number" min="1" value={form.max_users} onChange={(e) => handleChange('max_users', Number(e.target.value))} />
          </div>
        </div>
        <div className="modal-field">
          <label className="checkbox-label">
            <input type="checkbox" checked={form.is_active} onChange={(e) => handleChange('is_active', e.target.checked)} />
            Empresa activa
          </label>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>{isEdit ? 'Guardar' : 'Crear empresa'}</button>
        </div>
      </form>
    </Modal>
  )
}

function AddUserModal({ orgId, orgName, maxUsers, currentUsers, onClose, onSaved }) {
  const [form, setForm] = useState({
    username: '', email: '', first_name: '', last_name: '',
    job_title: '', password: '', is_staff: false,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (currentUsers >= maxUsers) {
      setError(`Límite de ${maxUsers} usuarios alcanzado`)
      return
    }
    setSaving(true)
    try {
      await api.post(`/organizations/${orgId}/add_user/`, form)
      onSaved()
      onClose()
    } catch (err) {
      setError(err.response?.data?.error || 'Error al crear usuario')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Nuevo usuario para ${orgName}`} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}
        <div className="form-row">
          <div className="modal-field">
            <label>Nombre</label>
            <input value={form.first_name} onChange={(e) => handleChange('first_name', e.target.value)} autoFocus />
          </div>
          <div className="modal-field">
            <label>Apellido</label>
            <input value={form.last_name} onChange={(e) => handleChange('last_name', e.target.value)} />
          </div>
        </div>
        <div className="form-row">
          <div className="modal-field">
            <label>Usuario *</label>
            <input value={form.username} onChange={(e) => handleChange('username', e.target.value)} required />
          </div>
          <div className="modal-field">
            <label>Email *</label>
            <input type="email" value={form.email} onChange={(e) => handleChange('email', e.target.value)} required />
          </div>
        </div>
        <div className="form-row">
          <div className="modal-field">
            <label>Cargo</label>
            <input value={form.job_title} onChange={(e) => handleChange('job_title', e.target.value)} />
          </div>
          <div className="modal-field">
            <label>Contraseña *</label>
            <input type="password" value={form.password} onChange={(e) => handleChange('password', e.target.value)} required />
          </div>
        </div>
        <div className="modal-field">
          <label className="checkbox-label">
            <input type="checkbox" checked={form.is_staff} onChange={(e) => handleChange('is_staff', e.target.checked)} />
            Admin de empresa
          </label>
        </div>
        <p className="sa-quota-info">Usuarios: {currentUsers}/{maxUsers}</p>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving || currentUsers >= maxUsers}>Crear usuario</button>
        </div>
      </form>
    </Modal>
  )
}
