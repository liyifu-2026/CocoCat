import { useEffect, useRef, useState } from "react"

interface MermaidBlockProps {
  code: string
}

export function MermaidBlock({ code }: MermaidBlockProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!ref.current || error) return
    let cancelled = false

    const load = async () => {
      try {
        const mermaid = await import("mermaid")
        if (!cancelled) {
          const api = mermaid.default ?? mermaid
          api.run({ nodes: [ref.current!] })
        }
      } catch {
        if (!cancelled) setError(true)
      }
    }
    load()

    return () => { cancelled = true }
  }, [code, error])

  if (error) {
    return (
      <pre className="rounded-md bg-muted p-3 text-sm overflow-x-auto">
        <code>{code}</code>
      </pre>
    )
  }

  return (
    <div className="my-2 flex justify-center bg-muted/20 rounded-xl p-3 overflow-x-auto">
      <div ref={ref} className="mermaid">
        {code}
      </div>
    </div>
  )
}
