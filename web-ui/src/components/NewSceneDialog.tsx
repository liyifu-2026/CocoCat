import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useT } from "@/context/LanguageContext"
import { useDialogState, useDialogActions } from "@/context/DialogContext"
import { scenesApi } from "@/api/scenes"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"

export function NewSceneDialog() {
  const { newSceneOpen } = useDialogState()
  const { closeNewScene } = useDialogActions()
  const t = useT()
  const queryClient = useQueryClient()

  const [id, setId] = useState("")
  const [context, setContext] = useState("")

  const handleCreate = async () => {
    if (!id.trim()) return
    try {
      await scenesApi.create(id.trim(), context.trim() || undefined)
      queryClient.invalidateQueries({ queryKey: ["scenes"] })
      closeNewScene()
      setId("")
      setContext("")
    } catch {}
  }

  return (
    <Dialog open={newSceneOpen} onOpenChange={(open) => !open && closeNewScene()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("scene_dialog.title")}</DialogTitle>
          <DialogDescription>{t("scene_dialog.desc")}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("scene_dialog.id")}</Label>
            <Input value={id} onChange={e => setId(e.target.value)} placeholder={t("scene_dialog.id_placeholder")} />
          </div>
          <div className="space-y-2">
            <Label>{t("scene_dialog.context")}</Label>
            <Textarea value={context} onChange={e => setContext(e.target.value)}
              placeholder={t("scene_dialog.context_placeholder")}
              className="min-h-[100px]" />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={closeNewScene}>{t("common.cancel")}</Button>
            <Button size="sm" disabled={!id.trim()} onClick={handleCreate}>{t("common.create")}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
