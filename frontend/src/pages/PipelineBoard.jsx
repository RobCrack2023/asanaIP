import { useState } from 'react'
import {
  DndContext, DragOverlay, closestCorners, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useDroppable } from '@dnd-kit/core'
import { Calendar, FileText, User } from 'lucide-react'
import { STAGES, formatMoney } from '../stages'
import { formatMonth } from '../dates'
import './PipelineBoard.css'

/**
 * The pipeline as a board: one column per stage, cards dragged between them.
 *
 * Moving into an open stage is a plain PATCH. Dropping on Ganada or Perdida
 * cannot be — those need a team or a reason — so the drop is reported to the
 * parent, which asks for the missing piece before anything is written.
 */
export default function PipelineBoard({ opportunities, onMove, onRequestOutcome, onOpen }) {
  const [activeId, setActiveId] = useState(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  const find = (id) => opportunities.find((o) => o.id === Number(id))
  const active = activeId ? find(activeId) : null

  const handleDragEnd = ({ active: dragged, over }) => {
    setActiveId(null)
    if (!over) return

    const opportunity = find(dragged.id)
    if (!opportunity) return

    // Dropping onto a card means "this column", not "this position" — the
    // board is not ordered, so only the target stage matters.
    const overOpportunity = find(over.id)
    const targetStage = overOpportunity ? overOpportunity.stage : String(over.id)

    if (!targetStage || targetStage === opportunity.stage) return

    if (targetStage === 'ganada' || targetStage === 'perdida') {
      onRequestOutcome(opportunity, targetStage)
      return
    }
    onMove(opportunity, targetStage)
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={({ active: dragged }) => setActiveId(dragged.id)}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActiveId(null)}
    >
      <div className="pipeline-board">
        {STAGES.map((stage) => (
          <PipelineColumn
            key={stage.value}
            stage={stage}
            opportunities={opportunities.filter((o) => o.stage === stage.value)}
            onOpen={onOpen}
          />
        ))}
      </div>

      <DragOverlay>
        {active && <PipelineCard opportunity={active} isDragging />}
      </DragOverlay>
    </DndContext>
  )
}

function PipelineColumn({ stage, opportunities, onOpen }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage.value })
  const ids = opportunities.map((o) => o.id)

  // Weighting by stage would be guesswork; this is the plain sum of what is
  // sitting in the column.
  const total = opportunities.reduce((sum, o) => sum + (Number(o.estimated_amount) || 0), 0)

  return (
    <div className="pipeline-column">
      <div className="pipeline-column-header" style={{ borderTopColor: stage.color }}>
        <div className="pipeline-column-title">
          <span>{stage.label}</span>
          <span className="pipeline-column-count">{opportunities.length}</span>
        </div>
        <span className="pipeline-column-total">{total ? formatMoney(total) : '—'}</span>
      </div>

      <SortableContext items={ids} strategy={verticalListSortingStrategy} id={stage.value}>
        <div ref={setNodeRef} className={`pipeline-column-cards ${isOver ? 'over' : ''}`}>
          {opportunities.map((opportunity) => (
            <SortablePipelineCard
              key={opportunity.id}
              opportunity={opportunity}
              onOpen={() => onOpen(opportunity)}
            />
          ))}
          {opportunities.length === 0 && <div className="pipeline-empty">Vacío</div>}
        </div>
      </SortableContext>
    </div>
  )
}

function SortablePipelineCard({ opportunity, onOpen }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: opportunity.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <PipelineCard opportunity={opportunity} onOpen={onOpen} />
    </div>
  )
}

function PipelineCard({ opportunity, onOpen, isDragging }) {
  const quotesCount = opportunity.quotes?.length ?? 0

  return (
    <div className={`pipeline-card ${isDragging ? 'dragging' : ''}`} onClick={onOpen}>
      <span className="pipeline-card-title">{opportunity.name}</span>
      <span className="pipeline-card-client">{opportunity.client_name}</span>

      <div className="pipeline-card-amount">{formatMoney(opportunity.estimated_amount)}</div>

      <div className="pipeline-card-meta">
        {opportunity.expected_close_date && (
          <span title="Cierre esperado">
            <Calendar size={11} /> {formatMonth(opportunity.expected_close_date)}
          </span>
        )}
        {quotesCount > 0 && (
          <span title={`${quotesCount} cotización(es)`}>
            <FileText size={11} /> {quotesCount}
          </span>
        )}
        {opportunity.owner_name && (
          <span className="pipeline-card-owner" title={opportunity.owner_name}>
            <User size={11} /> {opportunity.owner_name.split(' ')[0]}
          </span>
        )}
      </div>
    </div>
  )
}
