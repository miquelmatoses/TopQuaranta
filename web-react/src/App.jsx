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
import ProposarArtistaPage from './pages/ProposarArtistaPage'
import SolicitarGestioPage from './pages/SolicitarGestioPage'
import AdminRoute from './components/AdminRoute'
import StaffLayout from './components/StaffLayout'
import StaffDashboardPage from './pages/staff/StaffDashboardPage'
import PendentsPage from './pages/staff/PendentsPage'
import StaffArtistesPage from './pages/staff/StaffArtistesPage'
import ArtistaCrearPage from './pages/staff/ArtistaCrearPage'
import ArtistaEditPage from './pages/staff/ArtistaEditPage'
import StaffCanconsPage from './pages/staff/StaffCanconsPage'
import CancoEditPage from './pages/staff/CancoEditPage'
import AlbumEditPage from './pages/staff/AlbumEditPage'
import StaffRankingPage from './pages/staff/StaffRankingPage'
import PropostesPage from './pages/staff/PropostesPage'
import PropostaDetailPage from './pages/staff/PropostaDetailPage'
import SolicitudsPage from './pages/staff/SolicitudsPage'
import SenyalPage from './pages/staff/SenyalPage'
import HistorialPage from './pages/staff/HistorialPage'
import ConfiguracioPage from './pages/staff/ConfiguracioPage'
import AuditlogPage from './pages/staff/AuditlogPage'
import UsuarisPage from './pages/staff/UsuarisPage'
import UsuariDetailPage from './pages/staff/UsuariDetailPage'

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
        <Route path="/compte/artista/proposta" element={<ProposarArtistaPage />} />
        <Route path="/compte/artista/gestio" element={<SolicitarGestioPage />} />
        {/* Staff panel. All /staff/* routes sit under a shared
            StaffLayout (dark sidebar) and require `is_staff`. As we
            port each Django staff view we'll add a nested route. */}
        <Route
          path="/staff/*"
          element={
            <AdminRoute>
              <StaffLayout>
                <Routes>
                  <Route path="/" element={<StaffDashboardPage />} />
                  <Route path="/pendents" element={<PendentsPage />} />
                  <Route path="/artistes" element={<StaffArtistesPage />} />
                  <Route path="/artistes/crear" element={<ArtistaCrearPage />} />
                  <Route path="/artistes/:pk" element={<ArtistaEditPage />} />
                  <Route path="/cancons" element={<StaffCanconsPage />} />
                  <Route path="/cancons/:pk" element={<CancoEditPage />} />
                  <Route path="/albums/:pk" element={<AlbumEditPage />} />
                  <Route path="/ranking" element={<StaffRankingPage />} />
                  <Route path="/propostes" element={<PropostesPage />} />
                  <Route path="/propostes/:pk" element={<PropostaDetailPage />} />
                  <Route path="/solicituds" element={<SolicitudsPage />} />
                  <Route path="/senyal" element={<SenyalPage />} />
                  <Route path="/historial" element={<HistorialPage />} />
                  <Route path="/configuracio" element={<ConfiguracioPage />} />
                  <Route path="/auditlog" element={<AuditlogPage />} />
                  <Route path="/usuaris" element={<UsuarisPage />} />
                  <Route path="/usuaris/:pk" element={<UsuariDetailPage />} />
                </Routes>
              </StaffLayout>
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
