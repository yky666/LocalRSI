# 验证记录：2026-11-15

## 已通过

- 12 项核心单元测试，约0.5秒：路径、备份、补丁、文档解析、引用检索、上下文保留、候选启用门槛、样本导出、模型传输配置和受限计算器。
- Python 编译检查及前端 JavaScript `node --check`。
- 本机 CLI 真实模型对话；GUI HTTP 200。
- 文件审批前不写入，拒绝不写入，批准后写入；命令批准后执行；重复审批和外部 Origin 被拒绝。
- BGE-small-zh ONNX 校验 SHA256：1294ea4b6331115a353d81f96b85e8c8d7fdcc284453d5b2fab5b016230aad38。
- 中文短文档冷索引约0.844秒，单文档热检索约0.007秒，返回来源和页码。未做大规模压测。
- Windows OCR 清晰中文图约0.996秒，识别文字带空格，不能保证复杂排版准确性。
- Windows 中文语音合成保存 WAV；Vosk 对该合成 WAV 转写约2.303秒，内容正确。真实麦克风和复杂噪声环境未测。
- 候选提示词12次推理（六项基线+六项候选）完整结束，均5/6。启用门槛通过、手动启用、再回滚全部成功。没有宣称能力提升。
- 算术错误通过工具增强修复：真实 Agent 调用 calculate 得到391。

## 不能据此宣称完成的部分

- 浏览器和桌面工具已有实现，但实际 GUI 操作端到端未验证；本轮界面验证因无法可靠确认浏览器 URL 被停止。
- 远端模型需要真实服务地址；LoRA/QLoRA 脚本只有语法检查，没有真实 GPU 训练结果。
- GitHub 发布状态必须看远端提交是否存在，不能把本地 commit 当作已推送。
- 500M视觉模型仅适合粗略描述，已知会漏掉测试图中的形状和背景；未达到可靠 GUI 视觉定位要求。
- 性能数字来自少量本机样例，缓存状态不同，不构成跨任务或其他机器的保证。

## v0.3 validation (2026-11-15)

- 25 unittest tests passed: original core tests plus modes, resumable budgets, MCP approval/config binding, stdio initialization/pagination/Unicode/timeout cleanup.
- Real CPU Qwen3-4B: fast chat, deep two-pass response, tool-grounded goal completion and MCP list_files with explicit approval completed.
- Real goal: calculate(17*23) -> 391; update_plan recorded evidence; final response completed in 3 rounds.
- GUI: Edge headless checked mode controls and configured MCP; actual GUI plan submission tested. CLI fast chat tested against running local service.
- Deep-review regression: initial implementation ignored a one-sentence constraint; revised review prompt preserved it on re-test. One smoke case is not a general quality benchmark.

| Live case | Model calls | Model request seconds | Output tokens |
|---|---:|---:|---:|
| deep_v2 | 2 | 8.10 | 46 |
| mcp | 2 | 22.23 | 73 |

Timings exclude queue, approval and tool time. No claim of Codex-level reasoning performance or native thinking in the installed Instruct model. MCP support is stdio tools for the explicitly documented protocol versions; no HTTP transport. Goal checklist completion remains model-reported. Remote GPU inference/training was not benchmarked or newly deployed.
