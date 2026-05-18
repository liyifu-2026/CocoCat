---
type: entity
title: E2B SDK
created: 2024-07-20
summary: AI Agent 领域流行的沙箱 SDK，定义了沙箱创建、管理和交互的标准 API。CubeSandbox 在接口层完全兼容此 SDK，实现无缝替换。
---
# E2B SDK

**E2B SDK** 是 AI Agent 社区广泛使用的沙箱软件开发工具包，它为开发者提供了一套标准的接口来创建、控制和销毁沙箱实例。[[CubeSandbox]] 在 API 层面完全遵循该规范，旨在成为 E2B 服务的“即插即用”替代方案。

## 兼容性设计

通过完全兼容 E2B SDK，CubeSandbox 实现了 [[完全兼容 E2B]] 的战略目标：

- **零代码改动**：用户的 Agent 代码无需修改，只需将 SDK 的配置中的 API 地址指向 CubeSandbox 服务端点。
- **生态复用**：所有围绕 E2B SDK 构建的工具、社区例程和文档可直接应用。
- **低成本迁移**：降低了从其他沙箱服务迁入的技术门槛，用户可无缝体验 CubeSandbox 的[[毫秒级冷启动]]和[[硬件级强隔离]]。

## 相关资源

- 官方 E2B 文档与 SDK 仓库
- [[CubeSandbox]] 快速开始指南