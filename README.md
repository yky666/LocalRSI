# LocalRSI

Windows 本地优先的科研与编程 Agent：GUI、CLI 共用任务循环、模型路由、文件工具和任务记录。默认使用本机 CPU 模型，不调用商业 API。版本：0.2.0。

## 快速开始

首次部署（Windows PowerShell，需联网下载软件与模型）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Bootstrap.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\Setup-Extras.ps1
.\Start-GUI.cmd
```

GUI：http://127.0.0.1:8090 。已部署的机器直接运行 `Start-GUI.cmd`。`Stop-LocalRSI.ps1` 关闭 Agent；相邻 `local-ai/Stop-LocalAI.ps1` 释放文字模型内存。下载代理可通过进程环境变量配置，不要提交代理或密钥。

```bat
localrsi.cmd "查看工作区文件"
localrsi.cmd --image "D:\example.png" "描述图片"
localrsi.cmd --groups documents "读取 paper.pdf 的第一页"
localrsi.cmd --index paper.pdf
localrsi.cmd --search "检索增强生成的方法"
localrsi.cmd --provider remote "分析这个复杂问题"
localrsi.cmd --continue-task TASK_ID "继续完善上面的笔记"
localrsi.cmd --note "论文笔记默认使用中文"
localrsi.cmd --record
```

CLI 交互模式默认续接上一条已完成任务；输入 `/exit` 退出。原始资料放到 `workspace/`，GUI 支持 5MB 以内上传；较大文件可手动复制。工具组按关键词或显式勾选启用，避免把所有工具定义塞进 4B 模型上下文。

## 能力与验证状态

| 能力 | 实现 | 本机验证 |
|---|---|---|
| 文字 Agent | Qwen3 4B、工具循环、状态与日志、会话续接、任务取消 | CLI 及短请求已测 |
| 文件与代码 | UTF-8 读取、写入、精确替换补丁、差异预览、备份、PowerShell/测试命令 | 核心与审批测试已测 |
| PDF / Word | 按页提取 PDF、DOCX 读取、DOCX 输出、PDF 渲染 | PDF / DOCX 单元测试通过 |
| 图片 | SmolVLM 500M + 投影文件，串行切换后由 Qwen 回答 | 图文链路已测，视觉准确性较弱 |
| 中文 OCR | Windows 自带离线 OCR，扫描页先渲染再识别 | 中文测试图片识别成功 |
| RAG | BGE-small-zh 512维语义向量 + 关键词重排，SQLite 索引，页码引用，重复索引缓存 | 真模型索引与引用检索已测 |
| 长期记忆 | 用户确认的偏好，自动带入上下文，搜索、删除 | 原有笔记存储已用，CRUD 实现 |
| 浏览器 | 独立 Edge 配置，打开、读取控件、CSS 点击、填表、截图 | 代码已接入，界面端到端未验证 |
| 桌面 | 截图、批准后点击坐标、输入 Unicode | 代码已接入，实际控制未验证 |
| 语音 | Windows 离线朗读、Vosk 中文 WAV 转写、显式按钮录音 | 合成语音和 WAV 转写通过；麦克风未测 |
| 反馈改进 | 任务评分/纠正、训练样本导出、候选提示词六项评测、无退化门槛、手动启用/回滚 | 完整流程实测，基线/候选均5/6，未提高；已回滚 |
| 远端推理 | OpenAI 兼容文本/视觉接口，密钥仅环境变量读取 | 适配器实现，真实远端待连接 |
| LoRA / QLoRA | 独立 CUDA 训练脚本、训练/测试划分、前后评估、不自动部署 | 语法检查；未在 GPU 实训 |

这是持续开发中的 Agent，不等同于成熟 Codex。未验证的能力不应被视为可靠自动化。浏览器和桌面操作一律逐项批准，不根据弱视觉模型自主点击。

## 性能记录

在 i7-9700、16GB RAM、CPU 推理上得到的样例，不是跨任务性能保证：

- Qwen 短请求生成约 9 tokens/s；一次热缓存三 token 回复端到端约 2.6 秒。首请求、长上下文和工具规划通常更慢。
- 工具定义按需加载，一条简单对话的 prompt 从约 590 tokens 减少至 175 tokens。此前和之后缓存状态不同，不能仅根据总耗时宣称同等倍数提速。
- 一个短中文文档冷索引约 0.84 秒；单文档热检索约 7 毫秒。大语料规模尚未压测。
- 一张清晰中文测试图的 Windows OCR 约 1 秒；合成中文语音文件离线转写约 2.3 秒。
- 原有 Qwen 配置的进程工作集约 4.64GB；视觉按需切换，向量模型和浏览器会增加额外内存。

SmolVLM 500M 的红方块/蓝圆形测试只提取了颜色，漏掉形状和背景。精细图表、公式、GUI 定位建议配置更强的远端视觉模型；不要把它当作可靠 OCR。

## 远端配置

复制 `config.example.json` 为 `config.json`，填写 remote / vision 的 `base_url` 和 `model`。密钥通过 `LOCALRSI_REMOTE_KEY` / `LOCALRSI_VISION_KEY` 等环境变量提供，禁止写进配置或日志。远端使用 HTTPS，或 SSH 隧道映射到 localhost。只有显式选择远端时才把任务交给该服务；默认仍为本机。

`training` 配置用于生成训练计划：

```bat
python remote_training.py "data\training-export\EXPORT_ID"
```

该命令仅生成待审核的上传/执行计划，不自动登录、不修改远端 CUDA、不终止科研任务。真正训练需在已明确分配的 GPU 上创建独立环境，安装 `requirements-training.txt`，上传人工审核的数据与 `train_lora.py`，再运行：

```bash
CUDA_VISIBLE_DEVICES=1 python train_lora.py --model Qwen/Qwen3-4B-Instruct-2507 --data dataset --output adapter --qlora --steps 100
```

训练脚本要求至少 10 条训练样本和 2 条独立测试样本；这只是最低运行门槛，不足以证明效果。人工确认的纠正优先，数据要检查隐私与正确性。提示词候选、LoRA 适配器和基础模型的升级属于不同流程，不能把启用提示词称作模型参数自我进化。

## 权限和数据

- 文件工具限制工作区，拒绝路径越界和链接。写入展示全文/差异，审批后执行；若文件在预览后被其他程序修改，会拒绝旧审批。
- 命令经批准后具有当前用户权限，**不是沙箱**。45 秒超时会终止本任务的进程树。不要批准不理解的命令。
- 浏览器使用独立 profile；打开网址、点击和填表需要批准。桌面输入会影响当前焦点窗口，坐标必须由人核对。
- 取消在模型/工具步骤之间生效，不能撤销已经执行的操作。
- `data/` 包含记忆、任务、备份、浏览器资料和评测；`workspace/` 包含用户文件。两者及本地配置、模型、运行时都在 `.gitignore` 中，不上传仓库。
- 默认 4096 tokens 上下文，会裁剪长工具结果并压缩续接历史。超长任务应拆分或交给远端。

## 开发和测试

```powershell
.\python\python.exe -m unittest discover -s tests -v
.\python\python.exe tests\test_runtime.py
```

12 项核心测试已通过。GitHub Actions 配置为 Windows + Python 3.12。`tests/test_runtime.py` 为显式运行的本机服务检查，CI 不下载大模型。

六项模型冒烟评测中，基线和候选均把 17×23 错答为 401，其余五项通过。已加入受限 AST 算术工具，真实 Agent 再测会调用 calculate 并返回正确结果391。原始模型心算错误仍然存在；本次修复是工具增强，不是训练提升。

源码 MIT；依赖和模型使用各自许可证，包括 PyMuPDF 的 AGPL/商业许可，分发时需遵守其条款。模型下载自 Qwen、Unsloth、ggml-org，推理引擎来自 llama.cpp，嵌入来自 BAAI/Qdrant，中文语音来自 Vosk。模型不包含在 Git 仓库内。

## v0.3：模式、MCP 与持续目标

GUI 与 CLI 共用 API，可选择：

- `--mode chat|plan|agent`：仅对话、仅制定计划、工具执行。前两种模式不向模型提供工具，也不启动 MCP 进程。
- `--thinking fast|standard|deep`：每段最多 6 / 12 / 20 轮；输出预算 400 / 700 / 1000 tokens。深度模式增加一次结果复核，遵守原请求格式。它是 Agent 工作流，不是开启当前 Qwen3 Instruct 模型原生 thinking，也不保证质量提升。
- `--goal`：保存目标、步骤、执行记录与证据。步骤完成状态由 Agent 自报；必须结合实际工具结果检查。轮次或输出预算耗尽标记 `budget_exhausted`，不会冒充完成。
- `--resume TASK_ID`：为预算耗尽或可安全恢复的中断任务增加一段预算，保留原目标和工具结果。中断操作结果不明时拒绝重放。取消后不自动恢复；重启不自动执行待批准操作。
- `--mcp workspace`：启用随附只读工作区 MCP 服务，首次工具发现后每次调用仍需明确批准。
- `--capabilities`：列出服务端支持的模式与已配置 MCP 服务。

```powershell
.\python\python.exe cli.py "计算17乘23并记录验收结果" --goal --thinking standard
.\python\python.exe cli.py "为项目制定测试计划" --mode plan --thinking deep
.\python\python.exe cli.py "使用 MCP workspace 列出根目录" --mcp workspace
.\python\python.exe cli.py --resume TASK_ID
```

MCP 服务在本地 `config.json` 的 `mcp_servers` 中配置；`{python}` 使用 LocalRSI 自身解释器。只启动用户配置且本次选中的命令，不接受模型传入可执行程序。配置命令拥有当前用户权限，应只使用可信服务。

```json
{"mcp_servers":{"workspace":{"command":"{python}","args":["scripts/workspace_mcp.py"],"timeout":15}}}
```

本版支持 MCP stdio 的 initialize / initialized、分页 tools/list、tools/call、ping、超时及进程清理。支持协议版本 2024-11-05、2025-03-26、2025-06-18、2025-11-25；不宣称支持 2026 协议、Streamable HTTP、资源订阅、sampling 或 elicitation。参照 [MCP 生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) 与 [stdio 传输](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)。

GUI 显示目标步骤、模型调用次数、累计模型耗时和生成 token 数；耗时不包含排队、用户审批和工具执行。CPU 4B 适合小任务，长目标应拆分或使用已配置的远端模型。自我改进仍采用反馈、候选、评测、手动启用与回滚；没有未经验证的自动权重更新。

## Web 工作台

新版界面提供独立的任务、知识库、长期记忆、评测与设置视图，采用响应式侧边导航；手机端使用折叠菜单。工具和 MCP 配置按需展开，保留原有模型、思考模式、持续目标及审批行为。支持 Ctrl/Cmd+Enter 提交任务、Alt+N 新建任务；页面 hash 可直接定位知识库等视图。

验证：桌面 1440px 和移动 390px 页面无 JavaScript 错误；移动端无横向溢出；导航、快捷任务、新建任务及本地真实模型调用通过。界面使用本地资源，无外部字体或图片依赖。

### 公网部署边界

当前 Python 服务仍只绑定 127.0.0.1，属于单用户工作空间，尚无成员身份认证及用户数据隔离。界面更新不代表已开放公网，也不能仅将 8090 端口转发或反向代理到公网来提供多用户服务。

待确定的生产目标为固定域名 + HTTPS + 受邀成员身份认证 + 独立工作空间 + 共享模型端点。成员的任务、文件、记忆、索引、反馈及审批都需要按身份隔离；可执行命令的 Agent worker 应使用独立低权限容器或账户，不能仅依靠目录检查。公网网关与 GPU 推理服务分离，模型接口不直接暴露。现有的桌面操作、服务器麦克风和本机 PowerShell 功能还需明确为所有者专用能力或替换为服务端可用实现。

部署尚待提供实际服务器入口及域名/访问策略。不要将本节当成已经完成的认证、隔离或生产部署。
