# ⛏️ Paper Miner — AI 论文淘金器

> 每日自动从 Hugging Face Daily Papers 抓取热门 AI 论文，通过 DeepSeek LLM 多维度评分，筛选高分论文推送日报到 Telegram。

## 项目状态

**✅ 已上线运行** — Cronjob 每日北京时间 8:00 自动执行，结果推送到 Telegram。

## 架构

```
[HuggingFace API] → [新鲜度过滤(180天)] → [去重(seen_papers.json)] → [DeepSeek 打分(top15)]
       → [筛选≥75分] → [格式化日报] → [Telegram 推送]
```

## 模块说明

| 文件 | 功能 |
|------|------|
| `src/main.py` | 主入口，串联全流程 + 新鲜度过滤 + 篇数限制 |
| `src/fetcher.py` | HF Daily Papers API 拉取 + 异常处理 |
| `src/dedup.py` | seen_papers.json 去重（已处理论文不重复打分） |
| `src/preferences.py` | 用户偏好管理 + 评审 Prompt 模板 + 偏好保鲜提醒 |
| `src/scorer.py` | DeepSeek LLM 打分 + JSON 解析容错 + 机构识别 |
| `src/formatter.py` | 日报合并格式化（含发布日期、偏好命中标记） |
| `src/pusher.py` | cronjob auto-deliver + Telegram Bot API 直接推送 |
| `src/notion_sync.py` | Notion 看板任务状态自动同步 |
| `src/config.json` | 全局配置（API、阈值、偏好路径等） |
| `data/user_preferences.json` | 用户关注方向 + 排除方向 |
| `data/seen_papers.json` | 已推送论文 ID 去重记录 |
| `PLAN.md` | 执行方案（V1） |

## 评分体系

**基础维度（满分100分）：**
- 工程落地性 40% — 是否有开源代码？复现门槛？能否直接用到产品？
- 痛点解决度 30% — 解决真实工程痛点 vs 纯跑分刷榜
- 创新性 20% — 思路新颖度，incremental vs breakthrough
- 出圈潜力 10% — 商业产品化可行性

**附加加分：**
- 大厂/顶尖高校（Meta, Google, OpenAI, Stanford, 清华等）+5~10
- 命中用户关注方向 +10~15

**推送阈值：75分** | **每次最多打分：15篇** | **新鲜度：180天内**

## 翻译纪律

所有 AI/ML 专有名词保留英文原词（RAG, MoE, Agent, Transformer, LoRA, fine-tuning, inference 等），严禁翻译成生硬中文。

## 运行

```bash
# 手动运行
cd /tmp/hermes-paper-miner-
DEEPSEEK_API_KEY=your_key python3 src/main.py

# 自动运行：Hermes cronjob 已配置，每日北京时间 8:00（UTC 0:00）
```

## 输出示例

**有高分时：**
```
⛏️ 今日 AI 淘金日报 | 2026-04-14
━━━━━━━━━━━━━━━━━━━━

📄 [85分] [unknown] CodeTracer: Towards Traceable Agent States
🔗 https://huggingface.co/papers/2604.11641 | 📅 2026-04-13
🎯 命中偏好：多 Agent 协作 / AI Agent 框架

💡 提出了一个名为 CodeTracer 的 tracing 架构，用于解析异构运行产物、
   重建 Code Agent 的完整状态转换历史树，并定位故障起源和传播链。
🛠 落地场景预测：
  1. AI Agent 框架开发和调试工具
  2. 代码生成与自动化任务的 QA 测试
  3. 复杂多步骤工作流的监控与可观测性平台
⚠️ 劝退点：系统依赖对特定 Agent 框架运行产物的解析器，对新框架适配需额外开发

━━━━━━━━━━━━━━━━━━━━
共 1 篇高分好文 | 数据源：Hugging Face Daily Papers
```

**无高分时：**
```
🚫 今日无高分好文，最高分为 78 分，已跳过推送。明天见！
```

**系统故障时：**
```
⚠️ 系统故障：网络连接超时，今日淘金任务失败。
```

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 阈值 75 分 | DeepSeek 打分偏保守，75 分每天约 3-6 篇，信息量合适 |
| Top 15 篇 | 逐篇调 API 约 3 分钟，避免 cronjob 超时 |
| 180 天新鲜度 | 过滤陈年老论文，保留半年内即可 |
| 记录所有已处理论文 | 无高分的论文也标记为已读，避免重复打分浪费 API |
| 纯 stdlib 实现 | 不依赖第三方库，cronjob 环境零配置 |

## 配置要求

- Python 3.8+（纯 stdlib，无第三方依赖）
- DeepSeek API Key（写入 `~/.hermes/.env`）
- Hermes Agent（用于 cronjob 调度和 Telegram 投递）

## 用户偏好配置

编辑 `data/user_preferences.json`：
- `focus_areas` — 关注方向及权重（命中加分）
- `reject_areas` — 不感兴趣的方向
- 每 14 天自动提醒更新偏好

## License

MIT
