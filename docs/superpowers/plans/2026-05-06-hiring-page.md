# Hiring Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Add hiring plan form + candidate generation + nickname dialog.

**Architecture:** New Python skill for leader, new FastAPI endpoint, frontend rewrite.

**Tech Stack:** Python (LLM tool), FastAPI, React/TypeScript

---

### Task 1: Python — Create dream_candidates skill

**Files:**
- Create: `py-agent/skills/dream_candidates.py`

- [ ] **Step 1: Create the skill script**

```python
"""Skill: Dream up candidate profiles for hiring."""
import json, os, sys

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "dream_candidates",
        "description": "根据招聘需求畅想候选人，生成候选人档案。每个候选人包含姓名、角色、目标、特质、规则、背景。",
        "parameters": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "description": "招聘职位"},
                "skills": {"type": "string", "description": "所需技能"},
                "responsibilities": {"type": "string", "description": "职责描述"},
                "traits": {"type": "string", "description": "性格特质"},
                "count": {"type": "integer", "description": "生成候选人数量"},
            },
            "required": ["position", "count"],
        },
    },
}

def dream_candidates(position: str, count: int = 5, skills: str = "", responsibilities: str = "", traits: str = "", **kwargs) -> str:
    """Generate candidate profiles using LLM and write them as hire requests."""
    from llm import LLMClient
    llm = LLMClient()
    
    prompt = f"""你是一个招聘专家。请根据以下招聘需求，畅想{count}个合适的候选人。

招聘职位：{position}
所需技能：{skills}
职责描述：{responsibilities}
性格特质：{traits}

请为每个候选人生成一个JSON对象，包含以下字段：
- name: 中文名（2-3个字）
- role: 角色/职位
- objective: 工作目标（一句话）
- traits: 特质列表（2-3个词）
- rules: 行为规则列表（2-3条）
- background: 背景简介（一句话）

以JSON数组格式返回，不要包含其他内容。"""

    resp = llm.chat([{"role": "user", "content": prompt}], max_tokens=4096, temperature=0.9)
    content = resp.get("content", "")
    
    # Extract JSON array from response
    import re
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if not json_match:
        return "Error: Failed to generate candidates - no JSON in response"
    
    try:
        candidates = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        return f"Error: Failed to parse candidates JSON: {e}"
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pending_dir = os.path.join(base_dir, "agents", "hire_requests", "pending")
    os.makedirs(pending_dir, exist_ok=True)
    
    created = []
    for c in candidates:
        cid = f"candidate_{c['name']}"
        hire_data = {
            "id": cid,
            "name": c["name"],
            "scene": "default",
            "profile": {
                "role": c.get("role", position),
                "objective": c.get("objective", ""),
                "traits": c.get("traits", []),
                "rules": c.get("rules", []),
                "background": c.get("background", ""),
            },
        }
        path = os.path.join(pending_dir, f"{cid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hire_data, f, ensure_ascii=False, indent=2)
        created.append(c["name"])
    
    return f"成功生成 {len(created)} 个候选人：{', '.join(created)}"

def run(**kwargs) -> str:
    return dream_candidates(**kwargs)
```

- [ ] **Step 2: Add the tool to leader's registry**

The tool needs to be registered. It should be loaded as an environment skill or registered in the tool registry. Let me check how existing tools are registered.

- [ ] **Step 3: Commit**

```bash
git add py-agent/skills/dream_candidates.py
git commit -m "feat: add dream_candidates skill for leader hiring"
```

---

### Task 2: FastAPI — Add POST /api/hiring/plan endpoint

**Files:**
- Modify: `web/routes/hiring.py` — or add to `web/main.py`

Actually, hiring is not a separate route file. The hiring endpoints are defined directly in `web/main.py`. Let me add the plan endpoint there.

- [ ] **Step 1: Add the plan endpoint in web/main.py**

Find the hiring section in `web/main.py`. Add after the `reject_hire` function:

```python
@app.post("/api/hiring/plan")
async def create_hiring_plan(request: Request):
    """Submit a hiring plan to leader for candidate generation."""
    body = await request.json()
    position = body.get("position", "")
    count = body.get("count", 5)
    if not position:
        return JSONResponse({"error": "position is required"}, status_code=400)
    
    # Dispatch to leader agent via Rust core
    from web.services.api_client import _call_rust_api
    async with httpx.AsyncClient() as client:
        try:
            # Get a token for Rust API auth
            resp = await client.post(
                "http://localhost:3000/api/chat",
                json={
                    "content": f"请根据招聘需求畅想候选人：职位={position}，技能={body.get('skills','')}，职责={body.get('responsibilities','')}，特质={body.get('traits','')}，数量={count}",
                    "agent_id": "leader",
                    "scene_id": "default",
                    "user_id": "admin",
                },
                timeout=5,
            )
            result = resp.json()
            return {"status": "plan_submitted", "task_uuid": result.get("task_uuid", "")}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
```

Add `import httpx` at the top of main.py if not already there.

- [ ] **Step 2: Verify**

```bash
python3 -c "import web.main; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web/main.py
git commit -m "feat: add POST /api/hiring/plan endpoint"
```

---

### Task 3: Frontend — Rewrite Hiring page with form + cards + nickname dialog

**Files:**
- Modify: `web-ui/src/pages/Hiring.tsx`

- [ ] **Step 1: Rewrite Hiring.tsx**

```tsx
import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { hiringApi } from "@/api/hiring"
import { agentsApi } from "@/api/agents"
import type { PendingHire } from "@/api/hiring"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  UserPlus, Check, X, Clock, Sparkles, Send, Users,
} from "lucide-react"
import { CardGridSkeleton } from "@/components/LoadingSkeleton"
import ErrorState from "@/components/ErrorState"
import { toast } from "sonner"
import { useT } from "@/context/LanguageContext"

export default function Hiring() {
  const t = useT()
  const queryClient = useQueryClient()
  const [position, setPosition] = useState("")
  const [skills, setSkills] = useState("")
  const [responsibilities, setResponsibilities] = useState("")
  const [traits, setTraits] = useState("")
  const [count, setCount] = useState(5)
  const [submitting, setSubmitting] = useState(false)
  const [acceptingId, setAcceptingId] = useState<string | null>(null)
  const [nickname, setNickname] = useState("")

  const { data: pending, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["hiring"],
    queryFn: () => hiringApi.listPending(),
    refetchInterval: 5000,
  })

  if (isLoading) return <CardGridSkeleton count={3} />
  if (isError) return <ErrorState message={error?.message} onRetry={refetch} />

  async function submitPlan() {
    if (!position.trim()) return
    setSubmitting(true)
    try {
      await fetch("/api/hiring/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ position: position.trim(), skills, responsibilities, traits, count }),
      })
      toast.success("Hiring plan submitted to Leader")
      setPosition(""); setSkills(""); setResponsibilities(""); setTraits("")
    } catch { toast.error("Failed to submit plan") }
    finally { setSubmitting(false) }
  }

  async function confirmApprove(hire: PendingHire) {
    try {
      await hiringApi.approve(hire.id)
      // If nickname was provided, set it after agent creation
      if (nickname.trim()) {
        // The approve handler creates agent with id=hire.id
        const agentId = hire.id
        try {
          await agentsApi.updateDisplay(agentId, { nickname: nickname.trim() } as any)
        } catch {}
      }
      toast.success(t("hiring.approved"))
      queryClient.invalidateQueries({ queryKey: ["hiring"] })
    } catch { toast.error("Failed to approve") }
    finally { setAcceptingId(null); setNickname("") }
  }

  async function reject(hire: PendingHire) {
    try {
      await hiringApi.reject(hire.id)
      toast.success(t("hiring.rejected"))
      queryClient.invalidateQueries({ queryKey: ["hiring"] })
    } catch { toast.error("Failed to reject") }
  }

  const hires = pending?.pending ?? []

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{t("hiring.title")}</h1>
        <Badge variant="outline" className="gap-1">
          <Clock className="size-3" /> {t("hiring.pending_count").replace("{count}", String(hires.length))}
        </Badge>
      </div>

      {/* Hiring Plan Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="size-4" />
            Post a Hiring Plan
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Position</Label>
              <Input value={position} onChange={e => setPosition(e.target.value)}
                placeholder="e.g. Customer Support Specialist" />
            </div>
            <div className="space-y-2">
              <Label>Number of Candidates</Label>
              <Input type="number" min={1} max={10} value={count}
                onChange={e => setCount(parseInt(e.target.value) || 5)} />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Required Skills</Label>
            <Input value={skills} onChange={e => setSkills(e.target.value)}
              placeholder="e.g. patience, communication, problem-solving" />
          </div>
          <div className="space-y-2">
            <Label>Responsibilities</Label>
            <Textarea value={responsibilities} onChange={e => setResponsibilities(e.target.value)}
              placeholder="Describe the role's responsibilities..." className="min-h-[80px]" />
          </div>
          <div className="space-y-2">
            <Label>Desired Traits</Label>
            <Input value={traits} onChange={e => setTraits(e.target.value)}
              placeholder="e.g. detail-oriented, responsible" />
          </div>
          <Button onClick={submitPlan} disabled={!position.trim() || submitting} className="gap-2">
            <Send className="size-4" />
            {submitting ? "Submitting..." : "Let Leader Dream Up Candidates"}
          </Button>
        </CardContent>
      </Card>

      {/* Candidate Cards */}
      {hires.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Users className="size-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Pending Approval ({hires.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {hires.map(hire => (
              <Card key={hire.id}>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold">{hire.name}</h4>
                      <p className="text-xs text-muted-foreground">{hire.profile?.role || "N/A"}</p>
                    </div>
                    <Badge variant="secondary" className="text-[10px]">{hire.id}</Badge>
                  </div>
                  {hire.profile?.objective && (
                    <p className="text-sm text-muted-foreground">{hire.profile.objective}</p>
                  )}
                  {hire.profile?.traits?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {hire.profile.traits.map((trait, i) => (
                        <Badge key={i} variant="outline" className="text-[10px]">{trait}</Badge>
                      ))}
                    </div>
                  )}
                  {hire.profile?.background && (
                    <p className="text-xs text-muted-foreground">{hire.profile.background}</p>
                  )}
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" className="flex-1" onClick={() => setAcceptingId(hire.id)}>
                      <Check className="size-3 mr-1" /> {t("hiring.approve")}
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1" onClick={() => reject(hire)}>
                      <X className="size-3 mr-1" /> {t("hiring.reject")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {hires.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <UserPlus className="size-12 mx-auto mb-4 opacity-30" />
          <p>{t("hiring.no_pending")}</p>
          <p className="text-sm mt-1">{t("hiring.no_pending_desc")}</p>
        </div>
      )}

      {/* Nickname Dialog */}
      <Dialog open={!!acceptingId} onOpenChange={(o) => { if (!o) { setAcceptingId(null); setNickname("") } }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Set Nickname</DialogTitle>
            <DialogDescription>
              Give this new team member a nickname. Leave empty to use their original name.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Nickname</Label>
              <Input value={nickname} onChange={e => setNickname(e.target.value)}
                placeholder="Optional nickname..." autoFocus
                onKeyDown={e => {
                  if (e.key === "Enter") {
                    const hire = hires.find(h => h.id === acceptingId)
                    if (hire) confirmApprove(hire)
                  }
                }} />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => {
                const hire = hires.find(h => h.id === acceptingId)
                if (hire) confirmApprove(hire)
              }}>Skip</Button>
              <Button size="sm" onClick={() => {
                const hire = hires.find(h => h.id === acceptingId)
                if (hire) confirmApprove(hire)
              }}>Confirm</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript + Build**

```bash
npx tsc --noEmit && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/Hiring.tsx
git commit -m "feat: rewrite Hiring page with plan form, candidate cards, and nickname dialog"
```
