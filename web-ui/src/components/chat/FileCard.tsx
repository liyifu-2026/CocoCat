import { FileText, FileImage, FileCode, File } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

interface Props {
  filename: string
  fileType: string
  fileUrl?: string
  onClick?: () => void
}

const typeIcons: Record<string, ReactNode> = {
  md: <FileText className="size-4 text-blue-400" />,
  pdf: <FileText className="size-4 text-red-400" />,
  png: <FileImage className="size-4 text-green-400" />,
  jpg: <FileImage className="size-4 text-green-400" />,
  jpeg: <FileImage className="size-4 text-green-400" />,
  svg: <FileImage className="size-4 text-green-400" />,
  gif: <FileImage className="size-4 text-green-400" />,
  py: <FileCode className="size-4 text-yellow-400" />,
  ts: <FileCode className="size-4 text-blue-400" />,
  tsx: <FileCode className="size-4 text-blue-400" />,
  js: <FileCode className="size-4 text-yellow-400" />,
  jsx: <FileCode className="size-4 text-blue-400" />,
  json: <FileCode className="size-4 text-orange-400" />,
  yaml: <FileCode className="size-4 text-purple-400" />,
  yml: <FileCode className="size-4 text-purple-400" />,
  css: <FileCode className="size-4 text-pink-400" />,
}

export default function FileCard({ filename, fileType, onClick }: Props) {
  const ext = filename.split(".").pop()?.toLowerCase() || ""
  const icon = typeIcons[ext] || <File className="size-4 text-muted-foreground" />

  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 bg-card border border-border rounded-xl px-3 py-2.5 cursor-pointer hover:border-primary/30 hover:shadow-sm transition-all group",
        "max-w-[260px]"
      )}
    >
      <div className="shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-medium text-foreground truncate">{filename}</p>
        <p className="text-[8px] text-muted-foreground">{fileType}</p>
      </div>
      <span className="text-[8px] px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
        Preview
      </span>
    </div>
  )
}
