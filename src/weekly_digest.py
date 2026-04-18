"""PM-207: 周报汇总生成器 — 每周日自动推送本周 Paper Miner 汇总。

功能：
- 本周推送统计（N篇 / 👍M篇 / 👎K篇）
- 最热方向排名
- 方向权重变化趋势（vs 上周快照）
- Top 3 必读论文回顾
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCORING_PATH = os.path.join(DATA_DIR, "scoring_results.jsonl")
FEEDBACK_PATH = os.path.join(DATA_DIR, "feedback.jsonl")
PREFS_PATH = os.path.join(DATA_DIR, "user_preferences.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "preferences_snapshot.json")


def _load_jsonl(path):
    """加载 JSONL 文件。"""
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _load_json(path):
    """加载 JSON 文件。"""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    """保存 JSON 文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _filter_week(records, timestamp_field="timestamp", weeks_ago=0):
    """筛选最近 N 周的记录。"""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(weeks=weeks_ago + 1)
    week_end = now - timedelta(weeks=weeks_ago)
    filtered = []
    for r in records:
        ts = r.get(timestamp_field, "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if week_start <= dt < week_end if weeks_ago > 0 else dt >= week_start:
                filtered.append(r)
        except ValueError:
            continue
    return filtered


def _filter_this_week(records, timestamp_field="timestamp"):
    """筛选本周记录（过去7天）。"""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    filtered = []
    for r in records:
        ts = r.get(timestamp_field, "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= week_ago:
                filtered.append(r)
        except ValueError:
            continue
    return filtered


def generate_digest():
    """生成周报内容。"""
    # 加载数据
    scoring_records = _load_jsonl(SCORING_PATH)
    feedback_records = _load_jsonl(FEEDBACK_PATH)
    current_prefs = _load_json(PREFS_PATH) or {"focus_areas": [], "reject_areas": []}
    last_snapshot = _load_json(SNAPSHOT_PATH)

    # 筛选本周数据
    week_scoring = _filter_this_week(scoring_records)
    week_feedback_up = [r for r in _filter_this_week(feedback_records) if r.get("feedback") == "up"]
    week_feedback_down = [r for r in _filter_this_week(feedback_records) if r.get("feedback") == "down"]

    # 统计
    pushed_count = len(week_scoring)
    up_count = len(week_feedback_up)
    down_count = len(week_feedback_down)

    # 最热方向
    from collections import Counter
    hits = Counter()
    for r in week_scoring:
        hit = r.get("preference_hit")
        if hit:
            hits[hit] += 1
    top_areas = hits.most_common(5)

    # 方向权重变化
    weight_changes = []
    current_areas = {a["keyword"]: a.get("weight", 0.5) for a in current_prefs.get("focus_areas", [])}
    if last_snapshot:
        old_areas = {a["keyword"]: a.get("weight", 0.5) for a in last_snapshot.get("focus_areas", [])}
        for keyword, new_w in current_areas.items():
            old_w = old_areas.get(keyword)
            if old_w is not None:
                diff = new_w - old_w
                arrow = "↑" if diff > 0.01 else ("↓" if diff < -0.01 else "→")
                weight_changes.append((keyword, old_w, new_w, arrow))
            else:
                weight_changes.append((keyword, "?", new_w, "🆕"))
    else:
        weight_changes = [(k, "?", w, "🆕") for k, w in current_areas.items()]

    # Top 3 必读（score 最高且未被 👎 的）
    downed_papers = {r["paper_id"] for r in week_feedback_down}
    candidates = [r for r in week_scoring if r.get("paper_id") not in downed_papers]
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    top3 = candidates[:3]

    # 获取日期范围
    now = datetime.now(timezone.utc)
    # 转成北京时间显示
    bj_now = now + timedelta(hours=8)
    week_ago_bj = bj_now - timedelta(days=7)
    date_range = f"{week_ago_bj.strftime('%m.%d')}-{bj_now.strftime('%m.%d')}"

    return {
        "date_range": date_range,
        "pushed_count": pushed_count,
        "up_count": up_count,
        "down_count": down_count,
        "top_areas": top_areas,
        "weight_changes": weight_changes,
        "top3": top3,
        "is_first_week": last_snapshot is None,
    }


def format_digest(digest):
    """格式化周报为 Telegram HTML 消息。"""
    lines = []
    lines.append(f"📊 <b>Paper Miner 周报</b>（{digest['date_range']}）")
    lines.append("")

    # 板块1：统计
    lines.append(f"📬 本周推送：{digest['pushed_count']}篇 | 👍 {digest['up_count']}篇 | 👎 {digest['down_count']}篇")

    # 板块2：最热方向
    if digest["top_areas"]:
        lines.append("")
        lines.append("🔥 <b>最热方向：</b>")
        for area, count in digest["top_areas"]:
            lines.append(f"  · {area} — {count}篇")
    elif digest["pushed_count"] == 0:
        lines.append("")
        lines.append("📭 本周无推送")

    # 板块3：方向权重变化
    if digest["weight_changes"]:
        lines.append("")
        if digest["is_first_week"]:
            lines.append("📈 <b>方向权重（首次记录，无对比数据）：</b>")
        else:
            lines.append("📈 <b>方向权重变化：</b>")
        for keyword, old_w, new_w, arrow in digest["weight_changes"]:
            if isinstance(old_w, float):
                lines.append(f"  · {keyword} {old_w:.2f}→{new_w:.2f} {arrow}")
            else:
                lines.append(f"  · {keyword} {new_w:.2f} {arrow}")

    # 板块4：Top 3 必读
    if digest["top3"]:
        lines.append("")
        lines.append("🏆 <b>本周 Top 3 必读：</b>")
        for i, r in enumerate(digest["top3"], 1):
            title = r.get("title", "未知")[:50]
            score = r.get("score", 0)
            one_liner = r.get("one_liner", "")
            line = f"  {i}. [{score}分] {title}"
            if one_liner:
                line += f"\n     {one_liner[:60]}"
            lines.append(line)

    return "\n".join(lines)


def save_snapshot():
    """保存当前偏好快照（用于下周对比）。"""
    current_prefs = _load_json(PREFS_PATH)
    if current_prefs:
        _save_json(SNAPSHOT_PATH, current_prefs)


def run():
    """主入口。"""
    # 先保存快照（在生成周报前保存，记录本周状态）
    save_snapshot()

    digest = generate_digest()
    text = format_digest(digest)

    # 通过 Telegram 推送
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pusher import _get_bot_token, _get_chat_id, _call_telegram_api

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    token = _get_bot_token(config)
    chat_id = _get_chat_id(config)

    if token:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        result = _call_telegram_api("sendMessage", token, payload)
        if result:
            print(f"✅ 周报已推送 (msg_id={result})")
        else:
            print(text)
    else:
        print(text)


if __name__ == "__main__":
    run()
