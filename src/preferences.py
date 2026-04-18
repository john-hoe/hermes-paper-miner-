"""PM-002.1 + PM-002.2: 偏好管理与 Prompt 构建"""

import json
import os
from datetime import datetime, timedelta

PROMPT_TEMPLATE = """你是一位资深 AI 工程师兼科技投资人，正在为一位技术型创业者筛选每日 AI 论文。

## 评审任务
请对以下论文进行多维度评审，输出严格的 JSON 格式。

## 待评审论文
标题：{title}
作者：{authors}
摘要：{summary}
{ms_context}

## 用户当前关注方向
{focus_areas}

## 用户不感兴趣的方向
{reject_areas}

## 评审维度（满分100分）
1. 工程落地性 (40%): 是否有开源代码？复现门槛多高？能否直接用到产品中？
2. 痛点解决度 (30%): 是解决真实工程痛点，还是单纯跑分刷榜？
3. 创新性 (20%): 思路是否新颖？是incremental还是breakthrough？
4. 出圈潜力 (10%): 商业产品化的可能性有多大？

## 附加加分
- 大厂/顶尖高校（Meta, Google, OpenAI, Anthropic, Microsoft, Stanford, MIT, 清华, 北大等）: +5~10分
- 命中用户关注方向: +10~15分（在 preference_hit 中标注具体命中哪条）

## 翻译纪律（极其重要，违反将导致严重扣分）
- 所有 AI/ML 专有名词必须保留英文原词：RAG, MoE, Agent, Transformer, LoRA, fine-tuning, inference, RLHF, DPO, CoT, few-shot, zero-shot, embedding, token, KV cache 等
- 严禁翻译成"检索增强生成"、"专家混合"等生硬中文
- 普通描述性文字用中文，但技术术语一律保留英文

## 输出格式（严格 JSON，不要添加任何 markdown 标记）
{{
    "score": <整数，最终总分>,
    "institution": "<第一作者/通讯作者所属机构，未知填 unknown>",
    "institution_bonus": <整数，机构加分 0-10>,
    "preference_hit": "<命中的关注方向，未命中填 null>",
    "preference_bonus": <整数，偏好加分 0-15>,
    "one_liner": "<一句话中文总结这篇论文做了什么，保留英文专有名词>",
    "why_read": "<为什么该读这篇：给技术型创业者的硬核理由，1-2句话，要具体不要废话，比如'首个在 7B 模型上实现 GPT-4 级 function calling 的开源方案'>",
    "deep_take": "<深度解读：与现有方案的对比、关键突破点、技术细节亮点，3-5句话，高信息密度>",
    "scenarios": [
        "<落地场景1：具体的商业/工程应用，要具体>",
        "<落地场景2>",
        "<落地场景3>"
    ],
    "caveat": "<落地劝退点：显存要求/数据要求/许可限制等>"
}}
"""


def load_preferences(filepath):
    """加载用户偏好配置。"""
    if not os.path.exists(filepath):
        return {"focus_areas": [], "reject_areas": [], "last_updated": ""}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_preferences(filepath, prefs):
    """保存用户偏好配置。"""
    prefs["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)


def build_scoring_prompt(paper, preferences):
    """为单篇论文构建完整的评审 Prompt。"""
    focus = "\n".join(
        f"- {a['keyword']} (权重: {a.get('weight', 0.5)})"
        for a in preferences.get("focus_areas", [])
    )
    reject = "\n".join(f"- {r}" for r in preferences.get("reject_areas", []))
    authors = ", ".join(paper.get("authors", [])[:5])
    
    # ModelScope 预评分上下文（如果有）
    ms_context = ""
    if paper.get("source") == "modelscope":
        ms_parts = []
        if paper.get("ms_innovation_score"):
            ms_parts.append(f"ModelScope AI 预评创新分: {paper['ms_innovation_score']}/500")
        if paper.get("ms_tech_depth_score"):
            ms_parts.append(f"ModelScope AI 预评技术深度: {paper['ms_tech_depth_score']}/500")
        if paper.get("ms_final_comment"):
            ms_parts.append(f"ModelScope AI 评语: {paper['ms_final_comment'][:300]}")
        if ms_parts:
            ms_context = "## ModelScope AI 预评估（仅供参考，请独立判断）\n" + "\n".join(f"- {p}" for p in ms_parts)
    
    return PROMPT_TEMPLATE.format(
        title=paper["title"],
        authors=authors,
        summary=paper["summary"],
        ms_context=ms_context,
        focus_areas=focus or "- 暂无设定",
        reject_areas=reject or "- 暂无设定",
    )


def should_remind_preferences(preferences, interval_days=14):
    """判断是否需要提醒用户更新偏好。"""
    last = preferences.get("last_updated", "")
    if not last:
        return True
    try:
        last_date = datetime.strptime(last, "%Y-%m-%d")
        return (datetime.now() - last_date).days >= interval_days
    except ValueError:
        return True


def adjust_weight(preferences, keyword, signal, alpha=0.2):
    """平滑调整某个 focus_area 的权重。

    公式：new_weight = old_weight * (1 - alpha) + signal * alpha
    signal > 0 提权，signal < 0 降权。权重 clamp 到 [0.1, 1.0]。

    Args:
        preferences: user_preferences dict
        keyword: 要调整的 focus_area keyword
        signal: 信号值，通常 1.0（👍）或 -1.0（👎）
        alpha: 平滑系数，默认 0.2

    Returns:
        (changed, old_weight, new_weight)
    """
    for area in preferences.get("focus_areas", []):
        if area["keyword"].lower() == keyword.lower():
            old_w = area.get("weight", 0.5)
            new_w = old_w * (1 - alpha) + signal * alpha
            new_w = max(0.1, min(1.0, round(new_w, 3)))
            area["weight"] = new_w
            return True, old_w, new_w
    return False, None, None


def add_reject_area(preferences, keyword):
    """添加一个新的 reject_area（如已存在则跳过）。

    Args:
        preferences: user_preferences dict
        keyword: 要拒绝的方向关键词

    Returns:
        True if added, False if already exists
    """
    rejects = preferences.get("reject_areas", [])
    # 大小写不敏感检查
    for r in rejects:
        if r.lower() == keyword.lower():
            return False
    rejects.append(keyword)
    preferences["reject_areas"] = rejects
    return True


def get_reminder_text(preferences):
    """生成偏好提醒文案。"""
    return (
        "🔔 [偏好保鲜提醒] 您的 AI 关注方向已使用超过 14 天，"
        "如有新方向或变动，请直接回复我「更新偏好」。"
    )
