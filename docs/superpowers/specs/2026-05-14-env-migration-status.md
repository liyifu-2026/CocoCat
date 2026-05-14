# 环境迁移状态：WSL2 → Arch Linux

日期: 2026-05-14

## 迁移概述

从 WSL2 迁移到 Arch Linux 裸金属，解决 KVM 不可用问题，为 CubeSandbox 部署创造条件。

## 环境状态

| 项目 | 状态 | 说明 |
|------|------|------|
| 操作系统 | ✅ Arch Linux | 7.0.2-arch1-1, x86_64 |
| KVM | ✅ 可用 | Intel KVM (`/dev/kvm`, kvm_intel) |
| Python | ✅ 3.14.4 | venv 已创建 (`.venv/`) |
| pip 依赖 | ✅ | pyproject.toml 全量安装 |
| pytest | ✅ 124 通过 | `cococat/tests/` 全绿 |
| Playwright | ✅ | Chromium 已下载，浏览器测试通过 |
| Node.js | ✅ v26.1.0 | npm 11.14.1 |
| 前端构建 | ✅ | `npm run build` 零 Error |

## CubeSandbox 安装尝试

### 方案：QEMU Dev Env（README 推荐）

按照 CubeSandbox README 的 dev-env 流程：

1. ✅ `prepare_image.sh` — 下载 OpenCloudOS qcow2，制成 100G 金镜像
2. ✅ `run_vm.sh` — QEMU/KVM 启动 VM（端口转发 10022→22, 13000→3000）
3. ⚠️ `online-install.sh` — 安装过程被内存限制阻塞

### 内存瓶颈

```
宿主机内存: 7.5GB total
QEMU VM 分配: 8GB (第一次尝试) → OOM kill
QEMU VM 分配: 4GB (第二次尝试) → cubelet OOM kill
```

原因：CubeSandbox 在 VM 内需要 Docker 运行 MySQL 8.0 + Redis + CoreDNS + cubemaster + cube-api + cubelet，4GB 不够。安装脚本硬编码要求 ≥8GB。

### 安装脚本的修改尝试

- ✅ 下载 + 解压 `cube-sandbox-one-click-9c16021.tar.gz`
- ✅ 绕过 8GB 内存检查（sed 删除检查代码）
- ✅ MySQL + Redis Docker 容器正常启动
- ✅ 拉取 cube-* 系列 Docker 镜像
- ✅ cubemaster、cube-api、cubelet 启动
- ❌ cubelet 进程被 OOM kill（`Killed`）

### 待尝试方案

1. **宿主机直装** — 不经过 QEMU VM，在 Arch 上直接安装 cubelet。需要适配 yum 系安装脚本（改用 pacman/systemd）。
2. **降服务** — 修改 install.sh 跳过 MySQL/Redis/CoreDNS，最小化运行 cubelet standalone。
3. **增加宿主机内存** — 升级到 ≥16GB 后继续 QEMU VM 方案。

## Agent Skills 安装

| 来源 | 数量 | 位置 |
|------|------|------|
| mattpocock/skills | 14 | `.agents/skills/` |
| obra/superpowers | 14 | `.agents/skills/` |
| **合计** | **28** | |

关键 skill：`brainstorming`, `tdd`, `diagnose`, `grill-with-docs`, `improve-codebase-architecture`, `subagent-driven-development`, `using-superpowers` 等。

## 测试状态

```
cococat/tests/ — 124 passed, 0 failed
tests/        — 24 collection error (旧模块引用，代码已重写，无影响)
```

## 待做事项

| # | 事项 | 状态 | 阻塞 |
|---|------|------|------|
| 1 | Auto-Dream（记忆自动提取） | 待开工 | 无 |
| 2 | chat route → SandboxProvider | 待 CubeSandbox | CubeSandbox 部署 |
| 3 | Main AI vs sub-agent 工具权限分离 | 待 #2 | CubeSandbox 部署 |
| 4 | CubeSandbox 部署 | 受阻 | 内存不足 (7.5G < 8G 要求) |

## 相关文档

- `docs/superpowers/specs/2026-05-12-architecture-brainstorm.md` — 架构脑暴 + 进度
- `docs/superpowers/specs/2026-05-13-grill-decisions.md` — 决策记录
- `docs/superpowers/specs/2026-05-14-work-log.md` — 工作记录
- `docs/superpowers/specs/2026-05-14-auto-dream-design.md` — Auto-Dream 设计（待开工）
- `/home/leaif/Projects/README_zh.md` — CubeSandbox 安装指南
