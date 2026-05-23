import { X } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { ReactNode } from "react"

interface Props {
  filename: string
  content: string
  fileType: string
  onClose: () => void
}

export default function FilePreviewOverlay({ filename, content, fileType, onClose }: Props) {
  const ext = fileType.toLowerCase()

  const renderContent = (): ReactNode => {
    if (["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext)) {
      return (
        <div className="flex items-center justify-center h-full">
          <img src={content} alt={filename} className="max-w-full max-h-full object-contain rounded-lg" />
        </div>
      )
    }

    if (ext === "pdf") {
      return (
        <iframe src={content} className="w-full h-full rounded-lg" title={filename} />
      )
    }

    if (["py", "ts", "tsx", "js", "jsx", "json", "yaml", "yml", "css", "html", "sh", "bash"].includes(ext)) {
      return (
        <pre className="bg-muted rounded-lg p-4 overflow-auto text-xs font-mono h-full">
          <code>{content}</code>
        </pre>
      )
    }

    return (
      <div className="markdown-content text-sm overflow-auto h-full">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    )
  }

  return (
    <div className="absolute inset-0 z-40 bg-background flex flex-col animate-view-enter">
      <div className="flex items-center gap-3 px-5 py-3 border-b border-border shrink-0">
        <button onClick={onClose} className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground transition-colors">
          <X className="size-3.5" />
          Back to chat
        </button>
        <span className="text-[11px] font-medium text-foreground truncate">{filename}</span>
        <span className="text-[9px] text-muted-foreground/50 ml-auto">{fileType}</span>
      </div>
      <div className="flex-1 overflow-hidden p-4">
        {renderContent()}
      </div>
    </div>
  )
}
