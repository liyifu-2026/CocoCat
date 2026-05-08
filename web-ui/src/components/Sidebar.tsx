import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useSidebar } from "@/context/SidebarContext"
import { useAuth } from "@/context/AuthContext"
import { useT } from "@/context/LanguageContext"
import {
  LayoutDashboard, Users, FolderKanban, Settings, BookOpen, Mail, BarChart3,
  UserPlus, MessageSquare, Calendar, GitBranch, Wrench,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { PanelLeftClose, PanelLeft, LogOut, Pencil, GripVertical, Eye, EyeOff } from "lucide-react"
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext, verticalListSortingStrategy, useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

interface NavItem {
  to: string
  labelKey: string
  icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/chat", labelKey: "nav.chat", icon: MessageSquare },
  { to: "/agents", labelKey: "nav.agents", icon: Users },
  { to: "/scenes", labelKey: "nav.scenes", icon: FolderKanban },
  { to: "/hiring", labelKey: "nav.hiring", icon: UserPlus },
  { to: "/mailbox", labelKey: "nav.mailbox", icon: Mail },
  { to: "/usage", labelKey: "nav.usage", icon: BarChart3 },
  { to: "/schedule", labelKey: "nav.schedule", icon: Calendar },
  { to: "/collaboration", labelKey: "nav.collaboration", icon: GitBranch },
  { to: "/knowledge", labelKey: "nav.knowledge", icon: BookOpen },
  { to: "/skills", labelKey: "nav.skills", icon: Wrench },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
]

const itemMap = new Map(navItems.map(i => [i.to, i]))

function SortableNavItem({
  item, collapsed, hidden, onToggleHide, t,
}: {
  item: NavItem
  collapsed: boolean
  hidden: boolean
  onToggleHide: () => void
  t: (key: string) => string
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.to })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center rounded-md transition-colors",
        isDragging && "opacity-50",
        hidden && "opacity-40",
      )}
    >
      <span
        {...attributes}
        {...listeners}
        className="flex items-center justify-center w-6 h-8 cursor-grab active:cursor-grabbing text-sidebar-foreground/50 hover:text-sidebar-foreground shrink-0"
      >
        <GripVertical className="size-3.5" />
      </span>
      <NavLink
        to={item.to}
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors flex-1",
            isActive && !hidden
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
          )
        }
      >
        <item.icon className="size-4 shrink-0" />
        {!collapsed && <span>{t(item.labelKey)}</span>}
      </NavLink>
      <button
        onClick={onToggleHide}
        className="flex items-center justify-center w-6 h-8 text-sidebar-foreground/50 hover:text-sidebar-foreground shrink-0"
        title={hidden ? t("component.show") : t("component.hide")}
      >
        {hidden ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
      </button>
    </div>
  )
}

export function Sidebar() {
  const { collapsed, toggle, navOrder, hiddenNavs, editMode, toggleEditMode, toggleNavVisibility, setNavOrder } = useSidebar()
  const { logout } = useAuth()
  const t = useT()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = navOrder.indexOf(active.id as string)
    const newIndex = navOrder.indexOf(over.id as string)
    const newOrder = [...navOrder]
    newOrder.splice(oldIndex, 1)
    newOrder.splice(newIndex, 0, active.id as string)
    setNavOrder(newOrder)
  }

  const visibleItems = editMode
    ? navOrder.map(p => itemMap.get(p)).filter(Boolean) as NavItem[]
    : navOrder.filter(p => !hiddenNavs.includes(p)).map(p => itemMap.get(p)).filter(Boolean) as NavItem[]

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200",
        collapsed ? "w-14" : "w-56",
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
        {!collapsed && (
          <span className="font-semibold text-sidebar-foreground">CocoCat</span>
        )}
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={toggle}
          className="text-sidebar-foreground"
        >
          {collapsed ? <PanelLeft className="size-4" /> : <PanelLeftClose className="size-4" />}
        </Button>
      </div>

      <nav className="flex-1 space-y-1 p-2 overflow-y-auto">
        {editMode ? (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={navOrder} strategy={verticalListSortingStrategy}>
              {visibleItems.map(item => (
                <SortableNavItem
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                  hidden={hiddenNavs.includes(item.to)}
                  onToggleHide={() => toggleNavVisibility(item.to)}
                  t={t}
                />
              ))}
            </SortableContext>
          </DndContext>
        ) : (
          visibleItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                )
              }
            >
              <item.icon className="size-4 shrink-0" />
              {!collapsed && <span>{t(item.labelKey)}</span>}
            </NavLink>
          ))
        )}
      </nav>

      <div className="border-t border-sidebar-border p-2 space-y-1">
        {!collapsed && (
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 transition-colors"
          >
            <LogOut className="size-4 shrink-0" />
            <span>{t("nav.logout")}</span>
          </button>
        )}
        {collapsed && (
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-md px-2 py-2 text-red-500 hover:bg-red-50 transition-colors"
            title={t("nav.logout")}
          >
            <LogOut className="size-4 shrink-0" />
          </button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleEditMode}
          className={cn(
            "w-full flex items-center gap-3 justify-start text-sm font-medium transition-colors",
            editMode
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground hover:bg-sidebar-accent",
          )}
        >
          <Pencil className="size-4 shrink-0" />
          {!collapsed && <span>{editMode ? t("component.done") : t("component.edit_sidebar")}</span>}
        </Button>
      </div>
    </aside>
  )
}
