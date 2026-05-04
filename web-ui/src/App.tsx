import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { Layout } from "@/components/Layout"
import ProtectedRoute from "@/components/ProtectedRoute"
import ErrorBoundary from "@/components/ErrorBoundary"
import Login from "@/pages/Login"
import Dashboard from "@/pages/Dashboard"
import Agents from "@/pages/Agents"
import AgentDetail from "@/pages/AgentDetail"
import Scenes from "@/pages/Scenes"
import SceneDetail from "@/pages/SceneDetail"
import Settings from "@/pages/Settings"
import Knowledge from "@/pages/Knowledge"
import KnowledgeDetail from "@/pages/KnowledgeDetail"
import Mailbox from "@/pages/Mailbox"
import TokenUsage from "@/pages/TokenUsage"
import Hiring from "@/pages/Hiring"
import Chat from "@/pages/Chat"
import Schedule from "@/pages/Schedule"
import Collaboration from "@/pages/Collaboration"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
          <Route path="/agents" element={<ErrorBoundary><Agents /></ErrorBoundary>} />
          <Route path="/agents/:id" element={<ErrorBoundary><AgentDetail /></ErrorBoundary>} />
          <Route path="/scenes" element={<ErrorBoundary><Scenes /></ErrorBoundary>} />
          <Route path="/scenes/:id" element={<ErrorBoundary><SceneDetail /></ErrorBoundary>} />
          <Route path="/knowledge" element={<ErrorBoundary><Knowledge /></ErrorBoundary>} />
          <Route path="/knowledge/:kbId" element={<ErrorBoundary><KnowledgeDetail /></ErrorBoundary>} />
          <Route path="/hiring" element={<ErrorBoundary><Hiring /></ErrorBoundary>} />
          <Route path="/chat" element={<ErrorBoundary><Chat /></ErrorBoundary>} />
          <Route path="/schedule" element={<ErrorBoundary><Schedule /></ErrorBoundary>} />
          <Route path="/collaboration" element={<ErrorBoundary><Collaboration /></ErrorBoundary>} />
          <Route path="/mailbox" element={<ErrorBoundary><Mailbox /></ErrorBoundary>} />
          <Route path="/usage" element={<ErrorBoundary><TokenUsage /></ErrorBoundary>} />
          <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
