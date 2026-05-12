# Scene Rail Design

## Left Rail（从 CompanyRail 改造为 SceneRail）

```
┌─────┐
│  C  │  ← Brand logo，点击 → Dashboard（全局）
├─────┤
│  G  │  ← 场景图标，自动取首字母 + 颜色
│  C  │  ← 场景图标
│  M  │  ← 场景图标
│  +  │  ← 创建/导入场景
├─────┤
│ 🌙  │  ← 暗/亮切换（全局）
└─────┘
```

### 场景图标
- **默认**：取场景 ID 首字母大写 + 确定性颜色（从场景 ID hash 映射到 8 色之一）
- **可自定义**：在场景详情页的"显示配置"中，选择 19 个 SVG 图标之一 + 8 色之一
- 复用 AgentAvatar 的图标库（`avatars.tsx`）

### 行为
- 点击场景图标 → 导航到 `/scenes/{id}`
- 当前活跃场景 → 高亮态（`bg-sidebar-accent`）
- 场景列表变化时 Rail 自动刷新

## 场景导入（4 种方式）

### 1. 从路径导入
用户输入一个本地目录路径（如 `/home/user/scenes/my-scene/`），系统扫描并识别场景结构：
- `CONTEXT.md` → 场景上下文
- `roster.json` → 成员列表
- `mounted_kbs.json` → 挂载的知识库
- `skills/manifest.json` → 环境技能
- `entries.json` → 接入配置

### 2. 从 ZIP 导入
用户通过文件选择器上传 `.zip`，解压后导入规则同"从路径导入"

### 3. 从 Git 导入
用户输入 Git 仓库 URL，`git clone` 到 `scenes/` 下

### 4. 创建新场景
调用已有的 `NewSceneDialog`（已通过 DialogProvider 注册）

### 导入对话框 UI
```
┌─────────────────────────────────┐
│   导入场景                      │
│                                 │
│  ○ 从路径  ○ 从 ZIP  ○ 从 Git  │
│                                 │
│  [路径输入框 / 文件选择 / URL]  │
│                                 │
│  [扫描结果预览]                 │
│  ├ 场景 ID: marketing           │
│  ├ 上下文: 200 chars...         │
│  ├ Agent: 3 名                  │
│  └ 知识库: 2 个                 │
│                                 │
│     [取消]        [导入]        │
└─────────────────────────────────┘
```

## 场景显示配置

在 `SceneDetail` 页面新增"Display"设置区域：

| 字段 | 类型 | 默认 |
|------|------|------|
| 图标 | AvatarPicker（19 SVG icons） | 首字母 |
| 颜色 | 8 色选择器 | 从 ID hash |
| 别名 | nickname | 场景 ID |

存储到 `scenes/{id}/display.json`

## 数据流

```
SceneRail
  ├─ useQuery(["scenes"]) → 读取场景列表
  ├─ useQuery(["scene-display", id]) → 读取各场景显示配置
  └─ onClick → navigate(`/scenes/${id}`)

ImportDialog
  ├─ 方式选择（path/zip/git）
  ├─ 文件扫描 / 解压 / clone
  ├─ 预检场景结构
  └─ 确认后调用 scenesApi.create() + 补充配置

SceneDetail 新增 Display 设置
  ├─ AvatarPicker 组件复用
  ├─ 颜色选择
  ├─ 别名输入
  └─ 保存到 scenes/{id}/display.json
```

## API

需要在 `routes/scenes.py` 中新增：

| 方法 | 路径 | 功能 |
|------|------|------|
| `POST` | `/api/scenes/import/path` | 从路径导入 |
| `POST` | `/api/scenes/import/zip` | 上传 ZIP 导入 |
| `POST` | `/api/scenes/import/git` | 从 Git 导入 |
| `GET` | `/api/scenes/{id}/display` | 获取场景显示配置 |
| `PUT` | `/api/scenes/{id}/display` | 更新场景显示配置 |

## Sidebar 上下文感知

第二栏（Sidebar）根据当前路由切换内容：

### 全局模式（`/dashboard`, `/agents`, `/chat` 等）

显示现有全局导航（Dashboard / Workspace / Management 分组），与当前一致。

### 场景模式（`/scenes/:id` 以及未来的 `/scenes/:id/...`）

Sidebar 切换为场景专属导航：

```
Scene: Marketing              ← 场景名 + 图标
[← Back to Scenes]            ← 返回场景列表
───
📝 Context                    ← 场景上下文查看/编辑
👥 Roster                     ← 成员管理
🔧 Skills                     ← 环境技能
📚 Knowledge Bases            ← 挂载知识库
🔌 Entries                    ← 接入配置
🎨 Display                    ← 图标/颜色/别名设置
```

### 切换逻辑

```
Sidebar.tsx
  ├─ useLocation() 检测当前路由
  ├─ 如果是 /scenes/:id 开头 → 场景模式
  │   ├─ 从 URL 提取 sceneId
  │   ├─ useQuery(["scenes"]) 找到场景名
  │   ├─ useQuery(["scene-display", id]) 获取图标/颜色
  │   └─ 渲染场景导航菜单
  └─ 否则 → 全局模式（现有逻辑）
```

### 布局结构（刷新后）

```
[SceneRail 44px] [Sidebar 220px: 场景导航] [Main + BreadcrumbBar + PropertiesPanel]
```

- 从 Rail 点击场景 → 跳转到 `/scenes/{id}`
- Sidebar 自动切换到场景模式
- BreadcrumbBar 显示 `Scenes > scene-name > Context`
- PropertiesPanel 显示场景摘要（已有）

## 已存复用

| 已有 | 复用方式 |
|------|----------|
| `avatars.tsx` 19 SVG 图标 | SceneAvatarPicker |
| `AvatarPicker` 组件 | 直接复用 |
| `AgentAvatar` 组件 | 改名为共用 `EntityAvatar` 或保留 |  
| `NewSceneDialog` | 作为导入对话框的"新建"选项 |
| `DialogProvider` | ImportDialog 通过 DialogProvider 控制 |
