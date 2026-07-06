import { useState, useEffect } from 'react'
import { UserPlus, Edit2, Trash2, X, Check, Shield, ShieldOff, Search } from 'lucide-react'
import api from '../api'
import Modal from '../components/Modal'
import './UsersPage.css'

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [teams, setTeams] = useState([])
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)

  const load = () => {
    Promise.all([
      api.get('/users/'),
      api.get('/teams/'),
    ]).then(([usersRes, teamsRes]) => {
      setUsers(usersRes.data)
      setTeams(teamsRes.data)
    })
  }

  useEffect(() => { load() }, [])

  const filtered = users.filter((u) => {
    const term = search.toLowerCase()
    return u.full_name.toLowerCase().includes(term)
      || u.username.toLowerCase().includes(term)
      || u.email.toLowerCase().includes(term)
      || u.job_title?.toLowerCase().includes(term)
  })

  const deleteUser = async (userId) => {
    if (!confirm('¿Estás seguro de eliminar este usuario?')) return
    await api.delete(`/users/${userId}/`)
    load()
  }

  return (
    <div className="users-page">
      <div className="users-header">
        <div>
          <h1>Usuarios</h1>
          <p>{users.length} usuarios registrados</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ type: 'create' })}>
          <UserPlus size={15} />
          Nuevo usuario
        </button>
      </div>

      <div className="users-toolbar">
        <div className="search-box">
          <Search size={15} />
          <input
            placeholder="Buscar por nombre, usuario, email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="users-table">
        <div className="users-table-header">
          <span className="ut-col-name">Usuario</span>
          <span className="ut-col-title">Cargo</span>
          <span className="ut-col-teams">Equipos</span>
          <span className="ut-col-status">Estado</span>
          <span className="ut-col-actions"></span>
        </div>

        {filtered.map((user) => (
          <div key={user.id} className={`users-table-row ${!user.is_active ? 'inactive' : ''}`}>
            <div className="ut-col-name">
              <div className="ut-avatar">{(user.first_name?.[0] || user.username[0]).toUpperCase()}</div>
              <div>
                <span className="ut-name">{user.full_name}</span>
                <span className="ut-username">@{user.username}</span>
              </div>
            </div>
            <span className="ut-col-title">{user.job_title || '—'}</span>
            <div className="ut-col-teams">
              {user.teams?.length > 0
                ? user.teams.map((t) => (
                    <span key={t.id} className="ut-team-badge">{t.name}</span>
                  ))
                : <span className="ut-no-team">Sin equipo</span>
              }
            </div>
            <div className="ut-col-status">
              {user.is_active
                ? <span className="ut-status-badge active">Activo</span>
                : <span className="ut-status-badge inactive">Inactivo</span>
              }
              {user.is_staff && <span className="ut-status-badge admin">Admin</span>}
              {user.is_sales && <span className="ut-status-badge sales">Ventas</span>}
            </div>
            <div className="ut-col-actions">
              <button className="ut-action-btn" title="Editar" onClick={() => setModal({ type: 'edit', user })}>
                <Edit2 size={14} />
              </button>
              <button className="ut-action-btn danger" title="Eliminar" onClick={() => deleteUser(user.id)}>
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="users-empty">No se encontraron usuarios</div>
        )}
      </div>

      {modal?.type === 'create' && (
        <UserFormModal teams={teams} onClose={() => setModal(null)} onSaved={load} />
      )}
      {modal?.type === 'edit' && (
        <UserFormModal user={modal.user} teams={teams} onClose={() => setModal(null)} onSaved={load} />
      )}
    </div>
  )
}

function UserFormModal({ user, teams, onClose, onSaved }) {
  const isEdit = !!user
  const [form, setForm] = useState({
    username: user?.username || '',
    email: user?.email || '',
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    job_title: user?.job_title || '',
    is_active: user?.is_active ?? true,
    is_staff: user?.is_staff ?? false,
    is_sales: user?.is_sales ?? false,
    password: '',
  })
  const [selectedTeams, setSelectedTeams] = useState(user?.teams?.map((t) => t.id) || [])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const toggleTeam = (teamId) => {
    setSelectedTeams((prev) =>
      prev.includes(teamId) ? prev.filter((id) => id !== teamId) : [...prev, teamId]
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.username.trim() || !form.email.trim()) {
      setError('Usuario y email son obligatorios')
      return
    }
    if (!isEdit && !form.password) {
      setError('La contraseña es obligatoria para nuevos usuarios')
      return
    }

    setSaving(true)
    setError('')

    try {
      const payload = { ...form }
      if (!payload.password) delete payload.password

      if (isEdit) {
        await api.patch(`/users/${user.id}/`, payload)
      } else {
        await api.post('/users/', payload)
      }

      const updatedUsers = (await api.get('/users/')).data
      const targetUser = updatedUsers.find((u) =>
        isEdit ? u.id === user.id : u.username === form.username
      )

      if (targetUser) {
        const currentTeamIds = targetUser.teams?.map((t) => t.id) || []
        for (const teamId of selectedTeams) {
          if (!currentTeamIds.includes(teamId)) {
            await api.post(`/teams/${teamId}/add_member/`, { user_id: targetUser.id })
          }
        }
        for (const teamId of currentTeamIds) {
          if (!selectedTeams.includes(teamId)) {
            await api.post(`/teams/${teamId}/remove_member/`, { user_id: targetUser.id })
          }
        }
      }

      onSaved()
      onClose()
    } catch (err) {
      setError(err.response?.data?.username?.[0] || err.response?.data?.email?.[0] || 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={isEdit ? 'Editar usuario' : 'Nuevo usuario'} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="form-row">
          <div className="modal-field">
            <label>Nombre</label>
            <input value={form.first_name} onChange={(e) => handleChange('first_name', e.target.value)} placeholder="Nombre" autoFocus />
          </div>
          <div className="modal-field">
            <label>Apellido</label>
            <input value={form.last_name} onChange={(e) => handleChange('last_name', e.target.value)} placeholder="Apellido" />
          </div>
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Usuario *</label>
            <input value={form.username} onChange={(e) => handleChange('username', e.target.value)} placeholder="nombre.usuario" required />
          </div>
          <div className="modal-field">
            <label>Email *</label>
            <input type="email" value={form.email} onChange={(e) => handleChange('email', e.target.value)} placeholder="correo@ejemplo.com" required />
          </div>
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label>Cargo</label>
            <input value={form.job_title} onChange={(e) => handleChange('job_title', e.target.value)} placeholder="Ej: Desarrollador..." />
          </div>
          <div className="modal-field">
            <label>{isEdit ? 'Nueva contraseña' : 'Contraseña *'}</label>
            <input type="password" value={form.password} onChange={(e) => handleChange('password', e.target.value)} placeholder={isEdit ? 'Dejar vacío para no cambiar' : 'Mínimo 6 caracteres'} />
          </div>
        </div>

        <div className="form-row">
          <div className="modal-field">
            <label className="checkbox-label">
              <input type="checkbox" checked={form.is_active} onChange={(e) => handleChange('is_active', e.target.checked)} />
              Usuario activo
            </label>
          </div>
          <div className="modal-field">
            <label className="checkbox-label">
              <input type="checkbox" checked={form.is_staff} onChange={(e) => handleChange('is_staff', e.target.checked)} />
              Administrador
            </label>
          </div>
          <div className="modal-field">
            <label className="checkbox-label">
              <input type="checkbox" checked={form.is_sales} onChange={(e) => handleChange('is_sales', e.target.checked)} />
              Ventas (acceso a CRM)
            </label>
          </div>
        </div>

        <div className="modal-field">
          <label>Equipos</label>
          <div className="team-selector">
            {teams.map((team) => (
              <button
                type="button"
                key={team.id}
                className={`team-chip ${selectedTeams.includes(team.id) ? 'selected' : ''}`}
                onClick={() => toggleTeam(team.id)}
              >
                {selectedTeams.includes(team.id) && <Check size={12} />}
                {team.name}
              </button>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando...' : isEdit ? 'Guardar cambios' : 'Crear usuario'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
