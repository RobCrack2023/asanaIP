import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderOpen, LayoutGrid, CheckCircle2, Clock, AlertCircle, Check, Flag, Calendar, Bell, CheckCheck, XCircle } from 'lucide-react'
import api from '../api'
import './HomePage.css'

const PRIORITY_COLORS = { urgent: '#e8384f', high: '#fd9a00', medium: '#4573d2', low: '#9ca0a5' }
const STATUS_CONFIG = {
  pending: { label: 'Pendiente', color: '#9ca0a5' },
  in_progress: { label: 'En progreso', color: '#4573d2' },
  completed: { label: 'Completada', color: '#5da283' },
}

export default function HomePage() {
  const [projects, setProjects] = useState([])
  const [areas, setAreas] = useState([])
  const [myTasks, setMyTasks] = useState([])
  const [pendingApprovals, setPendingApprovals] = useState([])
  const [taskFilter, setTaskFilter] = useState('pending')
  const navigate = useNavigate()

  const loadTasks = () => {
    api.get('/auth/me/').then((meRes) => {
      api.get(`/tasks/?assignee=${meRes.data.id}&parent=none`).then((res) => setMyTasks(res.data))
      api.get('/tasks/pending_assignments/').then((res) => setPendingApprovals(res.data))
    })
  }

  useEffect(() => {
    Promise.all([
      api.get('/projects/'),
      api.get('/areas/'),
    ]).then(([projRes, areasRes]) => {
      setProjects(projRes.data)
      setAreas(areasRes.data)
    })
    loadTasks()
  }, [])

  const filteredTasks = taskFilter === 'all'
    ? myTasks
    : myTasks.filter((t) => t.status === taskFilter)

  const pendingCount = myTasks.filter((t) => t.status === 'pending').length
  const inProgressCount = myTasks.filter((t) => t.status === 'in_progress').length
  const completedCount = myTasks.filter((t) => t.status === 'completed').length

  const toggleTask = async (task) => {
    const newStatus = task.status === 'completed' ? 'pending' : 'completed'
    await api.patch(`/tasks/${task.id}/`, { status: newStatus })
    loadTasks()
  }

  const acceptTask = async (taskId) => {
    await api.post(`/tasks/${taskId}/accept/`)
    loadTasks()
  }

  const rejectTask = async (taskId) => {
    await api.post(`/tasks/${taskId}/reject/`)
    loadTasks()
  }

  return (
    <div className="home-page">
      <div className="home-header">
        <h1>Inicio</h1>
        <p>Bienvenido a AsanaIP</p>
      </div>

      <div className="home-stats">
        <div className="stat-card">
          <FolderOpen size={24} />
          <div>
            <span className="stat-number">{projects.length}</span>
            <span className="stat-label">Proyectos</span>
          </div>
        </div>
        <div className="stat-card">
          <LayoutGrid size={24} />
          <div>
            <span className="stat-number">{areas.length}</span>
            <span className="stat-label">Áreas</span>
          </div>
        </div>
        <div className="stat-card accent">
          <AlertCircle size={24} />
          <div>
            <span className="stat-number">{pendingCount + inProgressCount}</span>
            <span className="stat-label">Tareas pendientes</span>
          </div>
        </div>
      </div>

      {pendingApprovals.length > 0 && (
        <div className="home-section">
          <div className="section-header-row">
            <h2><Bell size={16} /> Solicitudes de asignación</h2>
            <span className="pending-count">{pendingApprovals.length} pendiente{pendingApprovals.length > 1 ? 's' : ''}</span>
          </div>
          <div className="approvals-list">
            {pendingApprovals.map((task) => (
              <div key={task.id} className="approval-row">
                <div className="approval-info">
                  <span className="approval-title">{task.title}</span>
                  <span className="approval-from">
                    Asignada por <strong>{task.assigned_by_name}</strong>
                    {task.due_date && <> · Vence {new Date(task.due_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short' })}</>}
                  </span>
                </div>
                <div className="approval-actions">
                  <button className="approval-btn accept" onClick={() => acceptTask(task.id)} title="Aceptar">
                    <CheckCheck size={16} /> Aceptar
                  </button>
                  <button className="approval-btn reject" onClick={() => rejectTask(task.id)} title="Rechazar">
                    <XCircle size={16} /> Rechazar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="home-section">
        <div className="section-header-row">
          <h2>Mis tareas</h2>
          <div className="task-filters">
            <button className={`filter-btn ${taskFilter === 'pending' ? 'active' : ''}`} onClick={() => setTaskFilter('pending')}>
              <Clock size={13} /> Pendientes ({pendingCount})
            </button>
            <button className={`filter-btn ${taskFilter === 'in_progress' ? 'active' : ''}`} onClick={() => setTaskFilter('in_progress')}>
              <AlertCircle size={13} /> En progreso ({inProgressCount})
            </button>
            <button className={`filter-btn ${taskFilter === 'completed' ? 'active' : ''}`} onClick={() => setTaskFilter('completed')}>
              <CheckCircle2 size={13} /> Completadas ({completedCount})
            </button>
            <button className={`filter-btn ${taskFilter === 'all' ? 'active' : ''}`} onClick={() => setTaskFilter('all')}>
              Todas ({myTasks.length})
            </button>
          </div>
        </div>

        {filteredTasks.length === 0 ? (
          <div className="my-tasks-empty">
            {taskFilter === 'completed' ? 'No hay tareas completadas' : 'No tienes tareas asignadas'}
          </div>
        ) : (
          <div className="my-tasks-list">
            {filteredTasks.map((task) => (
              <div key={task.id} className={`my-task-row ${task.status === 'completed' ? 'completed' : ''}`}>
                <button
                  className={`my-task-check ${task.status === 'completed' ? 'checked' : ''}`}
                  onClick={() => toggleTask(task)}
                >
                  {task.status === 'completed' && <Check size={11} />}
                </button>
                <span className={`my-task-title ${task.status === 'completed' ? 'done' : ''}`}>{task.title}</span>
                {task.due_date && (
                  <span className="my-task-due">
                    <Calendar size={11} />
                    {new Date(task.due_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short' })}
                  </span>
                )}
                <span style={{ color: PRIORITY_COLORS[task.priority] }}>
                  <Flag size={12} />
                </span>
                <span className="my-task-status" style={{ background: STATUS_CONFIG[task.status].color }}>
                  {STATUS_CONFIG[task.status].label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="home-section">
        <h2>Proyectos recientes</h2>
        <div className="project-grid">
          {projects.map((project) => (
            <button
              key={project.id}
              className="project-card"
              onClick={() => navigate(`/project/${project.id}`)}
            >
              <div className="project-card-bar" style={{ background: project.color }} />
              <div className="project-card-content">
                <h3>{project.name}</h3>
                <span className="project-card-team">{project.team_name}</span>
                <span className="project-card-tasks">{project.tasks_count} tareas</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
