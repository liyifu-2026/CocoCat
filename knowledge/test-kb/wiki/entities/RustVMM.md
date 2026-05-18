---
type: entity
title: RustVMM
created: 2024-07-20
summary: 基于 Rust 语言实现的虚拟机监控器（VMM），与 KVM 配合构建轻量级虚拟机，是 CubeSandbox 实现硬件级隔离和高性能的核心虚拟化组件。
---
# RustVMM

**RustVMM** 是使用 Rust 语言编写的虚拟机监控器（Virtual Machine Monitor），作为 [[CubeSandbox]] 的底层虚拟化引擎之一。它与内核虚拟化模块 [[KVM]] 紧密集成，负责创建和管理轻量级虚拟机实例。

## 角色与优势

- **内存安全**：Rust 语言的所有权和借用机制在编译期消除了大量内存错误，显著降低了宿主机逃逸风险。
- **低开销**：经过裁剪和优化，RustVMM 本身占用极少资源，是实现 [[高密度部署]] （每个沙箱<5MB 开销）的关键使能者。
- **快照与恢复**：支持虚拟机的快照、克隆和快速恢复，这是 [[毫秒级冷启动]] 的核心技术基础。

## 在 CubeSandbox 中的位置

RustVMM 位于 Sandbox Manager 下方，直接调用 KVM 接口来创建沙箱实例。它与 [[CubeVS (eBPF-based)]] 协同工作，在提供计算隔离的同时，由 eBPF 补充网络隔离。

## 相关概念

- [[KVM]]：提供硬件辅助虚拟化能力的内核模块。
- [[硬件级强隔离]]：得益于 RustVMM 和 KVM 的结合，每个沙箱拥有独立的 Guest 内核。