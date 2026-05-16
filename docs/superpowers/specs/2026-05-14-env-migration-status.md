# 环境迁移状态：WSL2 → Arch Linux → Debian

日期: 2026-05-14（更新：迁移至 Debian）

## 迁移概述

WSL2 → Arch Linux 裸金属（解决 KVM）→ Debian 13 裸金属（解决内存不足）。最终为 CubeSandbox 部署创造条件。

## 环境状态

| 项目 | 状态 | 说明 |
|------|------|------|
| 操作系统 | ✅ Debian 13 | trixie, x86_64 |
| 内存 | ✅ 15GB | 满足 CubeSandbox ≥8GB 要求 |
| KVM | ✅ 可用 | Intel KVM (`/dev/kvm`, kvm_intel) |
| Python | ✅ 3.13.5 | venv 已创建 (`.venv/`) |
| pip 依赖 | ✅ | pyproject.toml 全量安装 + python-multipart |
| pytest | ✅ 130 通过 | `cococat/tests/` 全绿 |
| Playwright | ✅ | Chromium 已下载 |
| Node.js | ✅ v24.15.0 | npm 11.12.1 |
| 前端构建 | ✅ | `npm run build` 零 Error |

## CubeSandbox 安装尝试

### 方案：QEMU Dev Env（README 推荐）

按照 CubeSandbox README 的 dev-env 流程：

1. ✅ `prepare_image.sh` — 下载 OpenCloudOS qcow2，制成 100G 金镜像
2. ✅ `run_vm.sh` — QEMU/KVM 启动 VM（端口转发 10022→22, 13000→3000）
3. ⚠️ `online-install.sh` — 安装过程被内存限制阻塞

### 内存情况（已解决）

~~Arch Linux 宿主机内存: 7.5GB total → QEMU VM 分配 8GB OOM kill → 分配 4GB cubelet OOM kill~~

Debian 宿主机内存: **15GB total**。QEMU VM 可分配 8GB，满足 CubeSandbox 要求。内存瓶颈已消除。

CubeSandbox 部署现可继续：直接复用之前的 QEMU VM 方案（`run_vm.sh` + `online-install.sh`），或尝试宿主机直装。

## Agent Skills 安装

| 来源 | 数量 | 位置 |
|------|------|------|
| mattpocock/skills | 14 | `.agents/skills/` |
| obra/superpowers | 14 | `.agents/skills/` |
| **合计** | **28** | |

关键 skill：`brainstorming`, `tdd`, `diagnose`, `grill-with-docs`, `improve-codebase-architecture`, `subagent-driven-development`, `using-superpowers` 等。

## 测试状态

```
cococat/tests/ — 151 passed, 0 failed
tests/        — 24 collection error (旧模块引用，代码已重写，无影响)
```

## 待做事项

| # | 事项 | 状态 | 阻塞 |
|---|------|------|------|
| 1 | Auto-Dream（记忆自动提取） | ✅ 完成 | 151 测试通过 |
| 2 | pip 依赖 + pytest + Playwright 恢复 | ✅ 完成 | — |
| 3 | 前端 `npm install` + 构建验证 | ✅ 完成 | — |
| 4 | CubeSandbox 部署 | ✅ 完成 | `tpl-dedcd9373c3f49939f7feb9b`, 端到端验证通过 |
| 5 | CocoChat bash tool → CubeSandbox 集成 | ✅ 完成 | `--cube-sandbox` CLI flag, sandbox_run 注入 |
| 6 | Main AI vs sub-agent 工具权限分离 | ✅ 已完成 | create_main_ai_tools vs create_core_tools |

## 相关文档

- `docs/superpowers/specs/2026-05-12-architecture-brainstorm.md` — 架构脑暴 + 进度
- `docs/superpowers/specs/2026-05-13-grill-decisions.md` — 决策记录
- `docs/superpowers/specs/2026-05-14-work-log.md` — 工作记录
- `docs/superpowers/specs/2026-05-14-auto-dream-design.md` — Auto-Dream 设计（待开工）
- `/home/leaif/Projects/README_zh.md` — CubeSandbox 安装指南
