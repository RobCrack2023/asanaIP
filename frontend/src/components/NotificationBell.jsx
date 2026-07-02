import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CheckCheck } from 'lucide-react'
import api from '../api'
import './NotificationBell.css'

function timeAgo(dateStr) {
  const diffSec = Math.max(0, (Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diffSec < 60) return 'ahora'
  if (diffSec < 3600) return `hace ${Math.floor(diffSec / 60)} min`
  if (diffSec < 86400) return `hace ${Math.floor(diffSec / 3600)} h`
  return `hace ${Math.floor(diffSec / 86400)} d`
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const wrapRef = useRef(null)
  const navigate = useNavigate()

  const loadCount = () => {
    api.get('/notifications/unread_count/').then((res) => setUnreadCount(res.data.count))
  }

  useEffect(() => {
    loadCount()
    const interval = setInterval(loadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const toggleOpen = () => {
    const next = !open
    setOpen(next)
    if (next) {
      api.get('/notifications/').then((res) => setNotifications(res.data))
    }
  }

  const handleItemClick = async (n) => {
    if (!n.is_read) {
      api.post(`/notifications/${n.id}/mark_read/`)
      setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
      setUnreadCount((c) => Math.max(0, c - 1))
    }
    setOpen(false)
    if (n.project_id) {
      navigate(`/project/${n.project_id}${n.task ? `?task=${n.task}` : ''}`)
    }
  }

  const markAllRead = async (e) => {
    e.stopPropagation()
    await api.post('/notifications/mark_all_read/')
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    setUnreadCount(0)
  }

  return (
    <div className="notif-bell-wrap" ref={wrapRef}>
      <button className="notif-bell-btn" onClick={toggleOpen} title="Notificaciones">
        <Bell size={17} />
        {unreadCount > 0 && <span className="notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-dropdown-header">
            <span>Notificaciones</span>
            {unreadCount > 0 && (
              <button className="notif-mark-all" onClick={markAllRead}>
                <CheckCheck size={13} /> Marcar todas
              </button>
            )}
          </div>
          <div className="notif-list">
            {notifications.length === 0 ? (
              <div className="notif-empty">No tenés notificaciones</div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`notif-item ${n.is_read ? '' : 'unread'}`}
                  onClick={() => handleItemClick(n)}
                >
                  <div className="notif-dot" />
                  <div className="notif-body">
                    <span className="notif-message">{n.message}</span>
                    <span className="notif-time">{timeAgo(n.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
