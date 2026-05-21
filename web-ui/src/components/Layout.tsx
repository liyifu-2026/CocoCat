import { useState } from "react"
import { Outlet } from "react-router-dom"
import LeftNav from "./LeftNav"
import OpDisplay from "./OpDisplay"
import ChatPanel from "./chat/ChatPanel"

export default function Layout() {
  const [activeNav, setActiveNav] = useState("chat")

  return (
    <div className="flex h-screen relative">
      <div className="bg-glow-blue" />
      <div className="bg-glow-amber" />

      <LeftNav active={activeNav} onNavigate={setActiveNav} />

      {activeNav === "chat" ? (
        <>
          <OpDisplay activeNav={activeNav} />
          <ChatPanel />
        </>
      ) : (
        <OpDisplay activeNav={activeNav} />
      )}

      <Outlet />
    </div>
  )
}
