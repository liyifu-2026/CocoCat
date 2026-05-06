import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { knowledgeApi } from "@/api/knowledge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { BookOpen, Upload, CheckCircle, Loader2 } from "lucide-react"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"
import ErrorState from "@/components/ErrorState"
import { useT } from "@/context/LanguageContext"
import { streamState, streamListeners } from "@/context/LiveUpdatesContext"

export default function Knowledge() {
  const t = useT()
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [kbInput, setKbInput] = useState("")
  const [taskUuid, setTaskUuid] = useState<string | null>(null)
  const [, forceRender] = useState(0)

  useEffect(() => {
    const handler = () => forceRender(n => n + 1)
    streamListeners.add(handler)
    return () => { streamListeners.delete(handler) }
  }, [])

  const taskProgress = taskUuid ? streamState.get(taskUuid) : null

  async function handleUpload() {
    if (!selectedFile || !kbInput.trim()) return
    setUploadOpen(false)
    const content = await selectedFile.text()
    const res = await knowledgeApi.upload(kbInput.trim(), selectedFile.name, content)
    setTaskUuid(res.task_uuid)
    refetch()
  }

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["knowledge"], queryFn: () => knowledgeApi.list() })

  if (isLoading) return <CardGridSkeleton count={3} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  if (!data?.kbs || data.kbs.length === 0) {
    return (
      <div className="p-6 space-y-6">
        <div className="stagger-item flex items-center justify-between" style={{animationDelay: "0s"}}>
          <h1 className="text-2xl font-bold">{t("knowledge.title")}</h1>
          <Button onClick={() => setUploadOpen(true)} variant="outline" size="sm">
            <Upload className="size-4 mr-2" /> Upload
          </Button>
        </div>
        <div className="stagger-item text-center py-20 text-muted-foreground" style={{animationDelay: "0.08s"}}>
          <BookOpen className="size-12 mx-auto mb-4 opacity-30" />
          <p>{t("knowledge.no_kbs")}</p>
        </div>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>Upload Knowledge</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">File</label>
                <Input type="file" onChange={e => setSelectedFile(e.target.files?.[0] ?? null)} />
              </div>
              <div>
                <label className="text-sm font-medium">Knowledge Base</label>
                <Input
                  placeholder="Select existing or type new name..."
                  value={kbInput}
                  onChange={e => setKbInput(e.target.value)}
                  list="kb-list"
                />
                <datalist id="kb-list">
                  {data?.kbs?.map((kb: any) => (
                    <option key={kb.id} value={kb.id} />
                  ))}
                </datalist>
              </div>
              <Button onClick={handleUpload} disabled={!selectedFile || !kbInput.trim()}>
                Upload & Process
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="stagger-item flex items-center justify-between" style={{animationDelay: "0s"}}>
        <h1 className="text-2xl font-bold">{t("knowledge.title")}</h1>
        <Button onClick={() => setUploadOpen(true)} variant="outline" size="sm">
          <Upload className="size-4 mr-2" /> Upload
        </Button>
      </div>

      {/* Progress Panel */}
      {taskProgress && (
        <div className="border rounded-lg p-4 bg-muted/30 stagger-item" style={{animationDelay: "0.04s"}}>
          <h3 className="font-semibold mb-2 text-sm">Processing: {taskProgress.task_uuid?.slice(0, 8)}</h3>
          <div className="space-y-1 text-sm">
            {taskProgress.event === "stream_progress" && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="size-3 animate-spin" />
                <span>{taskProgress.stream_event?.content || taskProgress.content || "Processing..."}</span>
              </div>
            )}
            {taskProgress.event === "task_completed" && (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="size-3" />
                <span>Complete</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="stagger-item grid gap-4 md:grid-cols-2 lg:grid-cols-3" style={{animationDelay: "0.08s"}}>
        {data.kbs.map(kb => (
          <Link key={kb.id} to={`/knowledge/${kb.id}`}>
            <Card className="hover:bg-accent/50 transition-colors cursor-pointer h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="size-4" /> {kb.id}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {t("knowledge.browse")}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Upload Dialog */}
      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Upload Knowledge</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">File</label>
              <Input type="file" onChange={e => setSelectedFile(e.target.files?.[0] ?? null)} />
            </div>
            <div>
              <label className="text-sm font-medium">Knowledge Base</label>
              <Input
                placeholder="Select existing or type new name..."
                value={kbInput}
                onChange={e => setKbInput(e.target.value)}
                list="kb-list"
              />
              <datalist id="kb-list">
                {data?.kbs?.map((kb: any) => (
                  <option key={kb.id} value={kb.id} />
                ))}
              </datalist>
            </div>
            <Button onClick={handleUpload} disabled={!selectedFile || !kbInput.trim()}>
              Upload & Process
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
