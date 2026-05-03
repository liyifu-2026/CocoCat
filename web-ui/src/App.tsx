import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { Layout } from "@/components/Layout"
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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/agents/:id" element={<AgentDetail />} />
          <Route path="/scenes" element={<Scenes />} />
          <Route path="/scenes/:id" element={<SceneDetail />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/knowledge/:kbId" element={<KnowledgeDetail />} />
          <Route path="/hiring" element={<Hiring />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/mailbox" element={<Mailbox />} />
          <Route path="/usage" element={<TokenUsage />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
