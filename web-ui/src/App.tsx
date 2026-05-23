import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import Layout from "@/components/Layout"
import Login from "@/pages/Login"
import ChatPage from "@/pages/ChatPage"
import BookshelfPage from "@/pages/BookshelfPage"
import ScenesPage from "@/pages/ScenesPage"
import SettingsPage from "@/pages/SettingsPage"
import MemoryPage from "@/pages/MemoryPage"

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route index element={<Navigate to="chat" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="chat/:sessionId" element={<ChatPage />} />
          <Route path="knowledge" element={<BookshelfPage />} />
          <Route path="knowledge/:kbName" element={<BookshelfPage />} />
          <Route path="knowledge/:kbName/:pageType/:pageName" element={<BookshelfPage />} />
          <Route path="scenes" element={<ScenesPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="settings/:tab" element={<SettingsPage />} />
          <Route path="memory" element={<MemoryPage />} />
          <Route path="*" element={<Navigate to="chat" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
