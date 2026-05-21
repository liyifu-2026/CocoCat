import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import ErrorBoundary from "@/components/ErrorBoundary"
import Layout from "@/components/Layout"
import Login from "@/pages/Login"

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/*" element={<ErrorBoundary><div /></ErrorBoundary>} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
