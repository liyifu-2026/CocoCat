---
type: entity
title: PVM (Prologue Virtual Machine)
created: 2024-07-20
summary: 一种部署方案，允许在普通云服务器（非裸金属）上启用 KVM 虚拟化能力，降低了 CubeSandbox 对硬件的门槛。
---
# PVM (Prologue Virtual Machine)

**PVM** 是专为 [[CubeSandbox]] 设计的一项辅助虚拟化技术，其全称为 Prologue Virtual Machine。它旨在解决一个问题：许多云服务器（如非裸金属的虚拟化实例）默认不支持嵌套虚拟化，因此无法直接运行 [[KVM]]。

## 解决的问题

- **硬件限制规避**：在不能直接暴露 Intel VT-x/AMD-V 的云主机上，PVM 通过软件模拟部分硬件功能或利用特殊的半虚拟化通道，使得上层的 CubeSandbox 仍然能够以“虚拟化”的方式启动带有 [[KVM]] 加速的沙箱。
- **部署灵活性**：用户无需专门采购昂贵的裸金属服务器，即可在常见的云虚拟机上部署高性能、安全隔离的沙箱服务。

## 工作方式

PVM 作为一个轻量级的前导层，拦截和仿真必要的 CPU 指令或内存映射，为内部的 [[RustVMM]] 呈现出有 KVM 能力的硬件环境。它本身不做完整的机器模拟，仅提供最小必要的“虚拟化中间层”，从而保持低开销。

## 相关文档

- 部署指南：[PVM 部署文档](docs/zh/guide/pvm-deploy.md)
- [[KVM]]
- [[RustVMM]]