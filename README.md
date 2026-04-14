# ⛏️ Paper Miner — AI 论文淘金器

每日自动从 Hugging Face Daily Papers 抓取热门 AI 论文，通过 DeepSeek LLM 多维度评分，筛选高分论文推送日报到 Telegram。

## 架构

```
[HuggingFace API] → [去重(seen_papers.json)] → [DeepSeek 打分] → [筛选≥85分] → [格式化日报] → [Telegram 推送]
```

## 模块说明

| 文件 | 功能 |
|------|------|
| `src/main.py` | 主入口，串联全流程 |
| `src/fetcher.py` | HF Daily Papers API 拉取 |
| `src/dedup.py` | seen_papers.json 去重 |
| `src/preferences.py` | 用户偏好管理 + Prompt 模板 |
| `src/scorer.py` | DeepSeek LLM 打分 + JSON 解析 |
| `src/formatter.py` | 日报格式化 + 偏好保鲜提醒 |
| `src/pusher.py` | 输出到 cronjob auto-deliver |
| `src/notion_sync.py` | Notion 看板状态同步 |
| `src/config.json` | 全局配置 |
| `data/user_preferences.json` | 用户关注方向 |
| `data/seen_papers.json` | 已推送论文 ID 记录 |

## 评分维度

- 工程落地性 40%
- 痛点解决度 30%
- 创新性 20%
- 出圈潜力 10%
- 附加分：大厂/顶尖高校 +5~10，命中用户偏好 +10~15

## 运行

```bash
# 手动运行
cd /tmp/hermes-paper-miner-
DEEPSEEK_API_KEY=your_key python3 src/main.py

# 自动运行：已配置 Hermes cronjob，每日北京时间 8:00
```

## 输出示例

**有高分时**：
```
⛏️ 今日 AI 淘金日报 | 2026-04-14
━━━━━━━━━━━━━━━━━━━━
📄 [85分] CodeTracer: Towards Traceable Agent States
🔗 https://huggingface.co/papers/2604.11641
🎯 命中偏好：多 Agent 协作 / AI Agent 框架
💡 提出了一个名为 CodeTracer 的 tracing 架构...
🛠 落地场景预测：
  1. AI Agent 框架开发与调试
  2. 自动化软件工程流水线
  3. AI Agent 性能评估与优化
⚠️ 劝退点：论文未明确说明计算开销...
━━━━━━━━━━━━━━━━━━━━
共 1 篇高分好文 | 数据源：Hugging Face Daily Papers
```

**无高分时**：
```
🚫 今日无高分好文，最高分为 78 分，已跳过推送。明天见！
```

**系统故障时**：
```
⚠️ 系统故障：网络连接超时，今日淘金任务失败。
```

## 配置要求

- Python 3.8+
- DeepSeek API Key（写入 `~/.hermes/.env`）
- Hermes Agent（用于 cronjob 调度和 Telegram 投递）
