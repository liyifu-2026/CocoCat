import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { Layout } from "@/components/Layout"
import ErrorBoundary from "@/components/ErrorBoundary"
import Chat from "@/pages/Chat"
import SceneDetail from "@/pages/SceneDetail"
import Dashboard from "@/pages/Dashboard"
import Scenes from "@/pages/Scenes"
import Knowledge from "@/pages/Knowledge"
import KnowledgeDetail from "@/pages/KnowledgeDetail"
import SceneNew from "@/pages/SceneNew"

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ErrorBoundary><Chat /></ErrorBoundary>} />
          <Route path="/dashboard" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
          <Route path="/scenes" element={<ErrorBoundary><Scenes /></ErrorBoundary>} />
          <Route path="/scenes/:id" element={<ErrorBoundary><SceneDetail /></ErrorBoundary>} />
          <Route path="/scenes/new" element={<ErrorBoundary><SceneNew /></ErrorBoundary>} />

          <Route path="/knowledge" element={<ErrorBoundary><Knowledge /></ErrorBoundary>} />
          <Route path="/knowledge/:kb" element={<ErrorBoundary><KnowledgeDetail /></ErrorBoundary>} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
