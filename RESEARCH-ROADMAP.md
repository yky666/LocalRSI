# LocalRSI：当前能力与科研闭环

更新：2026-11-15。以下严格区分已实现、待接入和长期研究目标。

## 当前部署

公网入口：https://localrsi-workspace-kaiyuan.frizzyice3.chatgpt.site/workspace

计算链路：受邀成员登录 → 托管队列 → Windows 出站 relay → kaiyuan1 跳板 → sg88n5-2（172.25.72.115）端口 28438。

当前模型服务名 `qwen3.8-27b-core100-20261106`，检查点路径为 `/data/yangkaiyuan/phyediting_eval_render_20261028/models/Qwen3.8-27B`。尚未核实该检查点是否与官方权重逐文件一致。
只读进程树与 nvidia-smi 交叉确认：API PID 3277606，engine PID 3277955，GPU 0，UUID `GPU-91b733ec-e331-9b77-e85d-d5982b768967`。引擎占用 79776 MiB；设备报告总显存 85651 MiB。瞬时资源数值会变化，GPU UUID 比卡号稳定。

两节点共六卡不等于六卡专属于 LocalRSI。当前复用既有服务，没有停止研究进程、修改驱动或启动训练。Windows 仍必须在线；GPU 服务器直连托管入口遇到 HTTP 403，尚未完成常驻迁移。

## 本次交付

- 输入框支持用户主动粘贴和拖放文件；不会后台扫描剪贴板。浏览器不能提供的文件引用需使用文件选择器。
- 普通文件每个不超过 5MB，每任务最多八个；路径和 SHA256 记录在任务。文件仍通过工具按需读取。
- PNG/JPEG 图片；每任务一个视觉输入。视频不超过 150MB，在浏览器均匀采样四帧并拼图，附采样时间。不上传完整视频、不转写音轨，不能据此推断未采样动作。
- 三个可选择、版本可追踪的内置 SKILL.md：论文分析、实验设计、编程验证。技能不扩展权限；尚无第三方技能自动安装市场。
- CLI `--skills paper-review,experiment-design --attach paper.pdf`；附件路径相对工作区。
- `research_runner.py`：评测文件哈希、基线对照、候选成绩、日志、单次/总时限、GPU UUID 配置及启动前空闲检查；默认仅验证 manifest，显式 `--run` 才执行。

## 实验执行器使用边界

这是用于可信、已审查命令的执行器，不是容器、调度器或恶意代码沙箱。GPU 空闲检查存在竞争窗口；CUDA_VISIBLE_DEVICES 也不是访问控制。真正的持续多成员实验必须增加集群资源预留和容器/cgroup 限额，不能仅靠此脚本保证隔离。任务不能自行创建脱离父进程的后台服务。当前没有把该执行器开放成公网任意命令接口。

manifest 位于实验目录，包含 question、metric、direction（min/max）、evaluation_file、budget_seconds（≤86400）、trial_seconds、gpu_uuids、trials。trials 第一项 id 必须为 baseline，每项 command 是参数数组。程序最后一行输出 JSON，例如 `{"validation_loss": 1.2}`；metric 填 validation_loss。不要把测试集分数作为可持续优化目标。

命令：`python research_runner.py experiment.json --output runs` 只验证；加 `--run` 才执行。测试用假指标仅验证记录/比较逻辑，不代表真实模型提升。

## 仍待实现的闭环

1. **基础运行环境**：服务器常驻桥接、任务恢复、隔离执行容器、资源预留。保留交互推理容量，训练使用明确分配的 GPU UUID 和每日预算。
2. **来源和知识**：按研究方向检索论文、代码、许可可用数据；保存 URL、时间、许可、哈希；去重、质量过滤、训练/评测去污染。先进行定向知识检索，不能把无限抓取视为有效学习。
3. **研究任务生成**：从复现失败、文献限制、真实工作失败中提出假设。每项必须有对照组、主指标、消融、预算和否定条件。
4. **执行与反馈**：隔离环境运行实验，用测试结果、环境奖励、准确率、延迟、显存和复现指标提供自动反馈。模型评论辅助分析，不能充当独立验证。
5. **学习**：经验证的轨迹进入技能或记忆；高质量数据进入 LoRA/QLoRA 候选训练。不要把新增 RAG 文档、修改提示词称作权重训练。
6. **晋升与回滚**：验证集用于筛选；保留测试集阶段验收。科研任务、工具调用、视觉、回归和资源指标同时通过后，灰度替换模型；保留旧版本和数据谱系。
7. **具身分支**：待文章对应论文/代码确认后，先接仿真环境、动作空间、任务成功率与碰撞等指标，再考虑真实设备。浏览器自动化与视频描述不能直接称作物理具身能力。

## 模型与对标

Qwen3.8-27B 官方模型卡：https://huggingface.co/Qwen/Qwen3.8-27B
Agent 功能参考：https://github.com/QwenLM/Qwen-Agent
固定预算自动实验参考：https://github.com/karpathy/autoresearch

当前 fast/standard/deep 调整 Agent 预算与复核流程，尚不是原生 reasoning_effort 的完整映射。共享站点禁用任意命令、浏览器/桌面控制与外部 MCP，需隔离 worker 后开放，不能说已达到 Codex 等价能力。

对标 GPT-6 Astra 是长期目标，当前没有同题、同工具、同预算的对照实验，不能声明齐平或超越。先衡量自有科研任务成功率、复现误差、工具成功率、视觉正确率、每任务时间和成本，再判断有无提升。

持续训练启动前需要：可用节点与 GPU UUID、每日 GPU 小时、首个科研方向/复现论文。微信文章未能读取，还需标题或对应项目链接。
