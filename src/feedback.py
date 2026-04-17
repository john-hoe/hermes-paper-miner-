"""PM-005: 反馈数据处理与偏好学习

功能：
1. 存储 👍/👎 反馈到 feedback.jsonl
2. 根据反馈数据动态调整偏好权重
3. 定期从反馈中提取新的关注/拒绝方向
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("paper_miner")


def get_feedback_path(config):
    """获取反馈数据文件路径。"""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    return os.path.join(base_dir, "data", "feedback.jsonl")


def record_feedback(paper_id, feedback_type, paper_result=None):
    """记录一条反馈数据。
    
    Args:
        paper_id: 论文 ID (arxiv_id)
        feedback_type: "up" 或 "down"
        paper_result: 当时的打分结果（用于后续偏好学习）
    """
    path = get_feedback_path(None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    record = {
        "paper_id": paper_id,
        "feedback": feedback_type,
        "timestamp": datetime.now().isoformat(),
    }
    
    # 附带论文元信息（便于后续分析）
    if paper_result:
        record["score"] = paper_result.get("score", 0)
        record["title"] = paper_result.get("paper", {}).get("title", "")
        record["one_liner"] = paper_result.get("one_liner", "")
        record["scenarios"] = paper_result.get("scenarios", [])
        record["preference_hit"] = paper_result.get("preference_hit")
        record["institution"] = paper_result.get("institution", "")
    
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    logger.info(f"反馈已记录: {paper_id} → {feedback_type}")


def load_feedback_data(config=None):
    """加载所有反馈数据。"""
    path = get_feedback_path(config)
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


def analyze_feedback_preferences(feedback_records):
    """从反馈数据中提取偏好信号。
    
    Returns:
        {
            "liked_institutions": [...],   # 👍多的机构
            "disliked_institutions": [...], # 👎多的机构
            "liked_scores_avg": float,     # 👍论文的平均分
            "disliked_scores_avg": float,  # 👎论文的平均分
            "total_up": int,
            "total_down": int,
        }
    """
    up_records = [r for r in feedback_records if r.get("feedback") == "up"]
    down_records = [r for r in feedback_records if r.get("feedback") == "down"]
    
    # 统计机构偏好
    inst_up = {}
    inst_down = {}
    for r in up_records:
        inst = r.get("institution", "unknown")
        inst_up[inst] = inst_up.get(inst, 0) + 1
    for r in down_records:
        inst = r.get("institution", "unknown")
        inst_down[inst] = inst_down.get(inst, 0) + 1
    
    # 找出明显偏好/厌恶的机构（>=2次且差值>=2）
    liked_inst = [k for k, v in inst_up.items() if v >= 2 and v - inst_down.get(k, 0) >= 2]
    disliked_inst = [k for k, v in inst_down.items() if v >= 2 and v - inst_up.get(k, 0) >= 2]
    
    up_scores = [r.get("score", 0) for r in up_records if r.get("score")]
    down_scores = [r.get("score", 0) for r in down_records if r.get("score")]
    
    return {
        "liked_institutions": liked_inst,
        "disliked_institutions": disliked_inst,
        "liked_scores_avg": sum(up_scores) / len(up_scores) if up_scores else 0,
        "disliked_scores_avg": sum(down_scores) / len(down_scores) if down_scores else 0,
        "total_up": len(up_records),
        "total_down": len(down_records),
    }


def get_feedback_stats():
    """获取反馈统计摘要（供调试/展示用）。"""
    records = load_feedback_data()
    if not records:
        return "暂无反馈数据"
    
    analysis = analyze_feedback_preferences(records)
    return (
        f"📊 反馈统计：👍 {analysis['total_up']} | 👎 {analysis['total_down']}\n"
        f"👍 平均分：{analysis['liked_scores_avg']:.0f} | 👎 平均分：{analysis['disliked_scores_avg']:.0f}"
    )
