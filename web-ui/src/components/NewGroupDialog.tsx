import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useQueryClient } from "@tanstack/react-query"
import { useT } from "@/context/LanguageContext"
import { useDialogState, useDialogActions } from "@/context/DialogContext"
import { chatApi } from "@/api/chat"
import { agentsApi } from "@/api/agents"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { X } from "lucide-react"

export function NewGroupDialog() {
  const { newGroupOpen } = useDialogState()
  const { closeNewGroup } = useDialogActions()
  const t = useT()
  const queryClient = useQueryClient()

  const [name, setName] = useState("")
  const [selectedAgents, setSelectedAgents] = useState<string[]>([])
  const [search, setSearch] = useState("")

  const { data: agentsData } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list(), enabled: newGroupOpen })

  const allAgents = agentsData?.agents ?? []
  const filteredAgents = allAgents.filter(
    (a: { id: string; name: string }) =>
      !selectedAgents.includes(a.id) &&
      (a.name.toLowerCase().includes(search.toLowerCase()) || a.id.includes(search)),
  )

  const handleCreate = async () => {
    if (!name.trim()) return
    try {
      const members = selectedAgents.map(id => {
        const agent = allAgents.find((a: { id: string }) => a.id === id)
        return { id, name: agent?.name ?? id, role: "member" as const }
      })
      await chatApi.createGroup(name.trim(), members)
      queryClient.invalidateQueries({ queryKey: ["chat"] })
      closeNewGroup()
      setName("")
      setSelectedAgents([])
      setSearch("")
    } catch {}
  }

  return (
    <Dialog open={newGroupOpen} onOpenChange={(open) => !open && closeNewGroup()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Chat Group</DialogTitle>
          <DialogDescription>Create a group chat with selected agents.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Group Name</Label>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Design Team" />
          </div>
          <div className="space-y-2">
            <Label>Members</Label>
            {selectedAgents.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {selectedAgents.map(id => {
                  const a = allAgents.find((x: { id: string }) => x.id === id)
                  return (
                    <Badge key={id} variant="secondary" className="gap-1">
                      {a?.name ?? id}
                      <button onClick={() => setSelectedAgents(s => s.filter(x => x !== id))}>
                        <X className="size-3" />
                      </button>
                    </Badge>
                  )
                })}
              </div>
            )}
            <Input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search agents..." />
            {search && filteredAgents.length > 0 && (
              <div className="border rounded-md mt-1 max-h-32 overflow-y-auto">
                {filteredAgents.slice(0, 10).map((a: { id: string; name: string }) => (
                  <button
                    key={a.id}
                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent transition-colors"
                    onClick={() => {
                      setSelectedAgents(s => [...s, a.id])
                      setSearch("")
                    }}
                  >
                    {a.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={closeNewGroup}>Cancel</Button>
            <Button size="sm" disabled={!name.trim()} onClick={handleCreate}>Create</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
