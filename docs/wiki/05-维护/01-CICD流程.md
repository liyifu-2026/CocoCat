---
title: CI/CD 流程
sidebar_position: 1
---

# CI/CD 流程

CocoCat 使用 GitHub Actions 进行持续集成和自动化测试。

## 工作流文件

位置：`.github/workflows/ci.yml`

## 触发条件

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

每次向 `main` 分支推送或创建 PR 时触发。

## 并行任务

CI 包含 2 个独立的并行 job：

### 1. Python 测试

```yaml
python:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Install deps
      run: |
        pip install -r requirements-dev.txt 2>/dev/null || true
        pip install pytest
    - name: Test
      run: |
        cp .env.example .env 2>/dev/null || true
        python -m pytest tests/ -v
```

- 使用 Python 3.12
- 复制 `.env.example` 为 `.env` 确保环境变量就绪
- 运行 `tests/` 下的所有 Python 测试
- 不安装缺失的 `requirements-dev.txt`（容错）

### 2. 前端 Lint + TypeScript 检查

```yaml
frontend:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: web-ui
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
    - name: Install deps
      run: npm ci 2>/dev/null || npm install
    - name: Lint
      run: npx eslint src/ 2>/dev/null || true
    - name: Build
      run: npx tsc --noEmit 2>/dev/null || true
```

- 使用 Node.js 20
- ESLint 代码规范检查
- TypeScript 类型检查（`tsc --noEmit`）
- 容错处理：ESLint 或 tsc 失败不阻断流程

## 运行流水线

首次设置时需确保：
1. GitHub 仓库已创建
2. Actions 功能已启用
3. secrets 已配置（如需）

## 本地运行测试

```bash
# Python 测试
cp .env.example .env
python -m pytest tests/ -v

# 前端检查
cd web-ui
npx eslint src/
npx tsc --noEmit
```
