import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Home, ChevronDown, ChevronRight, Plus, Users, LogOut, UserCog } from 'lucide-react'
import api from '../api'
import Modal from './Modal'
import './Sidebar.css'

const COLORS = ['#4573D2', '#7C3AED', '#E8384F', '#FD9A00', '#5DA283', '#EA4E9D', '#EEC300', '#4ECBC4']

export default function Sidebar({ user, onLogout }) {
  const [areas, setAreas] = useState([])
  const [teams, setTeams] = useState([])
  const [projects, setProjects] = useState([])
  const [expandedAreas, setExpandedAreas] = useState({})
  const [expandedTeams, setExpandedTeams] = useState({})
  const [modal, setModal] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()

  const reload = () => {
    Promise.all([
      api.get('/areas/'),
      api.get('/teams/'),
      api.get('/projects/'),
    ]).then(([areasRes, teamsRes, projectsRes]) => {
      setAreas(areasRes.data)
      setTeams(teamsRes.data)
      setProjects(projectsRes.data)
      setExpandedAreas((prev) => {
        const next = { ...prev }
        areasRes.data.forEach((a) => { if (!(a.id in next)) next[a.id] = true })
        return next
      })
      setExpandedTeams((prev) => {
        const next = { ...prev }
        teamsRes.data.forEach((t) => { if (!(t.id in next)) next[t.id] = true })
        return next
      })
    })
  }

  useEffect(() => { reload() }, [])

  const toggleArea = (id) => setExpandedAreas((prev) => ({ ...prev, [id]: !prev[id] }))
  const toggleTeam = (id) => setExpandedTeams((prev) => ({ ...prev, [id]: !prev[id] }))
  const getTeamsByArea = (areaId) => teams.filter((t) => t.area === areaId)
  const getProjectsByTeam = (teamId) => projects.filter((p) => p.team === teamId)
  const currentProjectId = location.pathname.match(/\/project\/(\d+)/)?.[1]

  const handleLogout = () => api.post('/auth/logout/').then(() => onLogout())

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-icon">IP</div>
          <span className="logo-text">AsanaIP</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <button className={`nav-item ${location.pathname === '/' ? 'active' : ''}`} onClick={() => navigate('/')}>
          <Home size={16} />
          <span>Inicio</span>
        </button>

        <button className={`nav-item ${location.pathname === '/users' ? 'active' : ''}`} onClick={() => navigate('/users')}>
          <UserCog size={16} />
          <span>Usuarios</span>
        </button>

        <div className="nav-section-label">
          <span>Organización</span>
          <button className="nav-section-add" onClick={() => setModal({ type: 'area' })} title="Nueva área">
            <Plus size={13} />
          </button>
        </div>

        {areas.map((area) => (
          <div key={area.id} className="nav-group">
            <div className={`nav-item nav-area ${location.pathname === `/area/${area.id}` ? 'active' : ''}`}>
              <button className="nav-chevron" onClick={() => toggleArea(area.id)}>
                {expandedAreas[area.id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
              <div className="area-dot" style={{ background: area.color }} />
              <span className="nav-area-link" onClick={() => navigate(`/area/${area.id}`)}>{area.name}</span>
              <button className="nav-inline-add" onClick={() => setModal({ type: 'team', areaId: area.id })} title="Nuevo equipo">
                <Plus size={12} />
              </button>
            </div>

            {expandedAreas[area.id] && getTeamsByArea(area.id).map((team) => (
              <div key={team.id} className="nav-team-group">
                <div className="nav-item nav-team" onClick={() => toggleTeam(team.id)}>
                  {expandedTeams[team.id] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  <Users size={14} />
                  <span>{team.name}</span>
                  <span className="nav-badge">{team.members_count}</span>
                  <button className="nav-inline-add" onClick={(e) => { e.stopPropagation(); setModal({ type: 'project', teamId: team.id }) }} title="Nuevo proyecto">
                    <Plus size={12} />
                  </button>
                </div>

                {expandedTeams[team.id] && getProjectsByTeam(team.id).map((project) => (
                  <button
                    key={project.id}
                    className={`nav-item nav-project ${currentProjectId === String(project.id) ? 'active' : ''}`}
                    onClick={() => navigate(`/project/${project.id}`)}
                  >
                    <div className="project-dot" style={{ background: project.color }} />
                    <span>{project.name}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">
            {user.first_name?.[0] || user.username[0]}
          </div>
          <span className="user-name">{user.full_name}</span>
        </div>
        <button className="logout-btn" onClick={handleLogout} title="Cerrar sesión">
          <LogOut size={16} />
        </button>
      </div>

      {modal?.type === 'area' && (
        <CreateAreaModal onClose={() => setModal(null)} onCreated={reload} />
      )}
      {modal?.type === 'team' && (
        <CreateTeamModal areaId={modal.areaId} areas={areas} onClose={() => setModal(null)} onCreated={reload} />
      )}
      {modal?.type === 'project' && (
        <CreateProjectModal teamId={modal.teamId} teams={teams} user={user} onClose={() => setModal(null)} onCreated={(p) => { reload(); navigate(`/project/${p.id}`) }} />
      )}
    </aside>
  )
}

function CreateAreaModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [color, setColor] = useState(COLORS[0])
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    await api.post('/areas/', { name, color })
    onCreated()
    onClose()
  }

  return (
    <Modal title="Nueva área" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="modal-field">
          <label>Nombre del área</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Tecnología, Marketing..." autoFocus />
        </div>
        <div className="modal-field">
          <label>Color</label>
          <div className="color-options">
            {COLORS.map((c) => (
              <button type="button" key={c} className={`color-option ${color === c ? 'selected' : ''}`} style={{ background: c }} onClick={() => setColor(c)} />
            ))}
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={!name.trim() || saving}>Crear área</button>
        </div>
      </form>
    </Modal>
  )
}

function CreateTeamModal({ areaId, areas, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [area, setArea] = useState(areaId)
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    await api.post('/teams/', { name, area })
    onCreated()
    onClose()
  }

  return (
    <Modal title="Nuevo equipo" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="modal-field">
          <label>Nombre del equipo</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Desarrollo Backend..." autoFocus />
        </div>
        <div className="modal-field">
          <label>Área</label>
          <select value={area} onChange={(e) => setArea(Number(e.target.value))}>
            {areas.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={!name.trim() || saving}>Crear equipo</button>
        </div>
      </form>
    </Modal>
  )
}

function CreateProjectModal({ teamId, teams, user, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [team, setTeam] = useState(teamId)
  const [color, setColor] = useState(COLORS[0])
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    const res = await api.post('/projects/', { name, team, color, owner: user.id })
    onCreated(res.data)
    onClose()
  }

  return (
    <Modal title="Nuevo proyecto" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div className="modal-field">
          <label>Nombre del proyecto</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Rediseño Web..." autoFocus />
        </div>
        <div className="modal-field">
          <label>Equipo</label>
          <select value={team} onChange={(e) => setTeam(Number(e.target.value))}>
            {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="modal-field">
          <label>Color</label>
          <div className="color-options">
            {COLORS.map((c) => (
              <button type="button" key={c} className={`color-option ${color === c ? 'selected' : ''}`} style={{ background: c }} onClick={() => setColor(c)} />
            ))}
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={!name.trim() || saving}>Crear proyecto</button>
        </div>
      </form>
    </Modal>
  )
}
