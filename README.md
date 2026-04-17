# ⛏️ Paper Miner — AI 论文淘金器

> 每日自动从 HuggingFace + ModelScope 双源抓取热门 AI 论文，通过 DeepSeek LLM 多维度评分，逐篇推送高分论文到 Telegram，附带 👍/👎 反馈闭环。

## 项目状态

**✅ 已上线运行** — Cronjob 每日北京时间 8:00 自动执行，结果推送到 Telegram DM。

## 架构

```
[HuggingFace Daily Papers] ──┐
                              ├── [跨源去重] → [新鲜度过滤(180天)] → [去重(seen_papers)]
[ModelScope Papers] ─────────┘
                                                              ↓
                                                    [DeepSeek 打分(top15)]
                                                              ↓
                                              [筛选≥75分] → [逐篇 Telegram 推送 + inline keyboard]
                                                              ↓
                                                    [反馈记录(feedback.jsonl)]
                                                              ↓
                                              [打分结果持久化(scoring_results.jsonl)]
                                                              ↓
                                              [Reddit Observer(可选,隔离)]
```

## 模块说明

| 文件 | 功能 |
|------|------|
| `src/main.py` | 主入口，串联全流程 |
| `src/fetcher.py` | HF Daily Papers + ModelScope 双源拉取 + 异常处理 |
| `src/dedup.py` | seen_papers.json 去重（已处理论文不重复打分） |
| `src/preferences.py` | 用户偏好管理 + 评审 Prompt 模板 + 偏好保鲜提醒 |
| `src/scorer.py` | DeepSeek LLM 打分 + JSON 解析容错 + 机构识别 |
| `src/formatter.py` | 单篇论文富格式化（Telegram HTML） |
| `src/pusher.py` | 逐篇 Telegram 推送 + inline keyboard 反馈按钮 |
| `src/feedback.py` | 👍/👎 反馈记录 + 偏好分析 |
| `src/feedback_analysis.py` | 评分 vs 反馈一致性分析（分桶统计 + CSV） |
| `src/feedback_analyzer.py` | 每3天自动反馈分析报告（cronjob） |
| `src/reddit_watcher.py` | Reddit r/LocalLLaMA 论文监控（独立模块，14天TTL） |
| `src/notion_sync.py` | Notion 看板任务状态自动同步 |
| `src/config.json` | 全局配置（API、阈值、偏好路径等） |

## 数据文件

| 文件 | 说明 |
|------|------|
| `data/user_preferences.json` | 用户关注方向 + 排除方向 |
| `data/seen_papers.json` | 已推送论文 ID 去重记录 |
| `data/feedback.jsonl` | 用户 👍/👎 反馈记录（含 reason） |
| `data/scoring_results.jsonl` | 每日打分结果持久化（score + why_read + deep_take） |
| `data/reddit_mentions.jsonl` | Reddit 论文提及记录（隔离数据） |
| `data/feedback_analysis.csv` | 分桶分析 CSV 输出 |
| `data/last_analysis.json` | 反馈分析器增量状态 |

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

## 反馈闭环

- 每篇推送附带 👍/👎 inline keyboard 按钮
- 👍 直接记录
- 👎 触发追问（5个原因选项 + 自由文字输入）
- 原因选项：🔖 话题不相关 / 📏 太浅太水 / 👀 已经看过 / 🏷️ 领域不对 / ✍️ 其他
- 反馈由 Hermes Gateway Telegram adapter 拦截处理
- 每3天自动运行反馈分析报告

## 数据源

| 源 | API | 日均论文量 | 特点 |
|----|-----|-----------|------|
| HuggingFace Daily Papers | `/api/daily_papers` | ~50篇 | 社区投票，质量较高 |
| ModelScope Papers | `/api/v1/papers` | ~20/页 | 中文 AI 覆盖，自带 AI 预评分 |

跨源去重：同 arxiv_id 保留 HF 版本（数据更丰富）。ModelScope InnovationScore ≥ 450 预筛。

## Reddit Observer

独立的论文覆盖率验证工具：
- 监控 r/LocalLLaMA 热门帖子，提取被讨论的论文
- 完全隔离，不碰主推送逻辑
- 14天 TTL 自动停止
- 目的：验证现有数据源覆盖率，overlap >80% 就不需要 Reddit

## 运行

```bash
# 手动运行（注意：约12分钟，需要后台运行）
cd /tmp/hermes-paper-miner-
python3 src/main.py

# 查看日志
tail -f logs/$(date +%Y-%m-%d).log

# 手动运行反馈分析
python3 src/feedback_analysis.py

# 手动运行 Reddit watcher
python3 src/reddit_watcher.py
```

**自动运行**：Hermes cronjob 每日 UTC 0:00（北京 8:00）

## 输出示例

**单篇推送：**
```
📄 [85分] OS-BLIND: The Blind Spot of Agent Safety
🏛 unknown
🔗 论文链接  📅 2026-04-17

💡 论文提出了 OS-BLIND 基准，揭示了 Computer-use Agent 的安全隐患
🔥 为什么读这篇：揭示了AI Agent执行看似无害指令时可能引发灾难性安全漏洞
🔍 深度解读：OS-BLIND直击当前Agent研发中被忽视的'指令-执行'安全鸿沟...
🛠 落地场景：
  1. Agent 安全测试基准
  2. 企业 Agent 部署风险评估
  3. 安全护栏设计方案验证
⚠️ 目前只覆盖计算机环境，未扩展到其他 Agent 类型

[👍 有用] [👎 没用]
```

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 阈值 75 分 | DeepSeek 打分偏保守，75 分每天约 3-5 篇，信息量合适 |
| Top 15 篇 | 逐篇调 API 约 3 分钟，避免 cronjob 超时 |
| 180 天新鲜度 | 过滤陈年老论文，保留半年内即可 |
| 记录所有已处理论文 | 无高分的论文也标记为已读，避免重复打分 |
| 逐篇推送 + inline keyboard | 比日报合并更方便逐篇反馈 |
| 纯 stdlib 实现 | 不依赖第三方库，cronjob 环境零配置 |
| Telegram HTML parse_mode | 论文标题含特殊字符时比 Markdown 更稳定 |
| callback_data ≤ 64 bytes | `pm:up:{paper_id}` 格式，安全 |
| 持久化打分结果 | 供 feedback_analysis.py 做 score vs feedback 一致性分析 |
| Reddit observer 隔离 | via negativa：不增加主系统复杂度 |

## 配置要求

- Python 3.8+（纯 stdlib，无第三方依赖）
- DeepSeek API Key（写入 `~/.hermes/.env`）
- Telegram Bot Token（写入 `~/.hermes/.env`）
- Hermes Agent（用于 cronjob 调度和 Telegram 回调拦截）

## License

MIT

---

[English Version →](README_EN.md)
