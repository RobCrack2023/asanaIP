import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Users, FolderOpen, ChevronRight } from 'lucide-react'
import api from '../api'
import './AreaView.css'

export default function AreaView() {
  const { areaId } = useParams()
  const [area, setArea] = useState(null)
  const [teams, setTeams] = useState([])
  const [projects, setProjects] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    api.get(`/areas/${areaId}/`).then((res) => setArea(res.data))
    api.get(`/teams/?area=${areaId}`).then((res) => setTeams(res.data))
    api.get('/projects/').then((res) => {
      setProjects(res.data)
    })
  }, [areaId])

  if (!area) return null

  const getProjectsByTeam = (teamId) => projects.filter((p) => p.team === teamId)

  return (
    <div className="area-view">
      <div className="area-header">
        <div className="area-color-bar" style={{ background: area.color }} />
        <div className="area-header-content">
          <h1>{area.name}</h1>
          {area.description && <p>{area.description}</p>}
          <div className="area-meta">
            <span><Users size={14} /> {teams.length} equipo{teams.length !== 1 ? 's' : ''}</span>
            <span><FolderOpen size={14} /> {projects.filter((p) => teams.some((t) => t.id === p.team)).length} proyectos</span>
          </div>
        </div>
      </div>

      <div className="area-teams">
        {teams.map((team) => {
          const teamProjects = getProjectsByTeam(team.id)
          return (
            <div key={team.id} className="area-team-card">
              <div className="area-team-header">
                <Users size={18} />
                <div>
                  <h2>{team.name}</h2>
                  {team.description && <p className="area-team-desc">{team.description}</p>}
                </div>
                <span className="area-team-members">{team.members_count} miembros</span>
              </div>

              {team.members?.length > 0 && (
                <div className="area-team-avatars">
                  {team.members.map((m) => (
                    <span key={m.id} className="area-avatar" title={m.full_name}>
                      {(m.first_name?.[0] || m.username[0]).toUpperCase()}
                    </span>
                  ))}
                </div>
              )}

              {teamProjects.length > 0 ? (
                <div className="area-projects-grid">
                  {teamProjects.map((project) => (
                    <button
                      key={project.id}
                      className="area-project-card"
                      onClick={() => navigate(`/project/${project.id}`)}
                    >
                      <div className="area-project-dot" style={{ background: project.color }} />
                      <div className="area-project-info">
                        <span className="area-project-name">{project.name}</span>
                        <span className="area-project-tasks">{project.tasks_count} tareas</span>
                      </div>
                      <ChevronRight size={16} className="area-project-arrow" />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="area-no-projects">Sin proyectos</div>
              )}
            </div>
          )
        })}

        {teams.length === 0 && (
          <div className="area-empty">Esta área no tiene equipos aún</div>
        )}
      </div>
    </div>
  )
}
