import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { useT } from "@/context/LanguageContext"
import { scenesApi } from "@/api/scenes"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useDialogState, useDialogActions } from "@/context/DialogContext"

export function ImportSceneDialog() {
  const { importSceneOpen } = useDialogState()
  const { closeImportScene } = useDialogActions()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const t = useT()
  const [sceneId, setSceneId] = useState("")
  const [loading, setLoading] = useState(false)

  const handleCreate = async () => {
    if (!sceneId.trim()) return
    setLoading(true)
    try {
      await scenesApi.create(sceneId.trim())
      queryClient.invalidateQueries({ queryKey: ["scenes"] })
      closeImportScene()
      setSceneId("")
      navigate(`/scenes/${sceneId.trim()}`)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  return (
    <Dialog open={importSceneOpen} onOpenChange={(open) => !open && closeImportScene()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("import_create.title")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("import_create.id")}</Label>
            <Input value={sceneId} onChange={e => setSceneId(e.target.value)}
              placeholder={t("import_create.id_placeholder")} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={closeImportScene}>{t("common.cancel")}</Button>
            <Button size="sm" onClick={handleCreate} disabled={!sceneId.trim() || loading}>
              {loading ? t("import_create.creating") : t("common.create")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
