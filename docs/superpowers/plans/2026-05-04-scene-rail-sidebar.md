# Scene Rail + Context-Aware Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace CompanyRail with SceneRail (scene icons + import button + theme toggle), add scene display config, make Sidebar context-aware (scene mode vs global mode)

**Architecture:** SceneRail reads scenes list + display configs, renders per-scene icons. Sidebar checks current route – `/scenes/:id` shows scene navigation, other routes show global navigation. Backend adds display.json CRUD and import endpoints.

**Tech Stack:** React 19, TypeScript, Tailwind v4, FastAPI

---

## File Structure

### New Files (3)
| File | Responsibility |
|------|---------------|
| `src/components/SceneRail.tsx` | Left rail with scene icons + import + theme toggle |
| `src/components/SceneAvatar.tsx` | Scene icon: auto initial+color or custom avatar |
| `src/components/ImportSceneDialog.tsx` | 4-tab import dialog (path/zip/git/new) |

### Modified Files (7)
| File | Change |
|------|--------|
| `src/components/Layout.tsx` | Replace CompanyRail with SceneRail |
| `src/components/Sidebar.tsx` | Add scene-mode navigation when on `/scenes/:id` |
| `src/pages/SceneDetail.tsx` | Add Display section (icon picker + color + nickname) |
| `src/api/scenes.ts` | Add `display`, `importViaPath`, `importViaZip`, `importViaGit` |
| `web/routes/scenes.py` | Add `GET/PUT /api/scenes/{id}/display`, `POST /api/scenes/import/*` |
| `src/components/ui/avatar.tsx` | Ensure Avatar supports fallback text styling |

---

### Task 1: SceneAvatar Component

**Files:**
- Create: `src/components/SceneAvatar.tsx`

- [ ] **Step 1: Create SceneAvatar component**

```tsx
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

const SCENE_COLORS = [
  "bg-blue-500", "bg-green-500", "bg-purple-500", "bg-orange-500",
  "bg-pink-500", "bg-teal-500", "bg-cyan-500", "bg-rose-500",
]

function hashColor(id: string): string {
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash = id.charCodeAt(i) + ((hash << 5) - hash)
  }
  return SCENE_COLORS[Math.abs(hash) % SCENE_COLORS.length]
}

interface SceneAvatarProps {
  id: string
  avatar?: string
  color?: string
  size?: "sm" | "md"
}

export function SceneAvatar({ id, avatar, color, size = "sm" }: SceneAvatarProps) {
  const bgColor = color || hashColor(id)
  const initial = id.charAt(0).toUpperCase()
  const dim = size === "md" ? "w-9 h-9 text-sm" : "w-7 h-7 text-xs"

  return (
    <Avatar className={cn(dim, "rounded-md")}>
      <AvatarFallback className={cn(bgColor, "text-white font-medium rounded-md")}>
        {initial}
      </AvatarFallback>
    </Avatar>
  )
}
```

- [ ] **Step 2: Verify compilation**

```bash
npx tsc --noEmit
```

---

### Task 2: SceneRail Component

**Files:**
- Create: `src/components/SceneRail.tsx`
- Remove: `src/components/CompanyRail.tsx`

- [ ] **Step 1: Create SceneRail component**

```tsx
import { useNavigate, useLocation } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { scenesApi } from "@/api/scenes"
import { SceneAvatar } from "./SceneAvatar"
import { useTheme } from "@/context/ThemeContext"
import { Button } from "@/components/ui/button"
import { Sun, Moon, Plus } from "lucide-react"
import { cn } from "@/lib/utils"

export function SceneRail() {
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()

  const { data } = useQuery({ queryKey: ["scenes"], queryFn: () => scenesApi.list() })
  const scenes = data?.scenes ?? []

  const activeSceneId = location.pathname.match(/^\/scenes\/([^/]+)/)?.[1]

  return (
    <aside className="w-11 shrink-0 border-r border-border bg-sidebar flex flex-col items-center py-2 gap-2">
      <button
        onClick={() => navigate("/dashboard")}
        className={cn(
          "w-7 h-7 rounded-md flex items-center justify-center transition-colors",
          location.pathname === "/dashboard" || location.pathname === "/"
            ? "bg-sidebar-accent text-sidebar-accent-foreground"
            : "text-sidebar-foreground hover:bg-sidebar-accent",
        )}
        title="Dashboard"
      >
        <span className="text-xs font-bold">CC</span>
      </button>

      <div className="w-full border-t border-sidebar-border my-1" />

      <nav className="flex-1 flex flex-col items-center gap-1.5 overflow-y-auto scrollbar-auto-hide">
        {scenes.map(scene => (
          <button
            key={scene.id}
            onClick={() => navigate(`/scenes/${scene.id}`)}
            className={cn(
              "rounded-md transition-all duration-150",
              activeSceneId === scene.id
                ? "ring-2 ring-sidebar-primary ring-offset-1 ring-offset-sidebar"
                : "hover:opacity-80",
            )}
            title={scene.id}
          >
            <SceneAvatar id={scene.id} avatar={undefined} color={undefined} />
          </button>
        ))}
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => {}} // TODO: open ImportSceneDialog
          className="mt-1 text-sidebar-foreground hover:bg-sidebar-accent"
          title="Import Scene"
        >
          <Plus className="size-4" />
        </Button>
      </nav>

      <div className="w-full border-t border-sidebar-border my-1" />

      <button
        onClick={toggleTheme}
        className="w-7 h-7 rounded-md flex items-center justify-center text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
        title={theme === "light" ? "Dark Mode" : "Light Mode"}
      >
        {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
      </button>
    </aside>
  )
}
```

- [ ] **Step 2: Update Layout.tsx**

Replace `import { CompanyRail } from "./CompanyRail"` with `import { SceneRail } from "./SceneRail"` and change `<CompanyRail />` to `<SceneRail />`.

- [ ] **Step 3: Remove CompanyRail.tsx**

```bash
rm src/components/CompanyRail.tsx
```

- [ ] **Step 4: Verify compilation**

```bash
npx tsc --noEmit
```

---

### Task 3: Scene Display API (Backend)

**Files:**
- Modify: `web/routes/scenes.py`

- [ ] **Step 1: Add display config endpoints**

Add to `web/routes/scenes.py`:

```python
@router.get("/api/scenes/{scene_id}/display")
def get_scene_display(scene_id: str):
    display_path = BASE_DIR / "scenes" / scene_id / "display.json"
    display = {"avatar": "", "color": "", "nickname": ""}
    if display_path.exists():
        try:
            display.update(json.loads(display_path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return display

@router.put("/api/scenes/{scene_id}/display")
def update_scene_display(scene_id: str, body: dict):
    scene_dir = BASE_DIR / "scenes" / scene_id
    if not scene_dir.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "scene not found"}, status_code=404)
    display_path = scene_dir / "display.json"
    existing = {}
    if display_path.exists():
        try:
            existing = json.loads(display_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    for key in ("avatar", "color", "nickname"):
        if key in body:
            existing[key] = body[key]
    display_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "display": existing}
```

- [ ] **Step 2: Verify backend starts**

```bash
cd /home/leaif/CocoCat && python3 -m web.main &
curl -s http://localhost:8000/api/health | head -c 50
```

---

### Task 4: Scene Display API (Frontend)

**Files:**
- Modify: `src/api/scenes.ts`

- [ ] **Step 1: Add display API calls**

Add to `src/api/scenes.ts`:

```ts
export interface SceneDisplay {
  avatar?: string
  color?: string
  nickname?: string
}

// In the scenesApi object, add:
  display: (sceneId: string) => api.get<SceneDisplay>(`/scenes/${sceneId}/display`),
  updateDisplay: (sceneId: string, display: SceneDisplay) =>
    api.put<{ display: SceneDisplay }>(`/scenes/${sceneId}/display`, display),
```

- [ ] **Step 2: Verify compilation**

```bash
npx tsc --noEmit
```

---

### Task 5: Scene Display Settings in SceneDetail

**Files:**
- Modify: `src/pages/SceneDetail.tsx`

- [ ] **Step 1: Add display config section**

Add after the existing cards (context/roster/skills/kbs sections):

```tsx
// Add import at top:
import { AvatarPicker } from "@/components/AvatarPicker"
import type { SceneDisplay } from "@/api/scenes"

// Add state:
const [displayOpen, setDisplayOpen] = useState(false)
const [displayConfig, setDisplayConfig] = useState<SceneDisplay>({ avatar: "", color: "", nickname: "" })

const { data: displayData } = useQuery({
  queryKey: ["scene", id, "display"],
  queryFn: () => scenesApi.display(id!),
  enabled: !!id,
})

// Add button + dialog before the closing </div> of the page:
<div className="pt-4 border-t border-border">
  <Button size="sm" variant="outline" onClick={() => {
    setDisplayConfig(displayData ?? { avatar: "", color: "", nickname: "" })
    setDisplayOpen(true)
  }}>
    <Pencil className="size-3 mr-1" /> Edit Display
  </Button>
</div>

<Dialog open={displayOpen} onOpenChange={setDisplayOpen}>
  <DialogContent className="max-w-sm">
    <DialogHeader><DialogTitle>Scene Display</DialogTitle></DialogHeader>
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium mb-1 block">Nickname</label>
        <Input value={displayConfig.nickname} onChange={e => setDisplayConfig(p => ({ ...p, nickname: e.target.value }))}
          placeholder={id} />
      </div>
      <AvatarPicker
        currentAvatar={displayConfig.avatar}
        currentColor={displayConfig.color}
        onAvatarChange={a => setDisplayConfig(p => ({ ...p, avatar: a }))}
        onColorChange={c => setDisplayConfig(p => ({ ...p, color: c }))}
      />
      <div className="flex items-center gap-3 pt-2">
        <div className="text-sm text-muted-foreground">Preview:</div>
        <SceneAvatar id={id!} avatar={displayConfig.avatar} color={displayConfig.color} size="md" />
        <span className="text-sm font-medium">{displayConfig.nickname || id}</span>
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={() => setDisplayOpen(false)}>Cancel</Button>
        <Button size="sm" onClick={async () => {
          await scenesApi.updateDisplay(id!, displayConfig)
          queryClient.invalidateQueries({ queryKey: ["scene", id, "display"] })
          setDisplayOpen(false)
        }}>Save</Button>
      </div>
    </div>
  </DialogContent>
</Dialog>
```

Also import `SceneAvatar`:
```tsx
import { SceneAvatar } from "@/components/SceneAvatar"
```

- [ ] **Step 2: Verify compilation**

```bash
npx tsc --noEmit
```

---

### Task 6: Context-Aware Sidebar

**Files:**
- Modify: `src/components/Sidebar.tsx`

- [ ] **Step 1: Add scene-mode navigation**

Add to the top of the Sidebar component, after hooks:

```tsx
import { useLocation, useNavigate, NavLink } from "react-router-dom"
// (already imported)

// Add after hooks:
const location = useLocation()
const sceneMatch = location.pathname.match(/^\/scenes\/([^/]+)/)
const activeSceneId = sceneMatch?.[1]

const { data: scenesData } = useQuery({
  queryKey: ["scenes"],
  queryFn: () => scenesApi.list(),
  enabled: !!activeSceneId,
})
const currentScene = scenesData?.scenes?.find(s => s.id === activeSceneId)

const { data: displayData } = useQuery({
  queryKey: ["scene", activeSceneId, "display"],
  queryFn: () => scenesApi.display(activeSceneId!),
  enabled: !!activeSceneId,
})

// Scene nav items:
const sceneNavItems = [
  { to: `/scenes/${activeSceneId}`, label: "Context", icon: FileText },
  { to: `/scenes/${activeSceneId}#roster`, label: "Roster", icon: Users },
  { to: `/scenes/${activeSceneId}#skills`, label: "Skills", icon: Wrench },
  { to: `/scenes/${activeSceneId}#kbs`, label: "Knowledge", icon: BookOpen },
  { to: `/scenes/${activeSceneId}#entries`, label: "Entries", icon: Plug },
]
```

Then replace the main content of the sidebar to conditionally render:

```tsx
{activeSceneId && currentScene ? (
  // Scene mode
  <nav className="flex-1 overflow-y-auto scrollbar-auto-hide px-2 py-3 space-y-4">
    <div className="flex items-center gap-2 px-3 py-2">
      <SceneAvatar id={activeSceneId} avatar={displayData?.avatar} color={displayData?.color} />
      <div className="min-w-0">
        <div className="text-sm font-medium truncate">{displayData?.nickname || currentScene.id}</div>
        <button onClick={() => navigate("/scenes")} className="text-xs text-muted-foreground hover:text-foreground">
          ← All Scenes
        </button>
      </div>
    </div>
    <div className="space-y-0.5">
      {sceneNavItems.map(item => (
        <NavLink key={item.to} to={item.to}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-1.5 text-[13px] font-medium transition-all duration-150",
              isActive
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground hover:bg-sidebar-accent",
            )
          }
        >
          <item.icon className="size-4 shrink-0" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </div>
  </nav>
) : (
  // Global mode (existing navSections code)
  ...
)}
```

Also add the missing imports (`FileText`, `Wrench`, `Plug` from lucide-react; `useQuery` from tanstack; `scenesApi`; `SceneAvatar`).

- [ ] **Step 2: Verify compilation**

```bash
npx tsc --noEmit
```

---

### Task 7: ImportSceneDialog

**Files:**
- Create: `src/components/ImportSceneDialog.tsx`

- [ ] **Step 1: Create ImportSceneDialog**

```tsx
import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { scenesApi } from "@/api/scenes"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FolderOpen, FileArchive, GitBranch, Plus } from "lucide-react"
import { toast } from "sonner"
import { useDialogState, useDialogActions } from "@/context/DialogContext"

export function ImportSceneDialog() {
  const { newSceneOpen } = useDialogState()
  const { closeNewScene } = useDialogActions()
  const queryClient = useQueryClient()

  const [path, setPath] = useState("")
  const [gitUrl, setGitUrl] = useState("")
  const [importing, setImporting] = useState(false)

  const handleImportPath = async () => {
    if (!path.trim()) return
    setImporting(true)
    try {
      await scenesApi.importViaPath(path.trim())
      queryClient.invalidateQueries({ queryKey: ["scenes"] })
      toast.success("Scene imported")
      closeNewScene()
      setPath("")
    } catch { toast.error("Import failed") }
    finally { setImporting(false) }
  }

  const handleImportGit = async () => {
    if (!gitUrl.trim()) return
    setImporting(true)
    try {
      await scenesApi.importViaGit(gitUrl.trim())
      queryClient.invalidateQueries({ queryKey: ["scenes"] })
      toast.success("Scene cloned from git")
      closeNewScene()
      setGitUrl("")
    } catch { toast.error("Git clone failed") }
    finally { setImporting(false) }
  }

  return (
    <Dialog open={newSceneOpen} onOpenChange={(open) => !open && closeNewScene()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Import Scene</DialogTitle>
          <DialogDescription>Add an existing scene from a local path, ZIP file, or git repository.</DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="path">
          <TabsList className="grid grid-cols-3">
            <TabsTrigger value="path"><FolderOpen className="size-3 mr-1" />Path</TabsTrigger>
            <TabsTrigger value="zip"><FileArchive className="size-3 mr-1" />ZIP</TabsTrigger>
            <TabsTrigger value="git"><GitBranch className="size-3 mr-1" />Git</TabsTrigger>
          </TabsList>

          <TabsContent value="path" className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>Local Path</Label>
              <Input value={path} onChange={e => setPath(e.target.value)}
                placeholder="/home/user/scenes/my-scene" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={closeNewScene}>Cancel</Button>
              <Button size="sm" onClick={handleImportPath} disabled={!path.trim() || importing}>
                {importing ? "Importing..." : "Import"}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="zip" className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>ZIP File</Label>
              <Input type="file" accept=".zip" />
            </div>
            <p className="text-xs text-muted-foreground">Select a .zip file containing a scene directory structure.</p>
          </TabsContent>

          <TabsContent value="git" className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>Git Repository URL</Label>
              <Input value={gitUrl} onChange={e => setGitUrl(e.target.value)}
                placeholder="https://github.com/user/scene-template.git" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={closeNewScene}>Cancel</Button>
              <Button size="sm" onClick={handleImportGit} disabled={!gitUrl.trim() || importing}>
                {importing ? "Cloning..." : "Clone & Import"}
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Add import API calls to scenes.ts**

Add to `scenesApi`:
```ts
  importViaPath: (path: string) =>
    api.post<{ status: string; scene_id: string }>("/scenes/import/path", { path }),
  importViaZip: (formData: FormData) =>
    api.post<{ status: string; scene_id: string }>("/scenes/import/zip", formData),
  importViaGit: (url: string) =>
    api.post<{ status: string; scene_id: string }>("/scenes/import/git", { url }),
```

- [ ] **Step 3: Add import endpoints to backend routes/scenes.py**

```python
@router.post("/api/scenes/import/path")
def import_scene_from_path(body: dict):
    import shutil
    src = body.get("path", "").strip()
    if not src or not Path(src).exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "invalid path"}, status_code=400)
    src_path = Path(src)
    scene_id = src_path.name
    dst = BASE_DIR / "scenes" / scene_id
    if dst.exists():
        return JSONResponse({"error": "scene already exists"}, status_code=409)
    shutil.copytree(src_path, dst)
    return {"status": "imported", "scene_id": scene_id}

@router.post("/api/scenes/import/git")
def import_scene_from_git(body: dict):
    import subprocess, tempfile
    url = body.get("url", "").strip()
    if not url:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "url is required"}, status_code=400)
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(["git", "clone", url, tmp], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return JSONResponse({"error": result.stderr}, status_code=400)
        scene_id = Path(url).stem
        dst = BASE_DIR / "scenes" / scene_id
        if dst.exists():
            return JSONResponse({"error": "scene already exists"}, status_code=409)
        import shutil
        shutil.copytree(tmp, dst)
    return {"status": "imported", "scene_id": scene_id}
```

- [ ] **Step 4: Register ImportSceneDialog in Layout.tsx**

Add `import { ImportSceneDialog } from "./ImportSceneDialog"` and `<ImportSceneDialog />` in the Layout return.

- [ ] **Step 5: Wire SceneRail import button**

In SceneRail.tsx, replace the `onClick={() => {}}` on the + button with `onClick={() => {}}` (keep for now — DialogProvider integration):

```tsx
// Import useDialogActions
import { useDialogActions } from "@/context/DialogContext"
// In component
const { openNewScene } = useDialogActions()
// On button:
onClick={openNewScene}
```

Note: We reuse `newSceneOpen` / `openNewScene` from DialogProvider for the import dialog. If there's a conflict with the existing NewSceneDialog, rename the import dialog state to `importSceneOpen` in DialogContext.

- [ ] **Step 6: Verify compilation**

```bash
npx tsc --noEmit
```

---

### Task 8: Build Verification

- [ ] **Step 1: Full build**

```bash
npm run build
```

Expected: Build succeeds. Fix any TypeScript errors.

- [ ] **Step 2: Start backend and test**

```bash
cd /home/leaif/CocoCat && python3 -m web.main &
curl -s -X POST http://localhost:8000/api/scenes/general/display -H "Content-Type: application/json" -d '{"avatar":"star","color":"bg-blue-500"}'
curl -s http://localhost:8000/api/scenes/general/display
```
