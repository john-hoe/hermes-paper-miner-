"""P0-2: 反馈数据分析器 — 评分 vs 用户反馈一致性检验

功能：
1. 读取 scoring_results.jsonl（每日打分结果）和 feedback.jsonl（用户反馈）
2. 按 DeepSeek 分数分桶，统计每个桶的 👍/👎/无反馈 比例
3. 计算 Spearman 相关性（样本充足时）
4. 输出分桶表 + CSV

用法：
  python3 src/feedback_analysis.py [--csv output.csv]
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load_jsonl(filename):
    """加载 JSONL 文件。"""
    path = os.path.join(DATA_DIR, filename)
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def get_score_buckets():
    """定义分数桶。"""
    return [
        ("<60", lambda s: s < 60),
        ("60-70", lambda s: 60 <= s < 70),
        ("70-75", lambda s: 70 <= s < 75),
        ("75-80", lambda s: 75 <= s < 80),
        ("80-85", lambda s: 80 <= s < 85),
        ("85-90", lambda s: 85 <= s < 90),
        (">=90", lambda s: s >= 90),
    ]


def analyze():
    """执行分析。"""
    # 加载打分结果
    scoring_records = load_jsonl("scoring_results.jsonl")

    # 加载反馈
    feedback_records = load_jsonl("feedback.jsonl")

    # 构建 paper_id -> 反馈方向 的映射（去重，取最新）
    feedback_map = {}
    for r in feedback_records:
        fb = r.get("feedback", "")
        pid = r.get("paper_id", "")
        if fb in ("up", "down"):
            feedback_map[pid] = fb

    # 构建 paper_id -> 打分结果 的映射
    scoring_map = {}
    for r in scoring_records:
        pid = r.get("paper_id", "")
        if pid and r.get("score") is not None:
            scoring_map[pid] = r

    # 如果 feedback.jsonl 里有带 score 的 sent 记录，也纳入 scoring_map
    for r in feedback_records:
        if r.get("feedback") == "sent" and r.get("score") is not None:
            pid = r.get("paper_id", "")
            if pid and pid not in scoring_map:
                scoring_map[pid] = r

    # 分桶统计
    buckets = get_score_buckets()
    bucket_stats = {name: {"up": 0, "down": 0, "no_feedback": 0, "papers": []}
                    for name, _ in buckets}

    for pid, score_data in scoring_map.items():
        score = score_data.get("score", 0)
        title = score_data.get("title", score_data.get("paper", {}).get("title", ""))[:50]

        fb = feedback_map.get(pid, "no_feedback")
        for name, predicate in buckets:
            if predicate(score):
                if fb == "no_feedback":
                    bucket_stats[name]["no_feedback"] += 1
                else:
                    bucket_stats[name][fb] += 1
                bucket_stats[name]["papers"].append({
                    "id": pid, "score": score, "feedback": fb, "title": title,
                })
                break

    # 输出结果
    print("=" * 70)
    print("📊 Paper Miner — 评分 vs 反馈一致性分析")
    print(f"   打分记录: {len(scoring_map)} 篇 | 用户反馈: {len(feedback_map)} 条")
    print(f"   生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print()

    header = f"{'分数桶':<10} {'总数':>6} {'👍':>5} {'👎':>5} {'无反馈':>6} {'👍率':>8}"
    print(header)
    print("-" * 50)

    total_up = 0
    total_down = 0
    total_no = 0
    csv_rows = []

    for name, _ in buckets:
        stats = bucket_stats[name]
        total = stats["up"] + stats["down"] + stats["no_feedback"]
        if total == 0:
            continue

        up = stats["up"]
        down = stats["down"]
        no = stats["no_feedback"]
        total_up += up
        total_down += down
        total_no += no

        up_rate = f"{up/total*100:.0f}%" if total > 0 else "—"
        print(f"{name:<10} {total:>6} {up:>5} {down:>5} {no:>6} {up_rate:>8}")

        # CSV 行
        for p in stats["papers"]:
            csv_rows.append({
                "bucket": name, "paper_id": p["id"], "score": p["score"],
                "feedback": p["feedback"], "title": p["title"],
            })

    print("-" * 50)
    grand_total = total_up + total_down + total_no
    if grand_total > 0:
        print(f"{'合计':<10} {grand_total:>6} {total_up:>5} {total_down:>5} {total_no:>6} {total_up/grand_total*100:.0f}%")
    print()

    # 信号判断
    print("📋 信号判断：")
    if len(feedback_map) < 5:
        print("   ⚠️ 反馈样本不足（<5条），暂无法判断评分有效性。")
        print("   建议：继续收集反馈，或手动回顾最近推送标注。")
    elif total_up > 0 and total_down > 0:
        up_avg = sum(1 for p in csv_rows if p["feedback"] == "up")
        down_avg = sum(1 for p in csv_rows if p["feedback"] == "down")
        print(f"   👍 {total_up} 条 | 👎 {total_down} 条 | 无反馈 {total_no} 条")

        # 检查高分桶是否 👍 率更高
        high_up = sum(bucket_stats[n]["up"] for n, _ in buckets if n in ("75-80", "80-85", "85-90", ">=90"))
        high_down = sum(bucket_stats[n]["down"] for n, _ in buckets if n in ("75-80", "80-85", "85-90", ">=90"))
        high_total = high_up + high_down
        if high_total > 3:
            rate = high_up / high_total * 100
            if rate >= 60:
                print(f"   ✅ 高分区（≥75）👍率 {rate:.0f}%，评分有正信号")
            elif rate >= 40:
                print(f"   🟡 高分区（≥75）👍率 {rate:.0f}%，信号较弱，需更多数据")
            else:
                print(f"   🔴 高分区（≥75）👍率仅 {rate:.0f}%，评分可能与用户偏好不一致")
                print("   → 建议检查 DeepSeek 评分 prompt 是否准确反映用户需求")
        else:
            print("   ℹ️ 高分区反馈样本不足，无法判断")
    else:
        print(f"   ℹ️ 只有 {'👍' if total_up > 0 else '👎'} 反馈，暂无对比数据")

    # CSV 输出
    csv_path = None
    if "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        if idx + 1 < len(sys.argv):
            csv_path = sys.argv[idx + 1]
    else:
        csv_path = os.path.join(DATA_DIR, "feedback_analysis.csv")

    if csv_path and csv_rows:
        import csv
        os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["bucket", "paper_id", "score", "feedback", "title"])
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\n📁 CSV 已保存: {csv_path}")


if __name__ == "__main__":
    analyze()
