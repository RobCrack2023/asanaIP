import { useState } from 'react'
import {
  DndContext, DragOverlay, closestCorners, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Plus, Check, Flag, Calendar, Trash2, User } from 'lucide-react'
import api from '../api'
import './KanbanView.css'

const PRIORITY_COLORS = { urgent: '#e8384f', high: '#fd9a00', medium: '#4573d2', low: '#9ca0a5' }

export default function KanbanView({ project, setProject, onSelectTask, users }) {
  const [activeTask, setActiveTask] = useState(null)
  const [addingToSection, setAddingToSection] = useState(null)
  const [newTitle, setNewTitle] = useState('')

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  const allTasks = project.sections.flatMap((s) =>
    s.tasks.filter((t) => !t.parent).map((t) => ({ ...t, sectionId: s.id }))
  )

  const findTask = (id) => allTasks.find((t) => t.id === Number(id))

  const handleDragStart = (event) => {
    setActiveTask(findTask(event.active.id))
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    setActiveTask(null)
    if (!over) return

    const task = findTask(active.id)
    if (!task) return

    let targetSectionId = null
    let targetIndex = 0

    const overTask = findTask(over.id)
    if (overTask) {
      targetSectionId = overTask.sectionId
      const sectionTasks = allTasks.filter((t) => t.sectionId === targetSectionId)
      targetIndex = sectionTasks.findIndex((t) => t.id === overTask.id)
    } else {
      targetSectionId = Number(over.id)
      const sectionTasks = allTasks.filter((t) => t.sectionId === targetSectionId)
      targetIndex = sectionTasks.length
    }

    if (task.sectionId === targetSectionId && task.order === targetIndex) return

    const sectionTasks = allTasks
      .filter((t) => t.sectionId === targetSectionId && t.id !== task.id)

    sectionTasks.splice(targetIndex, 0, task)

    const order = sectionTasks.map((t, i) => ({
      id: t.id,
      order: i,
      section: targetSectionId,
    }))

    setProject((prev) => ({
      ...prev,
      sections: prev.sections.map((s) => {
        if (s.id === targetSectionId) {
          return { ...s, tasks: sectionTasks.map((t, i) => ({ ...t, order: i, section: targetSectionId })) }
        }
        if (s.id === task.sectionId && s.id !== targetSectionId) {
          return { ...s, tasks: s.tasks.filter((t) => t.id !== task.id) }
        }
        return s
      }),
    }))

    await api.post('/tasks/reorder/', { order })
  }

  const addTask = async (sectionId) => {
    if (!newTitle.trim()) return
    const title = newTitle
    setNewTitle('')
    setAddingToSection(null)
    const sectionTasks = allTasks.filter((t) => t.sectionId === sectionId)
    const res = await api.post('/tasks/', {
      title,
      section: sectionId,
      order: sectionTasks.length,
    })
    setProject((prev) => ({
      ...prev,
      sections: prev.sections.map((s) =>
        s.id === sectionId ? { ...s, tasks: [...s.tasks, res.data] } : s
      ),
    }))
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="kanban-board">
        {project.sections.map((section) => {
          const sectionTasks = section.tasks.filter((t) => !t.parent)
          return (
            <KanbanColumn
              key={section.id}
              section={section}
              tasks={sectionTasks}
              onSelectTask={onSelectTask}
              onAddClick={() => { setAddingToSection(section.id); setNewTitle('') }}
              addingTask={addingToSection === section.id}
              newTitle={newTitle}
              onNewTitleChange={setNewTitle}
              onAddSubmit={() => addTask(section.id)}
              onAddCancel={() => setAddingToSection(null)}
            />
          )
        })}
      </div>

      <DragOverlay>
        {activeTask && <KanbanCard task={activeTask} isDragging />}
      </DragOverlay>
    </DndContext>
  )
}

function KanbanColumn({ section, tasks, onSelectTask, onAddClick, addingTask, newTitle, onNewTitleChange, onAddSubmit, onAddCancel }) {
  const taskIds = tasks.map((t) => t.id)

  return (
    <div className="kanban-column">
      <div className="kanban-column-header">
        <span className="kanban-column-title">{section.name}</span>
        <span className="kanban-column-count">{tasks.length}</span>
        <button className="kanban-column-add" onClick={onAddClick}>
          <Plus size={15} />
        </button>
      </div>

      <SortableContext items={taskIds} strategy={verticalListSortingStrategy} id={String(section.id)}>
        <div className="kanban-column-tasks" data-section-id={section.id}>
          {tasks.map((task) => (
            <SortableKanbanCard key={task.id} task={task} onClick={() => onSelectTask(task)} />
          ))}

          {addingTask && (
            <div className="kanban-card kanban-card-new">
              <input
                className="kanban-new-input"
                placeholder="Nombre de la tarea..."
                value={newTitle}
                onChange={(e) => onNewTitleChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onAddSubmit()
                  if (e.key === 'Escape') onAddCancel()
                }}
                onBlur={() => { if (newTitle.trim()) onAddSubmit(); else onAddCancel() }}
                autoFocus
              />
            </div>
          )}

          {tasks.length === 0 && !addingTask && (
            <div className="kanban-empty">Sin tareas</div>
          )}
        </div>
      </SortableContext>
    </div>
  )
}

function SortableKanbanCard({ task, onClick }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <KanbanCard task={task} onClick={onClick} />
    </div>
  )
}

function KanbanCard({ task, onClick, isDragging }) {
  return (
    <div className={`kanban-card ${isDragging ? 'dragging' : ''} ${task.status === 'completed' ? 'completed' : ''}`} onClick={onClick}>
      <div className="kanban-card-top">
        <span className={`kanban-card-title ${task.status === 'completed' ? 'done' : ''}`}>
          {task.title}
        </span>
      </div>

      <div className="kanban-card-meta">
        {(task.start_date || task.due_date) && (
          <span className="kanban-card-due">
            <Calendar size={11} />
            {task.start_date
              ? new Date(task.start_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short' })
              : ''}
            {task.start_date && task.due_date ? ' – ' : ''}
            {task.due_date
              ? new Date(task.due_date + 'T00:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short' })
              : ''}
          </span>
        )}
        <span className="kanban-card-priority" style={{ color: PRIORITY_COLORS[task.priority] }}>
          <Flag size={11} />
        </span>
        {task.assignee_name && (
          <span className="kanban-card-assignee" title={task.assignee_name}>
            {task.assignee_name[0]}
          </span>
        )}
      </div>

      {task.subtasks_count > 0 && (
        <div className="kanban-card-subtasks">
          {task.subtasks_count} subtarea{task.subtasks_count > 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}
