# Paper Miner v2 Feature Plan

## 概述

基于多视角讨论（PG / Karpathy / 张一鸣 / 费曼），确定 4 个功能点，2 个 P0 + 2 个 P1。

---

## P0-A：偏好自适应学习

### 目标
让 👍👎 反馈按钮不再是摆设。反馈数据回灌到 `user_preferences.json` 的 focus_area 权重中。

### 决策记录
- Q1：只做 A（调权重），B（提取新关键词）Phase 2 再做
- Q2：按 reason 分类处理
  - `topic` → 降低对应 focus_area 权重
  - `domain` → 降低权重 + 加入 reject_areas（如不存在）
  - `shallow` / `seen` / `free_text` → 不动 focus_area（不是方向问题）
  - 用户明确说"不要推 XX"→ 立即加入 reject_areas，不走批量流程
- Q3：平滑公式 `新权重 = 旧权重 * 0.8 + 信号 * 0.2`
- Q4：每 3 天反馈分析器运行时批量调整

### 修改文件
1. `src/feedback_analyzer.py` — 实现 `auto_adjust_weights()`
2. `src/preferences.py` — 添加 `adjust_weight()` 和 `add_reject_area()` 函数

### 实现逻辑

#### auto_adjust_weights(analysis, prefs)
```
输入：
  - analysis: 反馈分析结果（含 papers_up, papers_down, reasons）
  - prefs: user_preferences.json 当前内容
  - scoring_results: 从 scoring_results.jsonl 加载（用于 cross-reference preference_hit）

处理流程：
1. 加载 scoring_results.jsonl，构建 paper_id → preference_hit 映射
2. 遍历 papers_up：
   - 查找该 paper_id 的 preference_hit
   - 如果 hit 了某个 focus_area → 该方向信号 = 1.0
3. 遍历 papers_down：
   - 查找 paper_id 的 preference_hit + reason
   - reason=topic → hit 的 focus_area 信号 = -1.0
   - reason=domain → hit 的 focus_area 信号 = -1.0 + 加入 reject_areas
   - reason=shallow/seen → 不处理
4. 汇总每个 focus_area 的信号，用平滑公式调整：
   new_weight = old_weight * 0.8 + signal * 0.2
   clamp 到 [0.1, 1.0]
5. 如果有变更，save_preferences()
6. 返回变更记录（用于日志/报告）
```

### Acceptance Test（Happy Path）
- 给定：3 天内有 2 篇 👍（hit "RAG" 和 "Agent"），1 篇 👎 reason=topic（hit "RAG"）
- RAG 信号：(1.0 + -1.0) / 2 = 0.0 → 权重不变
- Agent 信号：1.0 → new = old * 0.8 + 1.0 * 0.2 = old*0.8 + 0.2
- 验证：RAG 权重不变，Agent 权重上升

### Edge Cases
- feedback.jsonl 为空 → 不调整，日志记录"无新反馈"
- paper_id 在 scoring_results.jsonl 中找不到 → 跳过该条反馈
- focus_area 权重调整后 < 0.1 → clamp 到 0.1
- focus_area 权重调整后 > 1.0 → clamp 到 1.0
- reject_areas 已存在该关键词 → 不重复添加

---

## P0-B：推送去噪

### 目标
0 篇过阈值时发通知（防以为系统挂了），高分密集时正常全推。

### 决策记录
- Q5：0 篇时发"今天没有高分论文"消息
- Q6：5 篇以上时全部正常推，不做特殊处理

### 修改文件
1. `src/pusher.py` — 添加 `send_no_papers_message(config)` 函数
2. `src/main.py` — Step 6 判断 scored_results 为空时调用 send_no_papers_message

### 实现逻辑

```python
# pusher.py 新增
def send_no_papers_message(config):
    """发送无高分论文通知"""
    text = "📭 今天没有高分论文（>75分）\n数据源正常，明天继续淘金。"
    # 复用 _call_telegram_api 发送

# main.py Step 6 修改
if not scored_results:
    send_no_papers_message(config)
    logger.info("No papers above threshold, sent notification")
else:
    for result in scored_results:
        send_paper_message(result, config)
```

### Acceptance Test
- 某天 0 篇过阈值 → Telegram 收到"📭 今天没有高分论文"消息
- 某天 8 篇过阈值 → 全部正常逐篇推送 + 总结消息

### Edge Cases
- Telegram API 发送失败 → 记日志，不 crash
- 连续多天 0 篇 → 每天都发通知（用户能判断系统是否正常）

---

## P1-A：代码/资源链接标注

### 目标
推送时自动检测并标注论文附带的 GitHub repo / project page。

### 决策记录
- Q7：A+B 都做（标题加 [有代码🔧] emoji + 链接区显示代码地址）

### 修改文件
1. `src/formatter.py` — 修改 `format_single_paper()` 

### 实现逻辑

```python
# formatter.py format_single_paper() 修改

# 1. 标题行：如果有 github_repo，标题后加 [有代码🔧]
title_line = f"<b>{score}分 | "
if paper.get("github_repo"):
    title_line += f"[有代码🔧] "
title_line += f"{title}</b>"

# 2. 链接区：在论文链接后，如果有 github_repo 则加一行
link_section = f"\n📄 <a href=\"{paper_url}\">论文链接</a>"
if paper.get("github_repo"):
    link_section += f"\n🔧 <a href=\"{github_repo}\">代码仓库</a>"
```

### 数据来源
- HF papers：`paper.get("github_repo")` — fetcher.py 已采集
- ModelScope papers：`paper.get("github_repo")` — 从 `CodeLink` 字段映射
- 如果两个字段都为空 → 不显示任何代码标注

### Acceptance Test
- 论文有 github_repo="github.com/foo/bar" → 标题显示 [有代码🔧]，链接区有代码仓库链接
- 论文无 github_repo → 标题无 emoji，链接区只有论文链接

### Edge Cases
- github_repo 为空字符串 → 视为无代码
- github_repo 为非 GitHub URL（如 gitlab.com）→ 正常显示
- github_repo 为相对路径或无效 URL → 跳过显示（做 URL 格式校验）

---

## P1-B：周报汇总

### 目标
每周日自动生成周报推送。

### 决策记录
- Q8：每周日晚 8 点（北京时间）
- Q9：完整版（推送统计 + Top 3 必读 + 方向权重变化趋势）

### 实现方案
新建独立脚本 + 独立 cronjob。

### 修改文件
1. 新建 `src/weekly_digest.py` — 周报生成器
2. 新建 cronjob — 每周日 UTC 12:00（北京 20:00）

### weekly_digest.py 逻辑

```
输入：
  - scoring_results.jsonl（本周所有评分记录）
  - feedback.jsonl（本周所有反馈）
  - user_preferences.json（当前权重 vs 周初权重）

流程：
1. 筛选本周数据（过去7天）
2. 统计：
   - 本周推送 N 篇，👍 M 篇，👎 K 篇
   - 最热方向（按 preference_hit 出现频率排序）
   - 方向权重变化（当前权重 vs 7天前）
3. 选 Top 3 必读（score 最高且未被 👎 的）
4. 生成 Telegram 消息（HTML 格式）
5. 调用 pusher 发送

输出格式：
📊 Paper Miner 周报（4.14-4.20）

📬 本周推送：23篇 | 👍 8篇 | 👎 2篇

🔥 最热方向：
  RAG — 7篇 | Agent — 5篇 | 推理优化 — 4篇

📈 方向权重变化：
  RAG 0.8→0.9 ↑ | 多模态 0.6→0.5 ↓ | Agent 0.7→0.7 →

🏆 本周 Top 3 必读：
  1. [92分] 论文标题 → one_liner
  2. [89分] 论文标题 → one_liner
  3. [87分] 论文标题 → one_liner
```

### 权重变化追踪
需要记录"上周权重快照"。方案：`data/preferences_snapshot.json`，每周日生成周报前先保存当前快照，对比上周快照。

### Acceptance Test
- 周日 20:00 自动推送周报
- 周报包含完整的 3 个板块（统计/方向/Top3）
- 如果本周 0 篇推送 → 周报显示"本周无推送"

### Edge Cases
- 首次运行无上周快照 → 方向权重变化显示"首次记录，无对比数据"
- scoring_results.jsonl 无本周数据 → 只显示"本周无推送"
- Top 3 中有被 👎 的论文 → 排除，从后面补

---

## 任务拆解

| ID | 任务 | 优先级 | 依赖 |
|----|------|--------|------|
| PM-201 | preferences.py 添加 adjust_weight() 和 add_reject_area() | P0 | 无 |
| PM-202 | feedback_analyzer.py 实现 auto_adjust_weights() | P0 | PM-201 |
| PM-203 | 集成测试：模拟反馈数据验证权重调整 | P0 | PM-202 |
| PM-204 | pusher.py 添加 send_no_papers_message() | P0 | 无 |
| PM-205 | main.py Step 6 集成去噪逻辑 | P0 | PM-204 |
| PM-206 | formatter.py 添加代码/资源链接标注 | P1 | 无 |
| PM-207 | 新建 weekly_digest.py | P1 | 无 |
| PM-208 | 创建周报 cronjob | P1 | PM-207 |
| PM-209 | 端到端测试 + 部署验证 | P1 | 全部 |

## 执行顺序
PM-201 → PM-202 → PM-203 → PM-204 → PM-205 → PM-206 → PM-207 → PM-208 → PM-209
