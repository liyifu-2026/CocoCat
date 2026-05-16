# CubeSandbox 部署计划

日期: 2026-05-14
状态: ✅ 已完成

## 当前环境探测

| 项目 | 状态 |
|------|------|
| 宿主机 | Debian 13, 15GB RAM, KVM `/dev/kvm` 可用 |
| CubeSandbox 仓库 | ❌ 未克隆 (debian 全新环境) |
| Docker | ❌ 未安装 |
| QEMU VM 残留 | ❌ 无 (Arch 虚拟机数据未带过来) |
| 上次进度 | Arch 上 `prepare_image.sh` + `run_vm.sh` 成功，`online-install.sh` 内存不足失败 |

## 方案选择

**采用 QEMU Dev Env 方案**（与 Arch 上次相同），而非宿主机直装。

原因：CubeSandbox 安装脚本 (`online-install.sh`) 是 yum 系（CentOS/OpenCloudOS）， Debian (apt 系) 无法直接运行。QEMU Dev Env 提供一次性 OpenCloudOS VM，隔离安装环境，不污染宿主机。

## 部署步骤

### 步骤 1：宿主机环境准备

```bash
# 安装 QEMU/KVM（宿主机）
sudo apt install -y qemu-system-x86 qemu-utils

# 克隆 CubeSandbox 仓库
git clone https://github.com/tencentcloud/CubeSandbox.git ~/CubeSandbox
```

### 步骤 2：制备金镜像（≈20分钟）

```bash
cd ~/CubeSandbox/dev-env
./prepare_image.sh
```

做的事：下载 OpenCloudOS qcow2 → 扩为 100G 金镜像。

> 上次 Arch 已完成此步。debian 需重新执行（镜像数据未迁移）。

### 步骤 3：启动 QEMU VM

```bash
./run_vm.sh
```

- 通过 KVM 启动 8GB 内存 VM
- 端口转发：10022→22 (SSH), 13000→3000 (CubeAPI)
- 终端保持开启

### 步骤 4：进入 VM 安装 CubeSandbox（≈15分钟）

```bash
# 新终端
cd ~/CubeSandbox/dev-env && ./login.sh
```

```bash
# VM 内部
curl -sL https://cnb.cool/CubeSandbox/CubeSandbox/-/git/raw/master/deploy/one-click/online-install.sh | MIRROR=cn bash
```

做的事：Docker + MySQL + Redis + CoreDNS + cubemaster + cube-api + cubelet 一键安装。已确认 VM 有 8GB 内存，不会再 OOM。

### 步骤 5：创建代码解释器沙箱模板

```bash
cubemastercli tpl create-from-image \
  --image cube-sandbox-cn.tencentcloudcr.com/cube-sandbox/sandbox-code:latest \
  --writable-layer-size 1G \
  --expose-port 49999 \
  --expose-port 49983 \
  --probe 49999
```

等待模板 READY（镜像较大，需耐心），记录 `template_id`。

### 步骤 6：验证 E2B SDK 连接

宿主机运行 Python SDK 测试：

```python
import os
from e2b_code_interpreter import Sandbox

os.environ["E2B_API_URL"] = "http://127.0.0.1:13000"
os.environ["E2B_API_KEY"] = "dummy"
os.environ["CUBE_TEMPLATE_ID"] = "<template_id>"

with Sandbox.create(template=os.environ["CUBE_TEMPLATE_ID"]) as sandbox:
    result = sandbox.run_code("print('Hello from Cube Sandbox!')")
    print(result)
```

### 步骤 7：CocoCat 集成

验证通过后，修改 CocoChat 的 `/api/chat` 路由：
- 当前 `chat.py:30` 引用 `ctx.sandbox_provider`，需确认其已指向 CubeSandbox
- 检查 `CubeSandboxExecutor` 是否使用 e2b_code_interpreter SDK 连接本地 CubeSandbox

## 风险

| 风险 | 缓解 |
|------|------|
| QEMU 包缺失 | `apt install qemu-system-x86 qemu-utils` |
| Docker 未安装 (宿主机) | QEMU 方案不需要宿主机 Docker。VM 内安装脚本自行处理 |
| 镜像下载慢 | 使用国内镜像 `MIRROR=cn` |
| 模板制作超时 | 镜像 ~2GB，下载 + 解压 + 构建约 5-15 分钟 |

## 预计耗时

| 步骤 | 时间 |
|------|------|
| clone repo + apt install | 3 分钟 |
| prepare_image.sh | 20 分钟（下载 qcow2） |
| run_vm.sh | 即时 |
| online-install.sh | 10-15 分钟 |
| 创建模板 | 5-15 分钟（依赖镜像下载速度） |
| **总计** | **40-60 分钟** |

---

## 实际执行结果

### 额外遇到的问题与解决

1. **SSH 密码认证**：QEMU VM 无图形界面，`ssh-askpass` 不可用。通过创建 `SSH_ASKPASS` 脚本 + `setsid` 绕过。

2. **root 权限**：`online-install.sh` 需要 root。通过 `echo password | sudo -S` pipe 解决。

3. **cubelet OOM Killed**：第一次启动时 cubelet 被 OOM 杀死（VM 8GB 勉强够用），`up.sh` 自动重启后成功。

4. **系统代理干扰**：宿主机 `ALL_PROXY=socks://127.0.0.1:6244` 导致 httpx 连接失败，`env -u` 清除后解决。

5. **DNS 通配解析**：沙箱访问需要 `*.cube.app` → `127.0.0.1`。安装 dnsmasq + 设为系统首选 DNS。

6. **端口转发**：cube-proxy 监听 VM 内 443，需 iptables DNAT 将宿主机 443 → 11443。

7. **SSL 自签证书**：从 VM 拷贝 `/root/.local/share/mkcert/rootCA.pem`，设置 `SSL_CERT_FILE`。

### 宿主机配置（持久化）

```bash
# dnsmasq: 通配 DNS
echo "address=/cube.app/127.0.0.1" > /etc/dnsmasq.d/cubesandbox.conf
# resolv.conf 首行: nameserver 127.0.0.1

# iptables: 443 → cube-proxy (11443)
iptables -t nat -A OUTPUT -p tcp --dport 443 -j DNAT --to-destination 127.0.0.1:11443
```

### E2B SDK 连接环境变量

```bash
export E2B_API_URL=http://127.0.0.1:13000
export E2B_API_KEY=dummy
export E2B_DOMAIN=cube.app
export SSL_CERT_FILE=/tmp/cubesandbox-ca.pem
```

### 验证结果

- Cube API: `{"status":"ok","sandboxes":0}` 
- 模板 ID: `tpl-dedcd9373c3f49939f7feb9b`
- E2B SDK `run_code` 成功: `Hello from Cube Sandbox!`, Python 3.12.13

---

## CocoCat 集成

### 改动文件

| 文件 | 改动 |
|------|------|
| `cococat/__main__.py` | 新增 `--cube-sandbox` 和 `--cube-sandbox-template` CLI 参数。启用时创建 `CubeSandboxExecutor`，将 `sandbox_run` 注入到 `create_core_tools()` 和 `LocalExecutor` |
| `cococat/core/sandbox/local_executor.py` | 构造函数新增 `sandbox_run` 参数，`run()` 中传给 `create_core_tools()` |
| `cococat/tests/core/test_cubesandbox_integration.py` | 新增 6 个集成测试（bash 工具路由、sandbox_run 隔离等） |

### 工作原理

```
用户消息 → POST /api/chat
  → SandboxProvider.run_once()
    → LocalExecutor.run()
      → Agent.run() (ReAct loop)
        → bash 工具 → _bash()
          → ctx.get("sandbox_run")  ← 闭包注入
            → CubeSandboxExecutor.sandbox_run()
              → KVM MicroVM → 执行代码 → 返回结果
```

### 使用方式

```bash
# 普通模式（bash 本地执行）
python -m cococat --port 8000

# CubeSandbox 模式（bash 在 MicroVM 中执行）
python -m cococat --port 8000 --cube-sandbox

# 或通过 start.sh + .env:
echo "CUBE_SANDBOX=1" >> .env
./start.sh
```

### 验证

- 单元测试: 136 passed（含 6 个新集成测试）
- 真实 CubeSandbox 端到端: Python 3.12.13 在 KVM MicroVM 中成功执行，`ls /` 显示隔离文件系统

