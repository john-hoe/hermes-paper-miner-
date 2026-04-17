---
name: paper-miner-ops
description: Operational knowledge for the Paper Miner (AI论文淘金器) project — cronjob maintenance, troubleshooting, and known issues.
---

# Paper Miner Operations

## Quick Reference

- **GitHub**: https://github.com/john-hoe/hermes-paper-miner-
- **Local path**: `/tmp/hermes-paper-miner-/`
- **Cronjob ID**: `42d5dd176035` — daily at UTC 0:00 (Beijing 8:00), delivers to Telegram
- **Notion Task Board**: DB ID `3421d5e7-bdab-8168-a27b-d4c1b9130b3a`
- **LLM**: DeepSeek (`deepseek-chat`) via `https://api.deepseek.com/chat/completions`
- **API Key env var**: `DEEPSEEK_API_KEY` (in `~/.hermes/.env`)

## Architecture

```
src/main.py → fetcher(HF + ModelScope) → dedup_cross_source → dedup(seen) → preferences → scorer → formatter (single paper HTML)
                                                                                               → pusher (逐篇 Telegram API + inline keyboard)
                                                                                               → feedback (记录反馈到 feedback.jsonl)
                                                                                               → notion_sync
```

**v2 改造（2026-04-17）**：从合并日报改为逐篇独立推送 + 👍/👎 反馈按钮。
- `formatter.py` — 单篇 HTML 格式，含 🔥为什么读、🔍深度解读（高信息密度）
- `pusher.py` — 逐篇 `sendMessage` + inline keyboard，完毕后发统计总结
- `feedback.py` — 新建，记录反馈到 `data/feedback.jsonl`，支持偏好分析
- `preferences.py` — PROMPT_TEMPLATE 增加 `why_read` + `deep_take` 字段
- `main.py` — Step 6 改为循环逐篇推送，Step 7 发总结

## Data Sources

| Source | API | Paper Count | Notes |
|--------|-----|-------------|-------|
| HuggingFace Daily Papers | `https://huggingface.co/api/daily_papers` | ~50/day | Community upvoted, higher quality |
| ModelScope Papers | `https://modelscope.cn/api/v1/papers?PageNumber=1&PageSize=20` | ~20/page | Chinese AI coverage, built-in AI scoring |

Cross-source dedup: same `arxiv_id` → keep HF version (richer data). ModelScope-only papers (no arxiv_id) are preserved.
ModelScope pre-filter: `InnovationScore >= 450` (configurable) to skip low-quality papers before LLM scoring.

## ModelScope Papers API（待集成）

**端点**: `https://modelscope.cn/api/v1/papers?PageNumber=1&PageSize=10`

关键发现（2026-04-16 实测）：
- 分页参数：`PageNumber` + `PageSize`（不是 `page`/`size`，后者被忽略）
- 总量 ~230K 篇，默认按最新排序
- `type`、`domain`、`keyword`、`StartTime`、`PublishDate` 等过滤参数**全部被忽略**，始终返回全量
- 无 hot/trending/recommend 端点（`/papers/recommend`、`/papers/hot`、`/papers/search` 均返回错误）
- 每篇论文自带 AI 预评分：`ImpactScore`、`InnovationScore`、`TechnicalDepthScore`（满分500）
- 有 `AbstractCn`（AI翻译中文摘要）、`Extra.summary`（AI章节分析）、`Extra.comment_and_rank_dict`（评分评语）
- `ArxivId` 字段可跟 HF 数据去重
- 集成策略：拉 PageNumber=1 PageSize=20 获取最新论文，用 ArxivId 与 HF 去重，可用 InnovationScore>=450 预筛减少 LLM 成本

## Known Issues & Pitfalls

1. **HF Daily Papers API field mapping**: `upvotes` is at `item` level (NOT inside `item.paper`), date field is `publishedAt` (not `published`).
2. **Double-scoring anti-pattern (fixed)**: Never discard non-threshold results during scoring then re-score. Record ALL results, filter afterward.
3. **Mark ALL papers as seen**: Even papers below threshold must be added to `seen_papers.json`, otherwise they get re-scored every day.
4. **execute_code sandbox cannot access external APIs**: Always use `terminal` for network requests (curl, python with urllib).
5. **50 papers ≈ 12 minutes**: Sequential DeepSeek API calls, ~13s per paper. **The 300s foreground timeout is insufficient.** Always run in background mode with `notify_on_complete=true` and monitor via the log file.
6. **DeepSeek balance depletion**: Monitor balance; if depleted, swap to another provider in `config.json`.
7. **Telegram group chat_id "chat not found"**: 群 ID `1003520617106` 返回 400，bot 可能未正确加入群或群 ID 格式有误。DM ID `6202626135` 正常工作。排查时先确认 bot 在群内有权限。
8. **Telegram HTML parse_mode**: 论文标题含 `_`、`*`、`[` 等字符时 Markdown 模式会解析错误，HTML 模式更稳定。用 `<b>` 加粗，`<a href="">` 做链接。
9. **callback_data 限制 64 bytes**: `pm:up:{paper_id}` 格式，arxiv_id 如 `2404.12345v2` 约 20 字节，安全。

## Telegram 推送

- **模式**：直接调用 Telegram Bot API（不再依赖 cronjob auto-deliver）
- **Bot Token**: `TELEGRAM_BOT_TOKEN` in `~/.hermes/.env`（token prefix `8748587209`）
- **DM chat_id**: `6202626135`（John 的私聊）
- **群 chat_id**: `1003520617106`（群聊，bot 需要被 @ 才响应）
- **parse_mode**: HTML（比 Markdown 更稳定，不会因为论文标题中的特殊字符炸）
- **每篇消息带 inline keyboard**: `👍 有用` / `👎 没用`，callback_data 格式 `pm:up:{paper_id}` / `pm:down:{paper_id}`
- **推送完毕发总结**: 分数分布（最高/均分/最低）+ 数据源统计
- **降级兼容**: Telegram API 失败时回退到 `deliver_output()`（print stdout → cronjob capture）

## Config Changes

All config in `src/config.json`. Key fields:
- `hf_api_url` — HuggingFace Daily Papers API
- `modelscope.enabled` — enable/disable ModelScope source
- `modelscope.api_url` — ModelScope papers API
- `modelscope.page_size` — papers per fetch (default 20)
- `modelscope.min_innovation_score` — pre-filter threshold (default 450)
- `llm.api_url` / `llm.model` — swap LLM provider here
- `scoring.push_threshold` — default 75
- `telegram.delivery_mode` — `direct_api`（v2）或 `cronjob_auto`（旧版降级）
- `telegram.chat_id` — 推送目标 chat_id
- `feedback.path` — `data/feedback.jsonl`
- `preferences.path` — `data/user_preferences.json`
- `dedup.seen_papers_path` — `data/seen_papers.json`

## Cronjobs

| Name | ID | Schedule | Purpose |
|------|----|----------|---------|
| Paper Miner | `42d5dd176035` | Daily UTC 0:00 (BJ 8:00) | 论文抓取+评分+推送 |
| 反馈分析 | `7e65758ac7cf` | Every 3 days | 分析用户反馈，推送报告 |

## Manual Run

**IMPORTANT**: The pipeline takes ~12 minutes for 50 papers. Do NOT run in foreground — it will timeout at 300s. Use background mode:

```
# Run in background
terminal(background=true, command="cd /tmp/hermes-paper-miner- && python3 src/main.py 2>&1", notify_on_complete=true, timeout=600)

# Monitor progress via log file (stdout is empty — output goes to logs)
terminal(command="tail -5 /tmp/hermes-paper-miner-/logs/2026-04-17.log")

# When done, fetch the formatted digest from background process log
process(action="log", session_id="...", limit=100)
```

**Why background**: `process(action="wait")` is clamped to 60s, so repeated `sleep + tail` on the log file is the reliable monitoring approach.

**v2 注意**: 逐篇推送模式下，stdout 只记录降级消息。正常论文直接通过 Telegram API 发送，查看推送结果需要看 Telegram 消息。

## Telegram 反馈闭环（Hermes Gateway 拦截）

用户点击 👍/👎 按钮后，Telegram 发送 `callback_query`，由 Hermes gateway 的 Telegram adapter 拦截处理。

**实现位置**: `~/.hermes/hermes-agent/gateway/platforms/telegram.py` → `_handle_callback_query()` 方法

**原理**: 在 `_handle_callback_query()` 中，`mp:` model picker 回调之后、`ea:` exec approval 回调之前，插入 `pm:` 前缀判断。Hermes 常驻运行（polling/webhook），所以能实时收到 callback。

**Callback 前缀**:
- `pm:up:{paper_id}` — 👍 直接记录
- `pm:down:{paper_id}` — 👎 记录 + 发追问消息
- `pmr:{paper_id}:{reason}` — 原因选择（topic/shallow/seen/domain）
- `pmf:{paper_id}` — 请求自由文字输入

**处理流程**:
1. 👍：记录 + 原消息标记 `👍 有用`，移除按钮
2. 👎：记录 + 原消息标记 `👎 没用（待反馈…）` + reply 发追问消息（5个选项按钮）
3. 选原因：追问消息消失 + 原消息更新为 `👎 🔖 话题不相关` 等标签 + 追加 feedback.jsonl（含 reason 字段）
4. 选 ✍️：提示用户打字 → `_pm_pending_free` 字典记录 → 下一条消息被 `_handle_pm_free_text()` 拦截 → 记录 free_text + 更新原消息
5. 自由输入 5 分钟超时自动清理

**原因选项**: 🔖 话题不相关(topic)、📏 太浅/太水(shallow)、👀 已经看过了(seen)、🏷️ 领域不对(domain)、✍️ 其他原因(free_text)

**关键内存状态**（运行时）:
- `_pm_original_msg`: `{paper_id: (chat_id, msg_id, orig_text)}` — 用于更新原消息标记
- `_pm_pending_free`: `{paper_id: {"chat_id": ..., "user": ...}}` — 等待自由输入的论文

**路径自动探测**: 先检查项目目录，再尝试 `~/hermes-paper-miner/`、`/tmp/hermes-paper-miner-/`

**修改 gateway 后需重启**: `kill $(pgrep -f "hermes_cli.main gateway")` 后会自动重启（`--replace` 模式），或 `systemctl restart hermes`。

## 反馈分析器

**脚本**: `src/feedback_analyzer.py`（每3天 cron）+ `src/feedback_analysis.py`（手动/随时）

**feedback_analysis.py** — P0-2 新增：
- 读取 `scoring_results.jsonl`（每日打分结果）+ `feedback.jsonl`
- 按分数分桶统计 👍/👎/无反馈比例
- 输出分桶表 + CSV（`data/feedback_analysis.csv`）
- 自动信号判断：高分桶 👍率 ≥60% 有正信号，<40% 可能不一致
- 用法：`python3 src/feedback_analysis.py` 或 `--csv path.csv`

**scoring_results.jsonl** — P0-2 新增，由 main.py Step 8 自动写入：
- 每条含 paper_id、score、title、why_read、deep_take、scenarios、timestamp
- 高分低分全部记录（不只是推送的）

**关键：反馈数据需要时间积累**。当前只有少量测试数据，等运行一周后有足够样本再分析。

## Reddit Observer

**脚本**: `src/reddit_watcher.py`（P1 新增）
**配置**: `config.json` → `reddit_watcher.enabled: false`（默认关）
**数据**: `data/reddit_mentions.jsonl`
**TTL**: 14天自动停止（`data/reddit_watcher_start.json`）

- 监控 r/LocalLLaMA hot posts，提取 arxiv ID
- Reddit JSON API（无需认证）
- 完全独立于主 pipeline，不碰任何现有代码
- 开启：改 config `enabled: true`，下次 cron 运行自动执行
- 手动：`python3 src/reddit_watcher.py`
- P2：两周后检查 `reddit_mentions.jsonl` 与 `seen_papers.json` 的 overlap rate

**报告内容**:
- 👍/👎 比例和总量
- 👎 原因分布
- 自由反馈摘要（最近3条）
- 优化建议（某原因出现2次以上自动提醒，如建议加入 reject_areas）
- 当前关注方向一览

**分析状态**: `data/last_analysis.json` 记录上次分析时间，增量分析用。

**手动运行**: `cd /tmp/hermes-paper-miner- && python3 src/feedback_analyzer.py`

## Cronjob Management

```
cronjob(action='list')  — check status
cronjob(action='run', job_id='42d5dd176035')  — trigger manually
cronjob(action='pause', job_id='42d5dd176035')  — pause
cronjob(action='resume', job_id='42d5dd176035')  — resume
```
