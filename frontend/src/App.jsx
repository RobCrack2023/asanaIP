import { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import api from './api'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import ProjectView from './pages/ProjectView'
import HomePage from './pages/HomePage'
import UsersPage from './pages/UsersPage'
import AreaView from './pages/AreaView'
import SuperAdminPage from './pages/SuperAdminPage'
import ClientsPage from './pages/ClientsPage'
import OpportunitiesPage from './pages/OpportunitiesPage'
import OpportunityDetailPage from './pages/OpportunityDetailPage'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/auth/me/')
      .then((res) => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return null

  if (!user) {
    return <LoginPage onLogin={setUser} />
  }

  if (user.is_super_admin) {
    return <SuperAdminPage user={user} onLogout={() => { api.post('/auth/logout/'); setUser(null) }} />
  }

  return (
    <Layout user={user} onLogout={() => setUser(null)}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/area/:areaId" element={<AreaView />} />
        <Route path="/project/:projectId" element={<ProjectView />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/opportunities" element={<OpportunitiesPage />} />
        <Route path="/opportunities/:opportunityId" element={<OpportunityDetailPage />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Layout>
  )
}
