import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import {
  Plus, Check, ChevronDown, ChevronRight, Calendar, User, File,
  Flag, MoreHorizontal, Trash2, X, List, LayoutGrid, Repeat, Lock,
} from 'lucide-react'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, DragOverlay } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import api from '../api'
import KanbanView from './KanbanView'
import AssetsPanel from './AssetsPanel'
import './ProjectView.css'

const PRIORITY_CONFIG = {
  urgent: { label: 'Urgente', color: '#e8384f' },
  high: { label: 'Alta', color: '#fd9a00' },
  medium: { label: 'Media', color: '#4573d2' },
  low: { label: 'Baja', color: '#9ca0a5' },
}

const STATUS_CONFIG = {
  pending: { label: 'Pendiente', color: '#9ca0a5' },
  in_progress: { label: 'En progreso', color: '#4573d2' },
  completed: { label: 'Completada', color: '#5da283' },
}

export default function ProjectView() {
  const { projectId } = useParams()
  const [project, setProject] = useState(null)
  const [users, setUsers] = useState([])
  const [collapsedSections, setCollapsedSections] = useState({})
  const [addingTaskSection, setAddingTaskSection] = useState(null)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [addingSection, setAddingSection] = useState(false)
  const [newSectionName, setNewSectionName] = useState('')
  const [selectedTask, setSelectedTask] = useState(null)
  const [viewMode, setViewMode] = useState('list')
  const [dragActiveTask, setDragActiveTask] = useState(null)
  const [currentUser, setCurrentUser] = useState(null)
  const [showOnlyMine, setShowOnlyMine] = useState(false)
  const newTaskRef = useRef(null)
  const newSectionRef = useRef(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  const loadProject = () => {
    api.get(`/projects/${projectId}/`).then((res) => setProject(res.data))
  }

  useEffect(() => {
    loadProject()
    api.get('/users/').then((res) => setUsers(res.data))
    api.get('/auth/me/').then((res) => {
      setCurrentUser(res.data)
      if (!res.data.is_staff && !res.data.is_super_admin) {
        setShowOnlyMine(true)
      }
    })
  }, [projectId])

  const filterTasks = (tasks) => {
    if (!showOnlyMine || !currentUser) return tasks
    return tasks.filter((t) => t.assignee === currentUser.id)
  }

  const toggleSection = (sectionId) => {
    setCollapsedSections((prev) => ({ ...prev, [sectionId]: !prev[sectionId] }))
  }

  const addTask = async (sectionId) => {
    if (!newTaskTitle.trim()) return
    const title = newTaskTitle
    setNewTaskTitle('')
    setAddingTaskSection(null)
    const res = await api.post('/tasks/', {
      title,
      section: sectionId,
      order: project.sections.find((s) => s.id === sectionId)?.tasks.length || 0,
    })
    setProject((prev) => ({
      ...prev,
      sections: prev.sections.map((s) =>
        s.id === sectionId ? { ...s, tasks: [...s.tasks, res.data] } : s
      ),
    }))
    setSelectedTask(res.data)
  }

  const addSection = async () => {
    if (!newSectionName.trim()) return
    const name = newSectionName
    setNewSectionName('')
    setAddingSection(false)
    const res = await api.post('/sections/', {
      name,
      project: parseInt(projectId),
      order: project.sections.length,
    })
    setProject((prev) => ({
      ...prev,
      sections: [...prev.sections, { ...res.data, tasks: res.data.tasks || [] }],
    }))
  }

  const updateProjectTasks = (updater) => {
    setProject((prev) => ({
      ...prev,
      sections: prev.sections.map((s) => ({
        ...s,
        tasks: updater(s.tasks, s.id),
      })),
    }))
  }

  const toggleTaskStatus = async (task) => {
    const newStatus = task.status === 'completed' ? 'pending' : 'completed'
    updateProjectTasks((tasks) =>
      tasks.map((t) => t.id === task.id ? { ...t, status: newStatus } : t)
    )
    if (selectedTask?.id === task.id) {
      setSelectedTask((prev) => ({ ...prev, status: newStatus }))
    }
    await api.patch(`/tasks/${task.id}/`, { status: newStatus })
    if (task.recurrence_type && task.recurrence_type !== 'none' && newStatus === 'completed') {
      const res = await api.get(`/tasks/?section=${task.section}&parent=none`)
      setProject((prev) => ({
        ...prev,
        sections: prev.sections.map((s) =>
          s.id === task.section ? { ...s, tasks: res.data } : s
        ),
      }))
    }
  }

  const updateTask = async (taskId, data) => {
    const enriched = { ...data }
    if ('assignee' in data) {
      const user = users.find((u) => String(u.id) === String(data.assignee))
      enriched.assignee_name = user ? user.full_name : null
    }
    updateProjectTasks((tasks) =>
      tasks.map((t) => t.id === taskId ? { ...t, ...enriched } : t)
    )
    await api.patch(`/tasks/${taskId}/`, data)
  }

  const deleteTask = async (taskId) => {
    updateProjectTasks((tasks) => tasks.filter((t) => t.id !== taskId))
    if (selectedTask?.id === taskId) setSelectedTask(null)
    await api.delete(`/tasks/${taskId}/`)
  }

  const deleteSection = async (sectionId) => {
    setProject((prev) => ({
      ...prev,
      sections: prev.sections.filter((s) => s.id !== sectionId),
    }))
    await api.delete(`/sections/${sectionId}/`)
  }

  const handleListDragStart = (event) => {
    const allTasks = project.sections.flatMap((s) => s.tasks.filter((t) => !t.parent))
    setDragActiveTask(allTasks.find((t) => t.id === Number(event.active.id)) || null)
  }

  const handleListDragEnd = async (event) => {
    const { active, over } = event
    setDragActiveTask(null)
    if (!over || active.id === over.id) return

    const allTasks = project.sections.flatMap((s) =>
      s.tasks.filter((t) => !t.parent).map((t) => ({ ...t, _sectionId: s.id }))
    )
    const draggedTask = allTasks.find((t) => t.id === Number(active.id))
    const overTask = allTasks.find((t) => t.id === Number(over.id))
    if (!draggedTask || !overTask) return

    const targetSectionId = overTask._sectionId
    const sectionTasks = allTasks
      .filter((t) => t._sectionId === targetSectionId && t.id !== draggedTask.id)
    const overIndex = sectionTasks.findIndex((t) => t.id === overTask.id)
    sectionTasks.splice(overIndex, 0, draggedTask)

    const order = sectionTasks.map((t, i) => ({
      id: t.id, order: i, section: targetSectionId,
    }))

    setProject((prev) => ({
      ...prev,
      sections: prev.sections.map((s) => {
        if (s.id === targetSectionId) {
          return { ...s, tasks: sectionTasks.map((t, i) => ({ ...t, order: i, section: targetSectionId })) }
        }
        if (s.id === draggedTask._sectionId && s.id !== targetSectionId) {
          return { ...s, tasks: s.tasks.filter((t) => t.id !== draggedTask.id) }
        }
        return s
      }),
    }))

    await api.post('/tasks/reorder/', { order })
  }

  useEffect(() => {
    if (addingTaskSection && newTaskRef.current) newTaskRef.current.focus()
  }, [addingTaskSection])

  useEffect(() => {
    if (addingSection && newSectionRef.current) newSectionRef.current.focus()
  }, [addingSection])

  if (!project) return <div className="loading">Cargando proyecto...</div>

  const allTaskIds = project.sections.flatMap((s) =>
    s.tasks.filter((t) => !t.parent).map((t) => t.id)
  )

  return (
    <div className="project-view">
      <div className="project-header">
        <div className="project-title-row">
          <div className="project-color-dot" style={{ background: project.color }} />
          <h1>{project.name}</h1>
          <button className="add-task-header-btn" onClick={() => {
            if (viewMode === 'assets') setViewMode('list')
            const firstSection = project.sections[0]
            if (firstSection) { setAddingTaskSection(firstSection.id); setNewTaskTitle('') }
          }}>
            <Plus size={14} /> Nueva tarea
          </button>
          <div className="task-filter-toggle">
            <button className={`filter-toggle-btn ${showOnlyMine ? 'active' : ''}`} onClick={() => setShowOnlyMine(true)}>
              <User size={13} /> Mis tareas
            </button>
            <button className={`filter-toggle-btn ${!showOnlyMine ? 'active' : ''}`} onClick={() => setShowOnlyMine(false)}>
              Todas
            </button>
          </div>
          <div className="view-switcher">
            <button className={`view-btn ${viewMode === 'list' ? 'active' : ''}`} onClick={() => setViewMode('list')} title="Vista lista">
              <List size={16} />
            </button>
            <button className={`view-btn ${viewMode === 'kanban' ? 'active' : ''}`} onClick={() => setViewMode('kanban')} title="Vista tablero">
              <LayoutGrid size={16} />
            </button>
            <button className={`view-btn ${viewMode === 'assets' ? 'active' : ''}`} onClick={() => setViewMode('assets')} title="Assets">
              <File size={16} />
            </button>
          </div>
        </div>
        {project.description && <p className="project-description">{project.description}</p>}
      </div>

      {viewMode === 'assets' ? (
        <AssetsPanel projectId={parseInt(projectId)} />
      ) : viewMode === 'list' ? (
        <div className="project-content-wrapper">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleListDragStart}
            onDragEnd={handleListDragEnd}
          >
            <div className="task-list-container">
              <div className="list-header">
                <span className="col-title">Tarea</span>
                <span className="col-assignee"><User size={13} /></span>
                <span className="col-due">Fechas</span>
                <span className="col-priority"><Flag size={13} /></span>
                <span className="col-status">Estado</span>
              </div>

              {project.sections.map((section) => {
                const sectionTasks = filterTasks(section.tasks.filter((t) => !t.parent))
                return (
                  <div key={section.id} className="section-group">
                    <div className="section-header">
                      <button className="section-toggle" onClick={() => toggleSection(section.id)}>
                        {collapsedSections[section.id] ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                      </button>
                      <span className="section-name">{section.name}</span>
                      <span className="section-count">{sectionTasks.length}</span>
                      <button className="section-action" onClick={() => { setAddingTaskSection(section.id); setNewTaskTitle('') }}>
                        <Plus size={14} />
                      </button>
                      <button className="section-action danger" onClick={() => deleteSection(section.id)}>
                        <Trash2 size={13} />
                      </button>
                    </div>

                    {!collapsedSections[section.id] && (
                      <SortableContext items={sectionTasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                        <div className="section-tasks">
                          {sectionTasks.map((task) => (
                            <SortableTaskRow
                              key={task.id}
                              task={task}
                              users={users}
                              onToggle={() => toggleTaskStatus(task)}
                              onClick={() => setSelectedTask(task)}
                              onUpdate={(data) => updateTask(task.id, data)}
                              onDelete={() => deleteTask(task.id)}
                              isSelected={selectedTask?.id === task.id}
                            />
                          ))}

                          {addingTaskSection === section.id && (
                            <div className="task-row new-task-row">
                              <div className="task-checkbox" />
                              <input
                                ref={newTaskRef}
                                className="new-task-input"
                                placeholder="Escribe el nombre de la tarea..."
                                value={newTaskTitle}
                                onChange={(e) => setNewTaskTitle(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') addTask(section.id)
                                  if (e.key === 'Escape') setAddingTaskSection(null)
                                }}
                                onBlur={() => { if (newTaskTitle.trim()) addTask(section.id); else setAddingTaskSection(null) }}
                              />
                            </div>
                          )}
                        </div>
                      </SortableContext>
                    )}
                  </div>
                )
              })}

              {addingSection ? (
                <div className="new-section-row">
                  <input
                    ref={newSectionRef}
                    className="new-section-input"
                    placeholder="Nombre de la sección..."
                    value={newSectionName}
                    onChange={(e) => setNewSectionName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') addSection()
                      if (e.key === 'Escape') setAddingSection(false)
                    }}
                    onBlur={() => { if (newSectionName.trim()) addSection(); else setAddingSection(false) }}
                  />
                </div>
              ) : (
                <button className="add-section-btn" onClick={() => { setAddingSection(true); setNewSectionName('') }}>
                  <Plus size={14} />
                  Agregar sección
                </button>
              )}
            </div>

            <DragOverlay>
              {dragActiveTask && (
                <div className="task-row dragging-overlay">
                  <div className="task-checkbox" />
                  <span className="task-title">{dragActiveTask.title}</span>
                </div>
              )}
            </DragOverlay>
          </DndContext>
        </div>
      ) : (
        <KanbanView
          project={project}
          setProject={setProject}
          onSelectTask={setSelectedTask}
          users={users}
          filterTasks={filterTasks}
        />
      )}

      {selectedTask && (
        <div className="task-detail-overlay" onClick={(e) => { if (e.target === e.currentTarget) setSelectedTask(null) }}>
          <TaskDetail
            task={selectedTask}
            users={users}
            onClose={() => setSelectedTask(null)}
            onUpdate={(data) => {
              const enriched = { ...data }
              if ('assignee' in data) {
                const user = users.find((u) => String(u.id) === String(data.assignee))
                enriched.assignee_name = user ? user.full_name : null
              }
              updateTask(selectedTask.id, data)
              setSelectedTask((prev) => ({ ...prev, ...enriched }))
            }}
            onDelete={() => deleteTask(selectedTask.id)}
          />
        </div>
      )}
    </div>
  )
}

function SortableTaskRow(props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: props.task.id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <TaskRow {...props} />
    </div>
  )
}

function TaskRow({ task, users, onToggle, onClick, onUpdate, onDelete, isSelected }) {
  const priorityConf = PRIORITY_CONFIG[task.priority]
  const statusConf = STATUS_CONFIG[task.status]

  return (
    <div className={`task-row ${isSelected ? 'selected' : ''} ${task.status === 'completed' ? 'completed' : ''}`}>
      <button
        className={`task-checkbox ${task.status === 'completed' ? 'checked' : ''}`}
        onClick={(e) => { e.stopPropagation(); onToggle() }}
      >
        {task.status === 'completed' && <Check size={12} />}
      </button>

      <button className="task-title" onClick={onClick}>
        {task.title}
        {task.visibility === 'private' && <Lock size={12} className="private-icon" />}
        {task.recurrence_type && task.recurrence_type !== 'none' && (
          <Repeat size={12} className="recurrence-icon" />
        )}
      </button>

      <div className="col-assignee">
        {task.assignee_name && (
          <span className="assignee-avatar" title={task.assignee_name}>{task.assignee_name[0]}</span>
        )}
      </div>

      <div className="col-due">
        {(task.start_date || task.due_date) && (
          <span className="due-date">
            <Calendar size={12} />
            {task.start_date
              ? new Date(task.start_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short' })
              : ''}
            {task.start_date && task.due_date ? ' – ' : ''}
            {task.due_date
              ? new Date(task.due_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short' })
              : ''}
          </span>
        )}
      </div>

      <div className="col-priority">
        <span className="priority-badge" style={{ color: priorityConf.color }} title={priorityConf.label}>
          <Flag size={14} />
        </span>
      </div>

      <div className="col-status">
        <span className="status-badge" style={{ background: statusConf.color }}>
          {statusConf.label}
        </span>
      </div>

      <button className="task-delete" onClick={(e) => { e.stopPropagation(); onDelete() }}>
        <Trash2 size={13} />
      </button>
    </div>
  )
}

function TaskDetail({ task, users, onClose, onUpdate, onDelete }) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)
  const [subtasks, setSubtasks] = useState([])
  const [newSubtask, setNewSubtask] = useState('')
  const [addingSubtask, setAddingSubtask] = useState(false)
  const subtaskRef = useRef(null)

  useEffect(() => {
    setTitle(task.title)
    setDescription(task.description)
    api.get(`/tasks/${task.id}/subtasks/`).then((res) => setSubtasks(res.data))
  }, [task.id])

  useEffect(() => {
    if (addingSubtask && subtaskRef.current) subtaskRef.current.focus()
  }, [addingSubtask])

  const addSubtask = async () => {
    if (!newSubtask.trim()) return
    await api.post('/tasks/', {
      title: newSubtask,
      section: task.section,
      parent: task.id,
      order: subtasks.length,
    })
    const res = await api.get(`/tasks/${task.id}/subtasks/`)
    setSubtasks(res.data)
    setNewSubtask('')
  }

  const toggleSubtask = async (sub) => {
    const newStatus = sub.status === 'completed' ? 'pending' : 'completed'
    await api.patch(`/tasks/${sub.id}/`, { status: newStatus })
    const res = await api.get(`/tasks/${task.id}/subtasks/`)
    setSubtasks(res.data)
  }

  const deleteSubtask = async (subId) => {
    await api.delete(`/tasks/${subId}/`)
    setSubtasks((prev) => prev.filter((s) => s.id !== subId))
  }

  return (
    <div className="task-detail">
      <div className="task-detail-header">
        <button
          className={`task-checkbox ${task.status === 'completed' ? 'checked' : ''}`}
          onClick={() => onUpdate({ status: task.status === 'completed' ? 'pending' : 'completed' })}
        >
          {task.status === 'completed' && <Check size={12} />}
        </button>
        <span className="task-detail-status">{STATUS_CONFIG[task.status].label}</span>
        <div style={{ flex: 1 }} />
        <button className="icon-btn" onClick={onDelete}><Trash2 size={16} /></button>
        <button className="icon-btn" onClick={onClose}><X size={16} /></button>
      </div>

      <input
        className="task-detail-title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onBlur={() => { if (title !== task.title) onUpdate({ title }) }}
        onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur() }}
      />

      {task.assignment_status === 'pending_approval' && (
        <div className="assignment-pending-banner">
          <span>Pendiente de aprobación por {task.assignee_name}</span>
          {task.assigned_by_name && <span className="assigned-by">Asignada por {task.assigned_by_name}</span>}
        </div>
      )}
      {task.assignment_status === 'rejected' && (
        <div className="assignment-rejected-banner">
          <span>Asignación rechazada</span>
        </div>
      )}

      <div className="task-detail-fields">
        <div className="detail-field">
          <label>Responsable</label>
          <select
            value={task.assignee != null ? String(task.assignee) : ''}
            onChange={(e) => onUpdate({ assignee: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Sin asignar</option>
            {users.map((u) => (
              <option key={u.id} value={String(u.id)}>{u.full_name}</option>
            ))}
          </select>
        </div>

        <div className="detail-field">
          <label>Fecha inicio</label>
          <input
            type="date"
            value={task.start_date || ''}
            onChange={(e) => onUpdate({ start_date: e.target.value || null })}
          />
        </div>

        <div className="detail-field">
          <label>Fecha límite</label>
          <input
            type="date"
            value={task.due_date || ''}
            onChange={(e) => onUpdate({ due_date: e.target.value || null })}
          />
        </div>

        <div className="detail-field">
          <label>Prioridad</label>
          <select
            value={task.priority}
            onChange={(e) => onUpdate({ priority: e.target.value })}
          >
            {Object.entries(PRIORITY_CONFIG).map(([key, conf]) => (
              <option key={key} value={key}>{conf.label}</option>
            ))}
          </select>
        </div>

        <div className="detail-field">
          <label>Estado</label>
          <select
            value={task.status}
            onChange={(e) => onUpdate({ status: e.target.value })}
          >
            {Object.entries(STATUS_CONFIG).map(([key, conf]) => (
              <option key={key} value={key}>{conf.label}</option>
            ))}
          </select>
        </div>

        <div className="detail-field">
          <label>Visibilidad</label>
          <select
            value={task.visibility || 'public'}
            onChange={(e) => onUpdate({ visibility: e.target.value })}
          >
            <option value="public">Pública</option>
            <option value="private">Privada</option>
          </select>
        </div>
      </div>

      <RecurrenceSection task={task} onUpdate={onUpdate} />

      <div className="detail-field description-field">
        <label>Descripción</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() => { if (description !== task.description) onUpdate({ description }) }}
          placeholder="Agregar una descripción..."
          rows={3}
        />
      </div>

      <div className="subtasks-section">
        <div className="subtasks-header">
          <label>Subtareas</label>
          <button className="subtask-add-btn" onClick={() => setAddingSubtask(true)}>
            <Plus size={14} />
          </button>
        </div>

        {subtasks.map((sub) => (
          <div key={sub.id} className={`subtask-row ${sub.status === 'completed' ? 'completed' : ''}`}>
            <button
              className={`task-checkbox small ${sub.status === 'completed' ? 'checked' : ''}`}
              onClick={() => toggleSubtask(sub)}
            >
              {sub.status === 'completed' && <Check size={10} />}
            </button>
            <span className="subtask-title">{sub.title}</span>
            <button className="subtask-delete" onClick={() => deleteSubtask(sub.id)}>
              <Trash2 size={12} />
            </button>
          </div>
        ))}

        {addingSubtask && (
          <div className="subtask-row">
            <div className="task-checkbox small" />
            <input
              ref={subtaskRef}
              className="subtask-input"
              placeholder="Nombre de la subtarea..."
              value={newSubtask}
              onChange={(e) => setNewSubtask(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addSubtask()
                if (e.key === 'Escape') setAddingSubtask(false)
              }}
              onBlur={() => { if (newSubtask.trim()) addSubtask(); else setAddingSubtask(false) }}
            />
          </div>
        )}

        {!addingSubtask && subtasks.length === 0 && (
          <button className="subtask-empty" onClick={() => setAddingSubtask(true)}>
            <Plus size={12} /> Agregar subtarea
          </button>
        )}
      </div>
    </div>
  )
}

const WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function RecurrenceSection({ task, onUpdate }) {
  const recType = task.recurrence_type || 'none'

  const handleTypeChange = (type) => {
    const updates = { recurrence_type: type }
    if (type === 'none') {
      updates.recurrence_day = null
      updates.recurrence_end_date = null
    } else if (type === 'weekly') {
      updates.recurrence_day = task.recurrence_day ?? 0
    } else if (type === 'monthly') {
      updates.recurrence_day = task.recurrence_day ?? 1
    }
    onUpdate(updates)
  }

  return (
    <div className="recurrence-section">
      <div className="recurrence-header">
        <Repeat size={14} />
        <label>Repetición</label>
      </div>

      <div className="recurrence-fields">
        <select
          className="recurrence-select"
          value={recType}
          onChange={(e) => handleTypeChange(e.target.value)}
        >
          <option value="none">Sin repetición</option>
          <option value="weekly">Semanal</option>
          <option value="monthly">Mensual</option>
          <option value="yearly">Anual</option>
        </select>

        {recType === 'weekly' && (
          <select
            className="recurrence-select"
            value={task.recurrence_day ?? 0}
            onChange={(e) => onUpdate({ recurrence_day: Number(e.target.value) })}
          >
            {WEEKDAYS.map((day, i) => (
              <option key={i} value={i}>Cada {day}</option>
            ))}
          </select>
        )}

        {recType === 'monthly' && (
          <select
            className="recurrence-select"
            value={task.recurrence_day ?? 1}
            onChange={(e) => onUpdate({ recurrence_day: Number(e.target.value) })}
          >
            {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>Día {d} de cada mes</option>
            ))}
          </select>
        )}

        {recType === 'yearly' && task.due_date && (
          <span className="recurrence-info">
            Se repite cada año el {new Date(task.due_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'long' })}
          </span>
        )}

        {recType !== 'none' && (
          <div className="recurrence-end">
            <label>Hasta</label>
            <input
              type="date"
              value={task.recurrence_end_date || ''}
              onChange={(e) => onUpdate({ recurrence_end_date: e.target.value || null })}
            />
            {!task.recurrence_end_date && <span className="recurrence-hint">Indefinido</span>}
          </div>
        )}
      </div>
    </div>
  )
}
