---
type: concept
title: 完全兼容 E2B
created: 2024-07-20
summary: CubeSandbox 的市场策略与工程设计，通过服务端完全遵循 E2B SDK 规范，实现用户应用零改动迁移。
---
# 完全兼容 E2B

**完全兼容 E2B** 是指 [[CubeSandbox]] 在 API 层面与 [[E2B SDK]] 保持严格的一致，使其成为 E2B 服务的即时替代品（Drop-in replacement）。

## 兼容性实现

- **API 规范**：CubeSandbox 服务端实现了 E2B 定义的所有必需 gRPC/REST 接口，包括沙箱创建、执行命令、文件传输、销毁等。
- **环境变量切换**：用户端（使用 E2B SDK 的 Python/JavaScript 代码）只需修改 SDK 初始化时传入的 `api_url` 等参数，指向自己的 CubeSandbox 部署地址，无需修改任何业务逻辑。
- **行为一致性**：CubeSandbox 力求在行为细节上也保持一致，例如错误码、事件流格式等。

## 战略意义

这个策略允许 CubeSandbox 直接面向现有的 E2B 用户社区，以更优的性能（[[毫秒级冷启动]]）、更强的安全（[[硬件级强隔离]]）和更低的资源开销（[[高密度部署]]）作为吸引力，提供免费的开源选择，推动市场迁移。

## 相关组件

- [[E2B SDK]]
- [[CubeSandbox]]