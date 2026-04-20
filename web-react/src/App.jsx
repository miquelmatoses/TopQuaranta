import { Component } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import TopPage from './pages/TopPage'
import ArtistesPage from './pages/ArtistesPage'
import ArtistaPage from './pages/ArtistaPage'
import AlbumPage from './pages/AlbumPage'
import CancoPage from './pages/CancoPage'
import MapaPage from './pages/MapaPage'
import AuthPage from './pages/AuthPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import ComptePage from './pages/ComptePage'
import ComptePerfilPage from './pages/ComptePerfilPage'
import AdminRoute from './components/AdminRoute'
import AdminDashboardPage from './pages/AdminDashboardPage'

/** Top-level error boundary — catches unexpected render errors and
 *  shows a minimal fallback with a reload button. */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen gap-4 px-6 text-center">
          <p className="text-gray-300 text-sm">Alguna cosa ha fallat. Recarrega la pàgina.</p>
          <button
            className="text-sm font-semibold text-tq-yellow underline"
            onClick={() => window.location.reload()}
          >
            Recarregar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function AppContent() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/top" element={<TopPage />} />
        <Route path="/artistes" element={<ArtistesPage />} />
        <Route path="/artista/:slug" element={<ArtistaPage />} />
        {/* Canonical flat routes (short, stable). */}
        <Route path="/album/:slug" element={<AlbumPage />} />
        <Route path="/canco/:slug" element={<CancoPage />} />
        {/* Nested SEO routes. React Router picks the most specific
            match; both shapes end up rendering the same page, which
            fetches by the leaf slug alone. */}
        <Route path="/artista/:artistaSlug/:albumSlug/:cancoSlug" element={<CancoPage />} />
        <Route path="/artista/:artistaSlug/:albumSlug" element={<AlbumPage />} />
        <Route path="/mapa" element={<MapaPage />} />
        <Route path="/compte/accedir" element={<AuthPage />} />
        <Route path="/compte/callback" element={<AuthCallbackPage />} />
        <Route path="/compte" element={<ComptePage />} />
        <Route path="/compte/perfil" element={<ComptePerfilPage />} />
        <Route
          path="/staff"
          element={
            <AdminRoute>
              <AdminDashboardPage />
            </AdminRoute>
          }
        />
      </Routes>
    </Layout>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      {/* `basename` is derived from Vite's BASE_URL (set in vite.config.js).
          During Sprint 1-3 this is `/beta/`; Sprint 4 flips it to `/`. */}
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
