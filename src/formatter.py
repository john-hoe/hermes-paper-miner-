"""PM-003.1 + PM-003.2: 日报合并格式化 + 偏好保鲜提醒"""

from datetime import datetime


def format_paper_block(paper_result):
    """格式化单篇论文的推送块。"""
    score = paper_result.get("score", 0)
    institution = paper_result.get("institution", "unknown")
    pref_hit = paper_result.get("preference_hit")
    one_liner = paper_result.get("one_liner", "")
    scenarios = paper_result.get("scenarios", [])
    caveat = paper_result.get("caveat", "")
    paper = paper_result.get("paper", {})

    lines = []
    # 标题行
    title_line = f"📄 [{score}分] [{institution}] {paper.get('title', '未知')}"
    lines.append(title_line)

    # 链接行 + 发布日期
    link = paper.get("url", "")
    pub = paper.get("published", "")[:10]  # 取日期部分
    date_tag = f" | 📅 {pub}" if pub else ""
    lines.append(f"🔗 {link}{date_tag}")

    # 偏好命中
    if pref_hit:
        lines.append(f"🎯 命中偏好：{pref_hit}")

    lines.append("")

    # 一句话总结
    if one_liner:
        lines.append(f"💡 {one_liner}")

    # 落地场景
    if scenarios:
        lines.append("🛠 落地场景预测：")
        for i, s in enumerate(scenarios, 1):
            lines.append(f"  {i}. {s}")

    # 劝退点
    if caveat:
        lines.append(f"⚠️ 劝退点：{caveat}")

    return "\n".join(lines)


def format_daily_digest(results, remind_text=None):
    """将多篇论文合并为单条日报。"""
    today = datetime.now().strftime("%Y-%m-%d")
    separator = "━" * 20

    parts = [f"⛏️ 今日 AI 淘金日报 | {today}", "", separator]

    for i, r in enumerate(results):
        if i > 0:
            parts.append("")
            parts.append(separator)
        parts.append("")
        parts.append(format_paper_block(r))

    # 底部统计
    parts.append("")
    parts.append(separator)
    parts.append(f"共 {len(results)} 篇高分好文 | 数据源：Hugging Face Daily Papers")

    # 偏好提醒
    if remind_text:
        parts.append("")
        parts.append(remind_text)

    return "\n".join(parts)


def format_no_high_digest(max_score):
    """格式化"无高分"降级提示。"""
    return f"🚫 今日无高分好文，最高分为 {max_score} 分，已跳过推送。明天见！"
