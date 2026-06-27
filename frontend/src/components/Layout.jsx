import Sidebar from './Sidebar'
import './Layout.css'

export default function Layout({ user, onLogout, children }) {
  return (
    <div className="layout">
      <Sidebar user={user} onLogout={onLogout} />
      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
