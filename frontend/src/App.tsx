import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import Upload from './pages/Upload'
import Recorrencias from './pages/Recorrencias'
import Perfil from './pages/Perfil'
import Onboarding from './pages/Onboarding'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transacoes" element={<Transactions />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/recorrencias" element={<Recorrencias />} />
          <Route path="/perfil" element={<Perfil />} />
          <Route path="/inicio" element={<Onboarding />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
