# 完整容器／共享浏览器／外部 MCP 部署前置条件

状态：镜像和离线隔离基线已编写，尚未构建或部署，也没有接入生产 Agent。不能把这些文件称作已经可用的完整开发环境。

2026-11-15 检查结果：Windows 10 家庭版未启用 hypervisor，没有 Docker；sg88n5-2 当前账户没有 Docker/Podman/bubblewrap，创建用户命名空间返回 Operation not permitted，sudo -n 返回需要密码。已保留现有 GPU 服务，没有尝试猜测 Linux 密码、修改 AppArmor、重启或停止科研任务。

需要管理员提供一台可部署容器的主机及 SSH 别名。可以在 sg88n5-2 安装，但建议将 CPU 执行服务与 GPU 推理解耦。不要在聊天中发送密码。Docker 组权限近似宿主 root 权限，不能授予站点成员；仅可信编排账户可访问 Docker。优先使用管理员配置的 rootless runtime，前提是用户命名空间确实可用。

## 可审阅的基线

Dockerfile 提供 Python 3.12、Node 22/npm、Git、编译工具、Chromium 和 Playwright。compose.yaml 为每位成员创建独立命名卷，以非 root 运行，移除 capabilities，限制 CPU、内存和进程数，不挂载宿主目录、凭据或 Docker socket。

在管理员准备好的主机上，先在独立目录构建并验证：

```bash
docker info
docker compose -p localrsi-preflight -f containers/compose.yaml build
docker compose -p localrsi-preflight -f containers/compose.yaml up -d
docker compose -p localrsi-preflight -f containers/compose.yaml exec development python -c 'print(17*23)'
docker compose -p localrsi-preflight -f containers/compose.yaml exec development node --version
docker compose -p localrsi-preflight -f containers/compose.yaml exec development git --version
docker compose -p localrsi-preflight -f containers/compose.yaml down
```

命名卷默认保留。完整生产集成还需要成员认证绑定、动作审计、超时与取消、容器/卷生命周期、磁盘配额及导入导出。不能只给用户一个 container_id，就视为租户权限检查。

## 网络与浏览器

此离线基线 network_mode=none 是部署测试的起点，尚不支持外网浏览或 npm/pip 下载。生产浏览器/外部 MCP 需要受控出站网络，并验证它不能访问宿主服务、其他成员、云元数据地址；不能简单改成 host 网络。

浏览器应每成员独立进程与 profile，持久化目录只属于该成员；通过认证工具 API 操作，不向公网开放无认证 CDP。需要实测 Chromium 在最终容器的 sandbox/seccomp 配置下能够启动。容器没有启动前，现有站点的共享浏览器继续保持关闭。

## 外部 MCP

目标是支持用户配置第三方 stdio 和 Streamable HTTP 服务，而不是只限内置服务。stdio 的 npm/python 可执行程序应运行在该成员容器，服务 URL、参数和密钥仅供对应成员使用；密钥不能写入模型上下文、Git、共享日志或普通任务队列。连接需初始化、列举工具、显示权限与调用确认，断线可恢复但不自动重放有副作用的请求。

本机已经实现 stdio 和 Streamable HTTP（2025 协议）的工具连接，详见 MCP-HTTP.md；HTTP JSON/SSE 会话已通过本地协议服务测试。上述共享生产连接器尚未部署，不承诺任何 MCP 包都兼容。获得容器宿主后，应选择一个真实 stdio 服务和一个 HTTP 服务完成成员隔离及端到端验收，再开放共享配置入口。
