# Paper Miner - 执行方案 (V1) — ✅ 已完成

## 1. 核心验收标准 (TDD Test Cases)

### 成功用例 (Happy Path)
每日早 8:00，成功抓取 HF Daily Papers，去重后筛选出 ≥75 分论文，合并为单条"今日 AI 淘金日报"推送：

```
⛏️ 今日 AI 淘金日报 | 2026-04-14

━━━━━━━━━━━━━━━━━━━━

📄 [85分] [unknown] CodeTracer: Towards Traceable Agent States
🔗 https://huggingface.co/papers/2604.11641 | 📅 2026-04-13
🎯 命中偏好：[多 Agent 协作 / AI Agent 框架]

💡 这是啥：提出了一个名为 CodeTracer 的 tracing 架构...

🛠 落地场景预测（你可以怎么用）：
 1. AI Agent 框架开发与调试
 2. 代码生成与自动化任务的 QA 测试
 3. 复杂多步骤工作流的监控与可观测性

⚠️ 劝退点：需要集成到现有 Agent 框架中运行

━━━━━━━━━━━━━━━━━━━━
共 1 篇高分好文 | 数据源：Hugging Face Daily Papers
```

### 边缘用例
- **无高分**: 推送 `🚫 今日无高分好文，最高分为 XX 分，已跳过推送。明天见！`
- **系统异常**: 仅推送 `⚠️ 系统故障：[错误简述]，今日淘金任务失败。`
- **偏好保鲜**: 每 14 天在日报底部追加提醒更新偏好

## 2. 架构设计与数据流

```
[HuggingFace API] → [新鲜度过滤(180天)] → [去重(seen_papers.json)] → [DeepSeek 打分(top15)]
       → [筛选≥75分] → [格式化日报] → [Telegram 推送]
```

### 核心模块
1. **Fetch + Freshness + Dedup**: 拉取 HF Daily Papers，过滤陈旧论文，去重
2. **Dynamic Preferences**: 读取外置 user_preferences.json，命中偏好加分并标记 🎯
3. **LLM Scoring**: 调用 DeepSeek API，强制输出 JSON（打分+场景+劝退点）
4. **Format + Push**: 合并为单条日报，通过 cronjob auto-deliver 推送到 Telegram

## 3. 打分权重
- 满分 100 分 + 附加分
- **工程落地性 (40%)**: 是否有代码？复现门槛？
- **痛点解决度 (30%)**: 解决真实痛点 vs 跑分刷榜
- **创新性 (20%)**: 思路新颖度
- **出圈潜力 (10%)**: 商业产品化可行性
- **附加分 (+5~10分)**: 大厂或顶尖高校
- **附加分 (+10~15分)**: 命中用户关注方向

## 4. 翻译纪律 (极严)
专有名词必须保留英文原词（RAG, MoE, Agent, Transformer, LoRA, fine-tuning 等），
严禁翻译成"检索增强生成"、"专家混合"等生硬中文。

## 5. 算力来源
DeepSeek API（云端），不使用本地算力。

## 6. 任务拆解 — 全部完成 ✅

- [x] PM-001.2: HuggingFace Daily Papers API 拉取模块
- [x] PM-001.3: seen_papers.json 去重判断模块
- [x] PM-001.4: 异常捕获框架（网络超时/API限流/空数据）
- [x] PM-001.5: 无数据/无高分的降级提示生成模块
- [x] PM-002.1: user_preferences.json 初始偏好模板
- [x] PM-002.2: 核心评审 Prompt（打分维度+翻译纪律+偏好注入）
- [x] PM-002.3: LLM API 调用层（DeepSeek）
- [x] PM-002.4: LLM 输出的 JSON 解析与容错模块
- [x] PM-002.5: 作者机构识别与加分逻辑
- [x] PM-003.1: 日报合并格式化模板
- [x] PM-003.2: 偏好保鲜提醒逻辑（每14天）
- [x] PM-003.3: Telegram 推送模块
- [x] PM-003.4: 单行警报推送（系统故障优雅降级）
- [x] PM-004.1: 主入口脚本 main.py 串联所有模块
- [x] PM-004.2: Hermes cronjob 定时任务（每日 8:00 北京时间）
- [x] PM-004.3: Notion 看板状态自动同步
- [x] PM-004.4: 全流程端到端冒烟测试
- [x] PM-004.5: 代码清理 + README 文档

## 7. 部署信息

- **Cronjob ID**: 42d5dd176035
- **执行时间**: UTC 0:00（北京时间 8:00）
- **推送目标**: Telegram
- **代码路径**: /tmp/hermes-paper-miner-/src/main.py
