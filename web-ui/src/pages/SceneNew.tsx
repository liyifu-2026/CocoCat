import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { ArrowLeft, ArrowRight, Check } from "lucide-react"

const PURPOSES = [
  { id: "customer_service", label: "客服", icon: "🎧" },
  { id: "content_writing", label: "内容写作", icon: "📝" },
  { id: "project_management", label: "项目管理", icon: "📋" },
  { id: "data_analysis", label: "数据分析", icon: "🔍" },
  { id: "custom", label: "自定义", icon: "✨" },
]

const TONES = [
  { id: "friendly", label: "亲切友好", emoji: "😊" },
  { id: "professional", label: "专业严谨", emoji: "👔" },
  { id: "concise", label: "简洁高效", emoji: "⚡" },
  { id: "humorous", label: "幽默风趣", emoji: "🎭" },
]

const LANGUAGES = [
  { id: "zh", label: "中文" },
  { id: "en", label: "English" },
  { id: "zh_en", label: "中英混合" },
]

const CHANNELS = [
  { id: "web", label: "Web 聊天", icon: "🌐" },
  { id: "wechat", label: "微信", icon: "💬" },
  { id: "feishu", label: "飞书", icon: "🐦" },
  { id: "api", label: "API", icon: "🔌" },
]

const STEPS = ["场景用途", "Agent 风格", "知识与技能", "渠道入口", "确认创建"]

const AVAILABLE_KBS = ["退货政策 FAQ", "产品手册", "team-wiki"]
const AVAILABLE_SKILLS = ["communication", "prd_writing", "code_review", "file-ops", "strategy"]

interface FormData {
  id: string
  name: string
  description: string
  purpose: string
  agentName: string
  agentTone: string
  agentLanguage: string
  agentModel: string
  kbs: string[]
  skills: string[]
  channels: string[]
}

export default function SceneNew() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<FormData>({
    id: `scene-${Date.now()}`,
    name: "",
    description: "",
    purpose: "customer_service",
    agentName: "",
    agentTone: "friendly",
    agentLanguage: "zh",
    agentModel: "",
    kbs: [],
    skills: [],
    channels: ["web"],
  })

  const update = (field: keyof FormData, value: string | string[]) =>
    setForm((f) => ({ ...f, [field]: value }))

  const toggleArray = (field: "kbs" | "skills" | "channels", item: string) => {
    const arr = form[field]
    update(field, arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item])
  }

  const handleCreate = async () => {
    const res = await fetch("/api/scenes/full", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    })
    if (res.ok) {
      navigate(`/scenes/${form.id}/run`)
    }
  }

  return (
    <div className="max-w-xl mx-auto p-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-2 flex-1">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0 ${
                i <= step ? "bg-blue-500 text-white" : "bg-muted text-muted-foreground"
              }`}
            >
              {i < step ? <Check size={16} /> : i + 1}
            </div>
            <span className={`text-xs hidden sm:inline ${i <= step ? "text-blue-600" : "text-muted-foreground"}`}>
              {s}
            </span>
            {i < STEPS.length - 1 && <div className="flex-1 h-px bg-border ml-2" />}
          </div>
        ))}
      </div>

      {/* Step 1: Purpose */}
      {step === 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">这个场景是干什么的？</h2>
          <label className="block text-sm font-medium mb-1">场景名称 *</label>
          <input
            className="w-full border rounded-lg px-3 py-2 mb-4 text-sm bg-background"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            placeholder="例如：售后客服"
          />
          <label className="block text-sm font-medium mb-2">场景用途 *</label>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {PURPOSES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => update("purpose", p.id)}
                className={`border rounded-lg p-3 text-center text-sm ${
                  form.purpose === p.id
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <span className="text-xl">{p.icon}</span>
                <p className="mt-1">{p.label}</p>
              </button>
            ))}
          </div>
          <label className="block text-sm font-medium mb-1">一句话描述</label>
          <input
            className="w-full border rounded-lg px-3 py-2 text-sm bg-background"
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            placeholder="这个场景具体做什么"
          />
        </div>
      )}

      {/* Step 2: Agent Style */}
      {step === 1 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Agent 是什么风格？</h2>
          <label className="block text-sm font-medium mb-1">Agent 名称</label>
          <input
            className="w-full border rounded-lg px-3 py-2 mb-4 text-sm bg-background"
            value={form.agentName || form.name}
            onChange={(e) => update("agentName", e.target.value)}
            placeholder="默认等于场景名"
          />
          <label className="block text-sm font-medium mb-2">说话风格</label>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {TONES.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => update("agentTone", t.id)}
                className={`border rounded-lg p-3 text-center text-sm ${
                  form.agentTone === t.id
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <span className="text-xl">{t.emoji}</span>
                <p className="mt-1">{t.label}</p>
              </button>
            ))}
          </div>
          <label className="block text-sm font-medium mb-2">语言</label>
          <div className="flex gap-3 mb-4">
            {LANGUAGES.map((l) => (
              <button
                key={l.id}
                type="button"
                onClick={() => update("agentLanguage", l.id)}
                className={`border rounded-lg px-4 py-2 text-sm ${
                  form.agentLanguage === l.id
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                    : "border-border"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: KB + Skills */}
      {step === 2 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">它需要知道什么？</h2>
          <label className="block text-sm font-medium mb-2">挂载知识库（可选）</label>
          <div className="border rounded-lg p-3 mb-4">
            {AVAILABLE_KBS.map((kb) => (
              <label key={kb} className="flex items-center gap-2 py-2 border-b border-border last:border-0 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.kbs.includes(kb)}
                  onChange={() => toggleArray("kbs", kb)}
                  className="accent-blue-500"
                />
                📚 {kb}
              </label>
            ))}
          </div>
          <label className="block text-sm font-medium mb-2">启用技能（可选）</label>
          <div className="flex flex-wrap gap-2">
            {AVAILABLE_SKILLS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => toggleArray("skills", s)}
                className={`px-3 py-1.5 rounded-full text-xs border ${
                  form.skills.includes(s)
                    ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400"
                    : "border-border text-muted-foreground"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 4: Channels */}
      {step === 3 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">用户从哪里找到它？</h2>
          <div className="grid grid-cols-2 gap-3">
            {CHANNELS.map((ch) => (
              <button
                key={ch.id}
                type="button"
                onClick={() => toggleArray("channels", ch.id)}
                className={`border rounded-lg p-4 text-center ${
                  form.channels.includes(ch.id)
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <div className="text-2xl">{ch.icon}</div>
                <p className="text-sm font-medium mt-1">{ch.label}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 5: Review */}
      {step === 4 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">确认创建</h2>
          <div className="bg-muted rounded-lg p-4 text-sm">
            {[
              ["场景名", form.name],
              ["用途", PURPOSES.find((p) => p.id === form.purpose)?.label ?? ""],
              ["Agent", `${form.agentName || form.name} · ${TONES.find((t) => t.id === form.agentTone)?.label} · ${LANGUAGES.find((l) => l.id === form.agentLanguage)?.label}`],
              ["知识库", form.kbs.length ? form.kbs.join(", ") : "无"],
              ["技能", form.skills.length ? form.skills.join(", ") : "无"],
              ["渠道", form.channels.join(", ")],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between py-2 border-b border-border last:border-0">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-medium">{value}</span>
              </div>
            ))}
          </div>
          <button
            onClick={handleCreate}
            className="w-full mt-6 bg-blue-500 text-white py-3 rounded-lg font-semibold hover:bg-blue-600 transition-colors"
          >
            🚀 创建场景
          </button>
        </div>
      )}

      {/* Navigation */}
      {step < 4 && (
        <div className="flex justify-between mt-8">
          <button
            onClick={() => setStep(step - 1)}
            disabled={step === 0}
            className="flex items-center gap-1 px-4 py-2 text-sm border rounded-lg disabled:opacity-30"
          >
            <ArrowLeft size={16} /> 上一步
          </button>
          <button
            onClick={() => setStep(step + 1)}
            disabled={step === 0 && !form.name}
            className="flex items-center gap-1 px-4 py-2 text-sm bg-blue-500 text-white rounded-lg disabled:opacity-30"
          >
            下一步 <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
