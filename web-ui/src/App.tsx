import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { Layout } from "@/components/Layout"
import ErrorBoundary from "@/components/ErrorBoundary"
import Chat from "@/pages/Chat"
import SceneDetail from "@/pages/SceneDetail"
import Dashboard from "@/pages/Dashboard"
import Agents from "@/pages/Agents"
import Scenes from "@/pages/Scenes"
import Knowledge from "@/pages/Knowledge"
import KnowledgeDetail from "@/pages/KnowledgeDetail"
import { KbChatProvider } from "@/lib/KbChatContext"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ErrorBoundary><Chat /></ErrorBoundary>} />
          <Route path="/dashboard" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
          <Route path="/agents" element={<ErrorBoundary><Agents /></ErrorBoundary>} />
          <Route path="/scenes" element={<ErrorBoundary><Scenes /></ErrorBoundary>} />
          <Route path="/scenes/:id" element={<ErrorBoundary><SceneDetail /></ErrorBoundary>} />
          <Route path="/knowledge" element={<ErrorBoundary><KbChatProvider><Knowledge /></KbChatProvider></ErrorBoundary>} />
          <Route path="/knowledge/:kb" element={<ErrorBoundary><KbChatProvider><KnowledgeDetail /></KbChatProvider></ErrorBoundary>} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
