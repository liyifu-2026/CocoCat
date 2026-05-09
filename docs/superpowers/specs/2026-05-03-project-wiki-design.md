# Project Wiki Design

## Goal

Create a comprehensive `docs/wiki/` directory for CocoCat that serves both new contributors (onboarding) and experienced maintainers (reference).

## Structure

```
docs/wiki/
├── README.md                         ← Wiki 入口
├── GLOSSARY.md                       ← 术语表
│
├── 00-概述/                          ← 面向所有人
│   ├── 01-项目简介.md
│   ├── 02-快速开始.md
│   ├── 03-开发环境搭建.md
│   └── 04-项目结构.md
│
├── 01-教程/                          ← 面向新用户：跟着做
│   ├── 01-第一次对话.md
│   ├── 02-雇佣第一个Agent.md
│   └── 03-管理知识库.md
│
├── 02-操作指南/                      ← 面向维护者：解决问题
│   ├── 01-添加新工具.md
│   ├── 02-接入新渠道.md
│   ├── 03-配置Agent.md
│   ├── 04-部署到服务器.md
│   └── 05-调试Agent行为.md
│
├── 03-参考/                          ← 面向所有人：查资料
│   ├── 01-系统架构.md
│   ├── 02-数据流.md
│   ├── 03-Agent生命周期.md
│   ├── 04-配置清单.md
│   ├── 05-工具列表.md
│   ├── 06-API端点.md
│   ├── 07-Rust核心模块.md
│   ├── 08-Python运行时.md
│   ├── 09-前端页面.md
│   ├── 10-记忆系统.md
│   ├── 11-知识库系统.md
│   ├── 12-场景系统.md
│   ├── 13-渠道系统.md
│   ├── 14-雇佣系统.md
│   ├── 15-权限与安全模型.md
│   └── 16-测试指南.md
│
├── 04-解释/                          ← 面向深度用户：理解设计
│   ├── 01-为什么Rust+Python.md
│   ├── 02-ReAct循环设计.md
│   ├── 03-记忆系统设计原理.md
│   ├── 04-安全模型设计.md
│   ├── 05-场景隔离设计.md
│   ├── 06-关键设计决策.md
│   └── 07-参考项目说明.md
│
└── 05-维护/
    ├── 01-CICD流程.md
    ├── 02-排错指南.md
    ├── 03-参与贡献.md
    └── 04-更新日志.md
```

## Writing Standards

Each file follows the same header format:

```markdown
# 标题

> **受众：** [新用户 / 维护者 / 所有人]  
> **前提：** [需要先读什么]  
> **目标：** [读完能做什么]
```

## File Count

Total: ~35 files across 6 sections

## Priority

Write in order: 概述 (4) → 参考 (16) → 教程 (3) → 操作指南 (5) → 解释 (7) → 维护 (4) → 词汇表 (1) → README
