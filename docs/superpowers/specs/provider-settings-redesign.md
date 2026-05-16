# Provider Settings 重设计

## 决策记录

| # | 问题 | 决策 |
|---|------|------|
| 1 | 核心功能 | 填 key → 自动测 → 选模型（模型分配另页） |
| 2 | 供应商信息 | Logo 字母 + 名字 + 绿/灰状态灯 + 模型数 |
| 3 | 供应商来源 | 内置 14 个（硬编码 BUILTIN_PROVIDERS）+ 用户自定义存 JSON |
| 4 | Key 交互 | 「保存并测试」合体按钮，先存盘再自动测 |
| 5 | 模型管理 | 左右双栏（可用/已启用）+ 拖拽 + 箭头按钮 + 手动输入 |
| 6 | 自定义供应商 | 右侧面板内联表单，不弹窗 |
| 7 | Base URL | 全部可编辑（内置也可改，防 URL 过时） |

---

## 后端改动

### 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `PUT` | `/api/providers/{name}/config` | 保存/更新自定义供应商的 base_url |
| `DELETE` | `/api/providers/{name}` | 删除自定义供应商（内置不可删） |
| `PUT` | `/api/providers/{name}/models/batch` | 批量更新模型列表（覆盖式） |

### 修改 API

| 方法 | 路径 | 变更 |
|------|------|------|
| `GET` | `/api/providers` | 合并内置 + 自定义供应商；返回字段加 `custom: bool`, `logo` |
| `PUT` | `/api/providers/key` | 存 key 后附带执行连通性测试，返回 `{saved, ok, error?, status}` |
| `GET` | `/api/providers/{name}/models` | 返回 `{available: [...], enabled: [...], default: "..."}` 结构化模型数据 |

### 数据存储

```
config/providers.json   ← 用户自定义供应商（数组，每个含 name, display_name, base_url）
config/models.json      ← 现有，不变（每个 provider 的启用模型列表）
config/auth.json        ← 现有，不变（API key 存储）
```

### 自定义供应商格式 (`config/providers.json`)

```json
[
  {
    "name": "my-llm",
    "display_name": "My LLM",
    "base_url": "https://api.example.com/v1",
    "env_key": "MY_LLM_API_KEY"
  }
]
```

### 内置供应商不可删除

`DELETE /api/providers/{name}` 检查是否在内置列表中，是则返回 403。

---

## 前端改动

### 文件：`web-ui/src/components/SettingsModal.tsx`

#### 左侧供应商列表

- 每组供应商：首字母 Logo（36×36 圆角方块，按首字母分配颜色）+ 名字 + 模型数（仅已配置显示）+ 绿/灰状态灯
- 已配置排前、未配置排后、各自按名字排序
- 选中态：蓝色边框 + 浅蓝底色
- 底部「+ 自定义供应商」按钮

#### 右侧详情面板

**Header**：Logo + 名称 + Base URL 预览 + 连接状态 badge

**API Key 行**：
- 密码框（带显示/隐藏切换）
- 「保存并测试」按钮 → 调用 `PUT /api/providers/key` → 后端存盘 + 自动测试 → 返回结果
- 通过：绿色状态行 "连接正常 · 最后测试：刚刚"
- 失败：红色状态行 "连接失败 · {错误原因}"

**Base URL 行**：
- 可编辑输入框（内置和自定义全可改）
- 失焦自动保存 → `PUT /api/providers/{name}/config`

**模型区域**（h: 210px）：

```
┌──────────────────┬──┬──────────────────┐
│ 可用模型         │⏩│ 已启用 · 2       │
│                  │▶ │                  │
│ ☐ deepseek-chat  │◀ │ ● deepseek-chat  │ ← 默认，蓝色圆点
│ ☐ deepseek-r1    │⏪│ ○ deepseek-v4    │ → 设为默认
│                  │  │                  │
│                  │  │ [手动输入...]     │
└──────────────────┴──┴──────────────────┘
```

交互：
- 左栏 checkbox 勾选 + 点击 ▶ 批量移入；⏩ 全部移入
- 右栏 × 删除逐个移出；◀ 批量移出；⏪ 全部移出
- 拖拽：左栏项拖到右栏 = 移入；右栏项拖到左栏 = 移出
- "设为默认"：点击后该模型标蓝，其余解除
- 手动输入框：输入模型名 → Enter 直接加到已启用

**移除 API Key**：
- 底部红色文字按钮，点击确认后清空 key 并将模型列表重置

#### 自定义供应商表单

- 点击「+ 自定义供应商」→ 左侧追加临时项 "新供应商" → 自动选中
- 右侧展示表单：Name + Base URL + API Key（三项必填）
- 填完自动保存 → 出现在左侧正式列表

---

## 实现步骤

1. 后端：新增 `PUT /api/providers/{name}/config`、`DELETE /api/providers/{name}`、`PUT /api/providers/{name}/models/batch`
2. 后端：修改 `PUT /api/providers/key` 附带连通性测试
3. 后端：修改 `GET /api/providers` 合并自定义供应商
4. 后端：修改 `GET /api/providers/{name}/models` 返回结构化模型数据
5. 前端：重写 `ProvidersTab` → 左侧列表（Logo + 状态灯 + 模型数）
6. 前端：重写 `ProviderDetailPanel` → Key + Base URL + 双栏模型管理
7. 前端：自定义供应商表单
8. 测试

---

## 不在此范围

- 模型分配（Main AI vs Sub-agent 模型绑定）→ 在 Agents 设置页单独处理
- 用量统计 / 计费 → 后续迭代
- Key 加密存储 → 后续迭代（当前明文存 auth.json）

## 参考 Demo

`/tmp/provider-demo.html` — 交互原型，展示了列表样式、Key 输入、双栏模型管理的完整交互流程。
