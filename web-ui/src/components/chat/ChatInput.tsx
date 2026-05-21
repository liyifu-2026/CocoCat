import { useState, useRef, useCallback } from "react"
import { Send, Plus, Loader2 } from "lucide-react"
import { useMode } from "@/context/ModeContext"

interface ChatInputProps {
  onSend: (text: string) => void
  streaming: boolean
}

export default function ChatInput({ onSend, streaming }: ChatInputProps) {
  const [input, setInput] = useState("")
  const { currentMode, modes, setMode } = useMode()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || streaming) return
    setInput("")
    onSend(text)
  }, [input, streaming, onSend])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    const cmd = value.match(/^\/mode\s+(\S+)/i)
    if (cmd?.[1] && modes.some(m => m.id === cmd[1].toLowerCase())) {
      setMode(cmd[1].toLowerCase())
      setInput("")
      return
    }
    setInput(value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="p-3 border-t border-border">
      <div className="flex items-center gap-2 bg-input border border-border rounded-xl px-3 py-2 focus-within:border-primary/30 transition-colors">
        <button className="w-7 h-7 flex items-center justify-center text-muted-foreground hover:text-foreground rounded-lg transition-colors">
          <Plus className="size-4" />
        </button>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Aa"
          rows={1}
          disabled={streaming}
          className="flex-1 bg-transparent border-none outline-none resize-none text-xs text-foreground placeholder:text-muted-foreground/40 font-sans"
          onInput={(e) => {
            const el = e.currentTarget
            el.style.height = "auto"
            el.style.height = Math.min(el.scrollHeight, 120) + "px"
          }}
        />
        <button
          onClick={handleSend}
          disabled={streaming || !input.trim()}
          className="w-7 h-7 flex items-center justify-center bg-primary/15 text-primary rounded-lg hover:bg-primary/25 disabled:opacity-30 transition-colors"
        >
          {streaming ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
        </button>
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[9px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">
          {currentMode}
        </span>
        <span className="text-[8px] text-muted-foreground/50">Shift+Enter to break</span>
      </div>
    </div>
  )
}
