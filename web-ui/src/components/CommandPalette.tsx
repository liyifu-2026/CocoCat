import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import { useDialogActions } from "@/context/DialogContext"
import { useT } from "@/context/LanguageContext"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { Users, FolderKanban, LayoutDashboard, Plus, MessageSquare, BookOpen, UserPlus, Mail, BarChart3, Calendar, GitBranch, Settings } from "lucide-react"

const pageItems = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/agents", labelKey: "nav.agents", icon: Users },
  { to: "/scenes", labelKey: "nav.scenes", icon: FolderKanban },
  { to: "/chat", labelKey: "nav.chat", icon: MessageSquare },
  { to: "/knowledge", labelKey: "nav.knowledge", icon: BookOpen },
  { to: "/hiring", labelKey: "nav.hiring", icon: UserPlus },
  { to: "/mailbox", labelKey: "nav.mailbox", icon: Mail },
  { to: "/usage", labelKey: "nav.usage", icon: BarChart3 },
  { to: "/schedule", labelKey: "nav.schedule", icon: Calendar },
  { to: "/collaboration", labelKey: "nav.collaboration", icon: GitBranch },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
]

interface Agent {
  id: string
  name: string
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const navigate = useNavigate()
  const t = useT()
  const { openNewAgent, openNewScene } = useDialogActions()

  const { data: agents = [], isFetching } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: () => api.get("/agents"),
    enabled: open,
  })

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen(o => !o)
      }
    }
    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  const runCommand = (command: () => void) => {
    setOpen(false)
    command()
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder={t("cmd.placeholder")} value={query} onValueChange={setQuery} />
      <CommandList>
        <CommandEmpty>
          {isFetching ? <span className="shimmer-text">{t("common.loading")}</span> : t("cmd.no_results")}
        </CommandEmpty>
        <CommandGroup heading={t("cmd.actions")}>
          <CommandItem onSelect={() => runCommand(openNewAgent)}>
            <Plus className="mr-2 h-4 w-4" />
            <span>{t("cmd.create_agent")}</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(openNewScene)}>
            <Plus className="mr-2 h-4 w-4" />
            <span>{t("cmd.create_scene")}</span>
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading={t("cmd.pages")}>
          {pageItems.map(item => (
            <CommandItem key={item.to} onSelect={() => runCommand(() => navigate(item.to))}>
              <item.icon className="mr-2 h-4 w-4" />
              <span>{t(item.labelKey)}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        {agents.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading={t("cmd.agents")}>
              {agents.map((agent: Agent) => (
                <CommandItem key={agent.id} onSelect={() => runCommand(() => navigate(`/agents/${agent.id}`))}>
                  <Users className="mr-2 h-4 w-4" />
                  <span>{agent.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  )
}
