type: entity
title: KVM (Kernel-based Virtual Machine)
created: 2024-07-20
summary: Linux 内核的虚拟化模块，提供硬件辅助的 CPU 和内存虚拟化能力，与 RustVMM 共同构成 CubeSandbox 的硬件隔离基础。
---
# KVM (Kernel-based Virtual Machine)

**KVM** 是 Linux 内核中的虚拟化基础架构，它利用处理器的硬件虚拟化扩展（如 Intel VT-x 或 AMD-V），将 Linux 转变为一个高效的 Hypervisor。在 [[CubeSandbox]] 中，KVM 负责提供核心的 CPU 和内存隔离。

## 功能与价值

- **硬件辅助隔离**：通过 VMX/SVM 指令实现虚拟机与宿主机、虚拟机之间的强隔离，这是 [[硬件级强隔离]] 的根本保障。
- **高性能**：与 [[RustVMM]] 配合，能够接近原生性能地执行沙箱代码，支撑毫秒级启动和高并发。
- **内存写时复制**：KVM 支持虚拟机内存的写时复制（CoW）共享，使得从同一模板克隆多个沙箱时，可以共享只读内存页，从而实现 [[高密度部署]] （单实例<5MB 开销）。

## 运行要求

通常 KVM 需要宿主机为裸金属服务器或启用嵌套虚拟化的云主机。对于普通云服务器，[[PVM (Prologue Virtual Machine)]] 技术可绕过限制，使 KVM 在非裸金属环境中可用。

## 参见

- [[RustVMM]]
- [[硬件级强隔离]]
- [[高密度部署]]