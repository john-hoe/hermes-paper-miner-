"""PM-004: 反馈分析器 — 每3天自动分析用户反馈，调整偏好权重，推送报告。"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import Counter

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FEEDBACK_PATH = os.path.join(DATA_DIR, "feedback.jsonl")
PREFS_PATH = os.path.join(DATA_DIR, "user_preferences.json")
ANALYSIS_PATH = os.path.join(DATA_DIR, "last_analysis.json")

# Reason code → human label
REASON_LABELS = {
    "topic": "🔖 话题不相关",
    "shallow": "📏 太浅/太水",
    "seen": "👀 已经看过了",
    "domain": "🏷️ 领域不对",
    "free_text": "✍️ 其他",
}

# Reason → preference adjustment strategy
REASON_ADJUSTMENTS = {
    "topic": {"action": "suggest_reject", "msg": "建议加入 reject_areas 或降低相关 focus 权重"},
    "shallow": {"action": "note", "msg": "可在 scoring prompt 中加强对技术深度的要求"},
    "seen": {"action": "note", "msg": "去重机制可能需要加强（检查 seen_papers 覆盖）"},
    "domain": {"action": "suggest_reject", "msg": "建议加入 reject_areas"},
    "free_text": {"action": "review", "msg": "需要人工查看自由文本反馈"},
}


def load_feedback():
    """Load all feedback records."""
    if not os.path.exists(FEEDBACK_PATH):
        return []
    records = []
    with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def load_last_analysis():
    """Load last analysis timestamp."""
    if not os.path.exists(ANALYSIS_PATH):
        return None
    try:
        with open(ANALYSIS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_analysis(analysis):
    """Save analysis result."""
    os.makedirs(os.path.dirname(ANALYSIS_PATH), exist_ok=True)
    with open(ANALYSIS_PATH, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def load_preferences():
    """Load current user preferences."""
    if not os.path.exists(PREFS_PATH):
        return {"focus_areas": [], "reject_areas": []}
    with open(PREFS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_preferences(prefs):
    """Save updated preferences."""
    prefs["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)


def analyze(records, since=None):
    """Analyze feedback records, optionally only since a given ISO timestamp."""
    if since:
        records = [r for r in records if r.get("timestamp", "") > since]

    if not records:
        return None

    total = len(records)
    ups = [r for r in records if r.get("feedback") == "up"]
    downs = [r for r in records if r.get("feedback") == "down"]

    # Reason distribution
    reasons = Counter()
    free_texts = []
    for r in downs:
        reason = r.get("reason")
        if reason:
            reasons[reason] += 1
        ft = r.get("free_text")
        if ft:
            free_texts.append({"paper_id": r["paper_id"], "text": ft})

    # Unique papers with feedback
    papers_up = {r["paper_id"] for r in ups}
    papers_down = {r["paper_id"] for r in downs}

    return {
        "total": total,
        "up_count": len(ups),
        "down_count": len(downs),
        "up_rate": round(len(ups) / total * 100, 1) if total else 0,
        "reasons": dict(reasons),
        "free_texts": free_texts,
        "papers_up": len(papers_up),
        "papers_down": len(papers_down),
        "analyzed_at": datetime.now().isoformat(),
    }


def build_report(analysis, prefs):
    """Build human-readable report for Telegram."""
    lines = []
    lines.append("📊 Paper Miner 反馈分析报告")
    lines.append(f"分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append(f"📈 反馈总量：{analysis['total']} 条")
    lines.append(f"  👍 有用：{analysis['up_count']} 条 ({analysis['up_rate']}%)")
    lines.append(f"  👎 没用：{analysis['down_count']} 条 ({100 - analysis['up_rate']}%)")
    lines.append("")

    if analysis["reasons"]:
        lines.append("👎 没用原因分布：")
        for code, count in sorted(analysis["reasons"].items(), key=lambda x: -x[1]):
            label = REASON_LABELS.get(code, code)
            lines.append(f"  {label}：{count} 次")
        lines.append("")

    if analysis["free_texts"]:
        lines.append("✍️ 自由反馈：")
        for ft in analysis["free_texts"][-3:]:  # 最近3条
            short = ft["text"][:80] + ("…" if len(ft["text"]) > 80 else "")
            lines.append(f"  · {short}")
        lines.append("")

    # Suggestions
    suggestions = []
    for code, count in analysis["reasons"].items():
        if count >= 2:  # 出现2次以上才建议
            adj = REASON_ADJUSTMENTS.get(code, {})
            if adj.get("action") == "suggest_reject":
                suggestions.append(f"⚠️ 「{REASON_LABELS.get(code, code)}」出现 {count} 次 → {adj['msg']}")

    if suggestions:
        lines.append("💡 优化建议：")
        for s in suggestions:
            lines.append(f"  {s}")
        lines.append("")

    lines.append("📐 当前关注方向：")
    for area in prefs.get("focus_areas", [])[:5]:
        lines.append(f"  · {area['keyword']} (权重: {area.get('weight', '?')})")

    return "\n".join(lines)


def auto_adjust_weights(analysis, prefs):
    """Auto-adjust focus area weights based on feedback (conservative)."""
    changed = False
    reason_counts = analysis.get("reasons", {})

    # If "topic" or "domain" is dominant (>50% of downs), suggest but don't auto-modify
    # Auto-adjust: slightly boost weights for papers that got 👍 (if we can match focus areas)
    # For now: just update last_updated timestamp and return whether prefs changed

    # Future: can cross-reference paper_id with scored papers to find which
    # focus_areas they matched, then adjust weights accordingly.

    # Mark analysis time
    return changed


def run():
    """Main entry point."""
    records = load_feedback()
    if not records:
        print("📭 暂无反馈数据，跳过分析。")
        return

    last = load_last_analysis()
    since = last.get("analyzed_at") if last else None

    # Analyze new records since last analysis
    new_analysis = analyze(records, since=since)
    # Also do full cumulative analysis
    full_analysis = analyze(records)

    if not new_analysis or new_analysis["total"] == 0:
        print("📭 自上次分析以来无新反馈，跳过。")
        return

    prefs = load_preferences()

    # Auto-adjust
    auto_adjust_weights(full_analysis, prefs)

    # Build report (based on new data since last analysis)
    report = build_report(new_analysis, prefs)

    # Save analysis
    save_analysis({
        "analyzed_at": datetime.now().isoformat(),
        "new_feedback_count": new_analysis["total"],
        "cumulative_total": full_analysis["total"],
        "cumulative_up_rate": full_analysis["up_rate"],
    })

    # Output report for cronjob delivery
    print(report)


if __name__ == "__main__":
    run()
