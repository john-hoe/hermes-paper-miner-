# ⛏️ Paper Miner — AI Paper Gold Digger

> Automatically fetches trending AI papers from HuggingFace + ModelScope, scores them via DeepSeek LLM across multiple dimensions, and delivers high-scoring papers individually to Telegram with 👍/👎 feedback buttons.

## Status

**✅ Production** — Cronjob runs daily at 8:00 AM Beijing Time, delivering to Telegram DM.

## Architecture

```
[HuggingFace Daily Papers] ──┐
                              ├── [Cross-source Dedup] → [Freshness Filter (180d)] → [Seen Papers Dedup]
[ModelScope Papers] ─────────┘
                                                              ↓
                                                    [DeepSeek Scoring (top 15)]
                                                              ↓
                                              [Filter ≥75] → [Per-paper Telegram push + inline keyboard]
                                                              ↓
                                                    [Feedback recording (feedback.jsonl)]
                                                              ↓
                                              [Score persistence (scoring_results.jsonl)]
                                                              ↓
                                              [Reddit Observer (optional, isolated)]
```

## Modules

| File | Purpose |
|------|---------|
| `src/main.py` | Main entry point, orchestrates the full pipeline |
| `src/fetcher.py` | HF Daily Papers + ModelScope dual-source fetching with error handling |
| `src/dedup.py` | seen_papers.json dedup (skip already-processed papers) |
| `src/preferences.py` | User preference management + scoring prompt template + refresh reminders |
| `src/scorer.py` | DeepSeek LLM scoring + robust JSON parsing + institution detection |
| `src/formatter.py` | Rich single-paper formatting (Telegram HTML) |
| `src/pusher.py` | Per-paper Telegram delivery + inline keyboard feedback buttons |
| `src/feedback.py` | 👍/👎 feedback recording + preference learning |
| `src/feedback_analysis.py` | Score vs feedback consistency analysis (bucket stats + CSV) |
| `src/feedback_analyzer.py` | Auto feedback analysis report every 3 days (cronjob) |
| `src/reddit_watcher.py` | Reddit r/LocalLLaMA paper monitor (isolated module, 14-day TTL) |
| `src/notion_sync.py` | Notion task board auto-sync |
| `src/config.json` | Global config (APIs, thresholds, paths) |

## Scoring System

**Base dimensions (100 points max):**
- Engineering Feasibility 40% — Open-source code? Reproduction barrier? Production-ready?
- Pain Point Relevance 30% — Real engineering pain vs benchmark padding
- Innovation 20% — Incremental vs breakthrough
- Commercial Potential 10% — Productization feasibility

**Bonuses:**
- Top institution (Meta, Google, OpenAI, Stanford, Tsinghua, etc.) +5~10
- User preference hit +10~15

**Push threshold: 75** | **Max scored per run: 15** | **Freshness: 180 days**

## Feedback Loop

- Each pushed paper has 👍/👎 inline keyboard buttons
- 👍 recorded directly
- 👎 triggers follow-up (5 reason options + free text)
- Reasons: 🔖 Off-topic / 📏 Too shallow / 👀 Already read / 🏷️ Wrong domain / ✍️ Other
- Feedback intercepted by Hermes Gateway Telegram adapter
- Auto analysis report every 3 days

## Data Sources

| Source | API | Daily Volume | Notes |
|--------|-----|-------------|-------|
| HuggingFace Daily Papers | `/api/daily_papers` | ~50 | Community upvoted, higher quality |
| ModelScope Papers | `/api/v1/papers` | ~20/page | Chinese AI coverage, built-in AI scoring |

Cross-source dedup: same arxiv_id → keep HF version (richer data). ModelScope InnovationScore ≥ 450 pre-filter.

## Reddit Observer

An isolated paper coverage verification tool:
- Monitors r/LocalLLaMA hot posts, extracts mentioned paper arxiv IDs
- Completely isolated from the main pipeline
- 14-day hardcoded TTL (auto-stop)
- Purpose: verify if current data sources have adequate coverage. If overlap >80%, Reddit adds no value.

## Running

```bash
# Manual run (note: ~12 min, run in background)
cd /tmp/hermes-paper-miner-
python3 src/main.py

# Check logs
tail -f logs/$(date +%Y-%m-%d).log

# Manual feedback analysis
python3 src/feedback_analysis.py

# Manual Reddit watcher
python3 src/reddit_watcher.py
```

**Automated**: Hermes cronjob daily at UTC 0:00 (Beijing 8:00)

## Output Example

**Single paper push:**
```
📄 [85] OS-BLIND: The Blind Spot of Agent Safety
🏛 unknown
🔗 Paper link  📅 2026-04-17

💡 Introduces OS-BLIND benchmark revealing Computer-use Agent safety blind spots
🔥 Why read: Reveals how AI agents can trigger catastrophic actions from benign instructions
🔍 Deep take: OS-BLIND targets the overlooked instruction-execution safety gap...
🛠 Scenarios:
  1. Agent safety testing benchmark
  2. Enterprise agent deployment risk assessment
  3. Safety guardrail design validation
⚠️ Only covers computer environments, not other agent types

[👍 Useful] [👎 Not useful]
```

## Key Design Decisions

| Decision | Reason |
|----------|--------|
| Threshold 75 | DeepSeek scores conservatively; 75 yields ~3-5 papers/day |
| Top 15 papers | ~3 min sequential API calls, avoids cronjob timeout |
| 180-day freshness | Filters out old papers |
| Record all processed papers | Even below-threshold papers marked as seen to avoid re-scoring |
| Per-paper push + inline keyboard | Easier per-paper feedback than daily digest |
| Pure stdlib | Zero dependency, works in cronjob environment |
| Telegram HTML parse_mode | More stable than Markdown for paper titles with special chars |
| callback_data ≤ 64 bytes | `pm:up:{paper_id}` format, safe |
| Persist scoring results | Enables score vs feedback consistency analysis |
| Isolated Reddit observer | Via negativa: don't add complexity to the main system |

## Requirements

- Python 3.8+ (pure stdlib, no third-party dependencies)
- DeepSeek API Key (in `~/.hermes/.env`)
- Telegram Bot Token (in `~/.hermes/.env`)
- Hermes Agent (for cronjob scheduling and Telegram callback interception)

## License

MIT
