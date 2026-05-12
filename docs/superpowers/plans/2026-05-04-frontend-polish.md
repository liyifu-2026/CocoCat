# Frontend Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fix all frontend maturity gaps - add error states, loading skeletons, fix Collaboration page, enhance Settings.

**Architecture:** Add ErrorBoundary wrapper + sonner toast system, then fix each page independently.

**Tech Stack:** React 19, TypeScript, TanStack Query, sonner, shadcn/ui

---

### File Structure
- web-ui/src/components/ErrorBoundary.tsx [NEW] - Global error boundary
- web-ui/src/components/ErrorState.tsx [NEW] - Reusable error state display
- web-ui/src/components/LoadingSkeleton.tsx [NEW] - Reusable loading skeletons
- web-ui/src/components/ui/sonner.tsx [NEW] - Sonner toast wrapper
- web-ui/src/App.tsx [MODIFY] - Add ErrorBoundary + Toaster
- web-ui/src/main.tsx [MODIFY] - Add QueryClient onError, retry config
- web-ui/src/pages/Dashboard.tsx [MODIFY] - Add loading skeletons + error state
- web-ui/src/pages/Agents.tsx [MODIFY] - Add skeleton + error state
- web-ui/src/pages/Scenes.tsx [MODIFY] - Add skeleton + error state
- web-ui/src/pages/Knowledge.tsx [MODIFY] - Add skeleton + error state
- web-ui/src/pages/TokenUsage.tsx [MODIFY] - Add skeleton + error state
- web-ui/src/pages/Hiring.tsx [MODIFY] - Add skeleton + error state + toast on approve/reject
- web-ui/src/pages/Collaboration.tsx [REWRITE] - Use api client, theme-aware, shadcn Button
- web-ui/src/pages/Settings.tsx [MODIFY] - Add LLM config, server info
- web-ui/package.json [MODIFY] - Add sonner dependency
