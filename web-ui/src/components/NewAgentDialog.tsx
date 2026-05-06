import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useT } from "@/context/LanguageContext"
import { useDialogState, useDialogActions } from "@/context/DialogContext"
import { api } from "@/api/client"
import { scenesApi } from "@/api/scenes"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function NewAgentDialog() {
  const { newAgentOpen } = useDialogState()
  const { closeNewAgent } = useDialogActions()
  const t = useT()
  const queryClient = useQueryClient()

  const [name, setName] = useState("")
  const [scene, setScene] = useState("default")
  const [role, setRole] = useState("")

  const { data: scenesData } = useQuery({
    queryKey: ["scenes"],
    queryFn: () => scenesApi.list(),
    enabled: newAgentOpen,
    staleTime: 60000,
  })

  const handleCreate = async () => {
    if (!name.trim()) return
    try {
      await api.post("/hiring/pending", { name: name.trim(), scene, profile: { role: role.trim() || "member" } })
      queryClient.invalidateQueries({ queryKey: ["agents"] })
      queryClient.invalidateQueries({ queryKey: ["hiring"] })
      closeNewAgent()
      setName("")
      setScene("default")
      setRole("")
    } catch {}
  }

  return (
    <Dialog open={newAgentOpen} onOpenChange={(open) => !open && closeNewAgent()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("cmd.create_agent")}</DialogTitle>
          <DialogDescription>Create a new agent and add it to the team.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. assistant" />
          </div>
          <div className="space-y-2">
            <Label>Scene</Label>
            <Select value={scene} onValueChange={setScene}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="default">default</SelectItem>
                {scenesData?.scenes?.map(s => (
                  <SelectItem key={s.id} value={s.id}>{s.id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Input value={role} onChange={e => setRole(e.target.value)} placeholder="e.g. customer support" />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={closeNewAgent}>Cancel</Button>
            <Button size="sm" disabled={!name.trim()} onClick={handleCreate}>Create</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
