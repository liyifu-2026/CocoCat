# CocoCat 设置界面重设计

日期: 2026-05-14
状态: 待确认
参考: hanako `SettingsNav.tsx`, `ProvidersTab.tsx`, `ApiKeyCredentials.tsx`, `ProviderDetail.tsx`, `provider-presets.ts`

## 改动范围

| CocoTab | 参考 hanako | 改动 |
|---------|------------|------|
| **供应商** Providers | ProvidersTab + ProviderDetail + ApiKeyCredentials | 大改：两栏布局，16 provider，verify，add custom |
| **外观** Interface | Interface 的 section card 样式 | 微调：当前是 select 下拉，改为卡片式选项 |
| **左侧导航** SettingsNav | TAB_ITEMS 的 icon+文字 模式 | 加 icon，当前纯文字 |

## 1. 供应商 (Providers) — 大改

### 布局

```
┌──────────────────────────────────────────────────────────┐
│  左栏 (33%)                         右栏 (flex:1)        │
│                                                          │
│  AI Providers                       DeepSeek             │
│   ● DeepSeek      (configured)      ─────────────────    │
│   ● OpenAI        (configured)      API Key  [......] 🔗 │
│   ○ Gemini        (dim, not set)    Base URL [url...] 🔒 │
│   ○ Groq          (dim, not set)    ─────────────────    │
│   ○ Mistral       (dim, not set)    [Save]               │
│   ○ ...                                                    │
│                                                          │
│  + Add Custom Provider                                   │
└──────────────────────────────────────────────────────────┘
```

- **状态圆点**：● 绿色 = 已配置，○ 灰色 = 未配
- **已配置**：正常显示 + 模型数
- **未配置**：灰色 dimmed（opacity 0.45）
- **右栏**：点击左边 provider，右边出编辑表单
- **Base URL**：preset 只读，custom 可编辑
- **Verify 按钮** 🔗：`GET {base_url}/models` → 200/401/403 判断

### 后端

`GET /api/providers` — 扩展返回 `base_url`, `env_key`。

`PUT /api/providers/key` — 新增。写入 `config/auth.json`。

`POST /api/providers/test` — 新增。抄 hanako `probeProvider`：
```python
resp = httpx.get(f"{base_url}/models", headers={"Authorization": f"Bearer {key}"})
# 200 = ok, 401/403 = fail
```

### Provider 列表（16 个，抄 hanako）

| name | display_name | base_url | env_key |
|------|-------------|----------|----------|
| openai | OpenAI | https://api.openai.com/v1 | OPENAI_API_KEY |
| deepseek | DeepSeek | https://api.deepseek.com | DEEPSEEK_API_KEY |
| anthropic | Anthropic | https://api.anthropic.com | ANTHROPIC_API_KEY |
| gemini | Google Gemini | https://generativelanguage.googleapis.com/v1beta | GEMINI_API_KEY |
| dashscope | DashScope (Qwen) | https://dashscope.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY |
| zhipu | Zhipu (GLM) | https://open.bigmodel.cn/api/paas/v4 | ZHIPU_API_KEY |
| siliconflow | SiliconFlow | https://api.siliconflow.cn/v1 | SILICONFLOW_API_KEY |
| groq | Groq | https://api.groq.com/openai/v1 | GROQ_API_KEY |
| mistral | Mistral | https://api.mistral.ai/v1 | MISTRAL_API_KEY |
| moonshot | Moonshot (Kimi) | https://api.moonshot.cn/v1 | MOONSHOT_API_KEY |
| volcengine | Volcengine (Doubao) | https://ark.cn-beijing.volces.com/api/v3 | VOLCENGINE_API_KEY |
| openrouter | OpenRouter | https://openrouter.ai/api/v1 | OPENROUTER_API_KEY |
| minimax | MiniMax | https://api.minimax.chat/v1 | MINIMAX_API_KEY |
| ollama | Ollama (Local) | http://localhost:11434/v1 | — |

### 后端 API

| Method | Path | 说明 | 参照 hanako |
|--------|------|------|------------|
| GET | `/api/providers` | 返回 `{name, display_name, base_url, has_key, models}` | `GET /api/providers/summary` |
| PUT | `/api/providers/key` | 保存 API key → `config/auth.json` | `PUT /api/config` |
| POST | `/api/providers/test` | `GET {base_url}/models` → ok/fail | `POST /api/providers/test` → `probeProvider()` |
| POST | `/api/providers/fetch-models` | `GET {base_url}/models` → parse model IDs → cache | `POST /api/providers/fetch-models` |
| GET | `/api/providers/{name}/models` | 返回已保存+已发现的模型列表 | `GET /api/providers/{name}/discovered-models` |
| PUT | `/api/providers/{name}/models` | 增删模型 `{action:"add/remove", model_id:"..."}` | `PUT /api/config` providers.models |

### 前端组件

| 组件 | 参照 hanako | 说明 |
|------|------------|------|
| `ProvidersTab` | `ProvidersTab.tsx` | 两栏布局，左列表右详情 |
| `ProviderDetail` | `ProviderDetail.tsx` | 右侧：API key + Base URL + Models |
| `ApiKeyCredentials` | `ApiKeyCredentials.tsx` | Key 输入 + verify 按钮 + save |
| `ProviderModelList` | `ProviderModelList.tsx` | 模型标签 + 删除 + 搜索下拉 + 添加 + fetch |
| `AddProviderOverlay` | `AddProviderForm` in ProviderList.tsx | 覆盖层：Name + URL + Key + API format + Save |
| `AppearanceTab` | hanako Interface tab | 卡片式主题/语言选择 |
| SettingsNav | `SettingsNav.tsx` `TAB_ITEMS` | icon + 文字导航 |

### "+ Add Custom Provider" overlay

点击 left 列表底部按钮 → 弹出 overlay 覆盖白卡区域：
- Name 输入框
- Base URL 输入框
- API Key 输入框
- Save 按钮
- 参照 hanako `AddProviderOverlay`

## 2. 外观 (Interface) — 微调

当前是 select 下拉，改为卡片式选项（参考 hanako 的 Interface tab）：

```
┌──────────────────────────────────────────────┐
│ Theme                                        │
│ ┌─────────┐  ┌──────────┐                   │
│ │ ☀️ Light │  │ 🌙 Dark  │                   │
│ │   (●)   │  │         │                   │
│ └─────────┘  └──────────┘                   │
│                                              │
│ Language                                     │
│ ┌───────────┐  ┌─────────┐                  │
│ │ English   │  │ 中文    │                  │
│ │   (●)    │  │         │                  │
│ └───────────┘  └─────────┘                  │
└──────────────────────────────────────────────┘
```

## 3. 左侧导航 — 加 icon

当前样式：
```
nav className="w-44 ..."
  button: "智能体" "供应商" "场景" ...
```

改为：
```
nav className="w-48 ..."
  button: 🔷 智能体
  button: 🔌 供应商
  button: ...
```

icon 用 lucide-react 已有图标（`Cpu`, `Plug`, `Layers`, `Wrench`, `Book`, `Radio`, `Palette`, `Settings`）。

## 文件变更

| 文件 | 改动 |
|------|------|
| `cococat/routes/providers.py` | 新增 6 个 endpoint（key save / test / fetch-models / model CRUD） |
| `cococat/providers/registry.py` | 新增 7 个 provider（14→现有7=增7），加 `base_url` 和 `env_key` |
| `web-ui/src/components/SettingsModal.tsx` | 重写 ProvidersTab（两栏） + 微调 AppearanceTab（卡片） + 左侧导航加 icon |
| `cococat/tests/test_providers_api.py` (新) | provider key save / test / fetch-models / model CRUD 测试 |

总计约 500 行新代码。