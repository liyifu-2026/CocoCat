# Web UI Frontend 修复计划

总计 27 个问题，按优先级分 4 个阶段。

---

## 阶段一：修复构建失败（P0）

### 1. 创建 PanelContext.tsx
- **文件**: `src/context/PanelContext.tsx`（缺失）
- **症状**: `PropertiesPanel.tsx` 导入 `usePanel` 导致构建 TS2307
- **修复**: 创建 `PanelContext.tsx`，提供 `content`, `visible`, `closePanel` 状态
- **估计**: ~30 行

### 2. 修复 mermaid 类型声明
- **文件**: `src/components/MermaidBlock.tsx:17`
- **症状**: 动态 `import("mermaid")` 缺少类型声明，构建 TS2307
- **修复**: 安装 `@types/mermaid` 或添加 `src/mermaid.d.ts` 模块声明
- **估计**: 1 行声明

### 3. 统一 tsconfig 配置
- **文件**: `tsconfig.json` vs `tsconfig.app.json`
- **症状**: `noUnusedLocals` 不一致（一个 false 一个 true），`tsc -b` 会用 strict 的那个
- **修复**: 对齐配置，确保构建通过
- **估计**: 2 行改动

---

## 阶段二：修复路由与导航（P0）

### 4. 添加缺失路由页面
- **文件**: `src/App.tsx`
- **症状**: `SceneRail` 和 `MobileBottomNav` 导航到 `/dashboard`, `/agents`, `/scenes` 但路由不存在
- **修复**: 添加路由和占位页面（或重定向到 `/chat`）
- **方案 A**: 为每个路由创建 stub page 组件
- **方案 B**: 将所有不存在路由重定向到 `/chat`
- **估计**: 10-20 行

### 5. MobileBottomNav 从未渲染
- **文件**: `src/components/MobileBottomNav.tsx`
- **症状**: 定义但无处引用，死代码
- **修复**: 在 `Layout.tsx` 中集成，或删除该文件
- **估计**: 5 行

---

## 阶段三：修复核心功能（P1）

### 6. 修复国际化系统
- **文件**: `src/context/LanguageContext.tsx`, `src/i18n/en.ts`, `src/i18n/zh.ts`
- **症状**: LanguageContext 只用内联 16 个键，`i18n/en.ts`/`zh.ts` 完全未被引用
- **修复**:
  - 删除 LanguageContext 内联 translations
  - 导入并使用 `i18n/en.ts`（或根据语言设置切换）
  - 添加语言切换状态（localStorage 持久化）
- **估计**: ~60 行

### 7. 合并 Chat.tsx WebSocket
- **文件**: `src/pages/Chat.tsx`
- **症状**: 单独创建第二个 `/ws` 连接，与 LiveUpdatesContext 重复
- **修复**: 删除 Chat.tsx 中独立的 WebSocket 逻辑；改为监听 `streamState` Map 或通过 LiveUpdatesContext 获取流式数据
- **估计**: ~40 行

### 8. 修复 Chat.tsx 的流式消息竞态
- **文件**: `src/pages/Chat.tsx`
- **症状**: `data.reply || streamText` 存在竞态；`send()` 闭包捕获过时 state
- **修复**: 用 `useRef` 替代 `streamText` state 用于非渲染数据流；确保 POST 响应后不再使用 streamText
- **估计**: ~20 行

### 9. Chat.tsx 支持 HTTPS WebSocket
- **文件**: `src/pages/Chat.tsx:25`
- **症状**: `ws://${location.host}/ws` 在 HTTPS 下报 Mixed Content
- **修复**: 同 LiveUpdatesContext — 检测 `location.protocol` 选择 `wss:` 或 `ws:`
- **估计**: 3 行

### 10. Chat.tsx 添加认证检查
- **文件**: `src/pages/Chat.tsx`
- **症状**: 未检查 `useAuth().isAuthenticated`
- **修复**: 页面顶部添加 `if (!isAuthenticated) return <LoginPrompt />`
- **估计**: 10 行

### 11. 修复 AppearanceTab 主题选择
- **文件**: `src/components/SettingsModal.tsx:261-265`
- **症状**: `<select>` 没有 `onChange`，选择不生效
- **修复**: 添加 `onChange` 处理调用 `setTheme()`
- **估计**: 5 行

### 12. SceneDetail 按钮无操作
- **文件**: `src/pages/SceneDetail.tsx:50,61`
- **症状**: Add KB / Add Skill 的 `Plus` 按钮没有 `onClick`
- **修复**: 添加空函数或 TODO 提示，或接入 API
- **估计**: 5 行

---

## 阶段四：代码整洁与优化（P2）

### 13. Chat.tsx 用 `any` 类型
- **文件**: `src/pages/Chat.tsx`, `src/pages/SceneDetail.tsx`
- **修复**: 定义 `Message`、`Scene` 等接口替换 `any`
- **估计**: 15 行

### 14. Chat.tsx 消息列表 key 用索引
- **文件**: `src/pages/Chat.tsx:91`
- **修复**: 改用 `message.id` 或 `crypto.randomUUID()` 生成唯一 key
- **估计**: 3 行

### 15. Chat.tsx 对话历史无交互
- **文件**: `src/pages/Chat.tsx:79-83`
- **修复**: 点击历史条目时填充输入框或滚动到该消息
- **估计**: 8 行

### 16. ScheduleModal 数据硬编码
- **文件**: `src/components/ScheduleModal.tsx:10-13`
- **修复**: 改为 API 请求 `/api/schedule/tasks`
- **估计**: 20 行

### 17. SettingsModal 重复切换请求
- **文件**: `src/components/SettingsModal.tsx:26-27`
- **修复**: 缓存已加载的 tab 数据，切换时不重复请求
- **估计**: 15 行

### 18. index.html 标题和 favicon
- **文件**: `index.html:7`
- **修复**: `<title>CocoCat</title>`, 添加正确 favicon
- **估计**: 2 行

### 19. FilterBar 事件重复触发
- **文件**: `src/components/FilterBar.tsx:41`
- **修复**: X 按钮用 `onMouseDown` 替代 `onClick`+`stopPropagation`，或调整事件冒泡逻辑
- **估计**: 3 行

### 20. LiveUpdatesContext 类型清理
- **文件**: `src/context/LiveUpdatesContext.tsx`
- **修复**: `reconnectTimerRef` 用 `ReturnType<typeof setTimeout>`
- **估计**: 2 行

---

## 修复顺序建议

```
阶段一 (P0) ──► 阶段二 (P0) ──► 阶段三 (P1) ──► 阶段四 (P2)
  构建通过          能导航          能用              更好
```

每个阶段完成后运行 `npm run build` 验证。
