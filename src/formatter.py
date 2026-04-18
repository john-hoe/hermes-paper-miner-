"""PM-003.1 + PM-003.2: 单篇论文富格式化

改版：从合并日报改为单篇独立推送，每篇包含丰富内容。
Telegram HTML 格式（比 Markdown 更稳定）。
"""


def format_single_paper(paper_result):
    """格式化单篇论文的推送内容（Telegram HTML 格式）。
    
    返回格式：
    - text: 推送文本
    - paper_id: 论文唯一ID（用于 feedback 按钮）
    """
    score = paper_result.get("score", 0)
    institution = paper_result.get("institution", "unknown")
    pref_hit = paper_result.get("preference_hit")
    one_liner = paper_result.get("one_liner", "")
    why_read = paper_result.get("why_read", "")
    deep_take = paper_result.get("deep_take", "")
    scenarios = paper_result.get("scenarios", [])
    caveat = paper_result.get("caveat", "")
    paper = paper_result.get("paper", {})
    paper_id = paper.get("id", "unknown")

    lines = []

    # 标题行：分数 + 机构
    title = paper.get("title", "未知标题")
    github_repo = paper.get("github_repo", "")
    has_code = github_repo and github_repo.startswith("http")
    if has_code:
        lines.append(f"📄 <b>[{score}分] [有代码🔧] {title}</b>")
    else:
        lines.append(f"📄 <b>[{score}分] {title}</b>")
    lines.append(f"🏛 {institution}")

    # 链接 + 日期
    link = paper.get("url", "")
    pub = paper.get("published", "")[:10]
    if link:
        lines.append(f'🔗 <a href="{link}">论文链接</a>  📅 {pub}' if pub else f'🔗 <a href="{link}">论文链接</a>')

    # 代码仓库链接
    if has_code:
        lines.append(f'🔧 <a href="{github_repo}">代码仓库</a>')

    # 偏好命中
    if pref_hit:
        lines.append(f"🎯 命中偏好：{pref_hit}")

    lines.append("")

    # 一句话总结
    if one_liner:
        lines.append(f"💡 {one_liner}")

    # 为什么读这篇（核心卖点）
    if why_read:
        lines.append(f"🔥 <b>为什么读这篇：</b>{why_read}")

    # 深度解读
    if deep_take:
        lines.append(f"🔍 <b>深度解读：</b>\n{deep_take}")

    # 落地场景
    if scenarios:
        lines.append("🛠 <b>落地场景：</b>")
        for i, s in enumerate(scenarios, 1):
            lines.append(f"  {i}. {s}")

    # 劝退点
    if caveat:
        lines.append(f"⚠️ {caveat}")

    return {
        "text": "\n".join(lines),
        "paper_id": paper_id,
    }


def format_no_high_digest(max_score):
    """格式化"无高分"降级提示。"""
    return {
        "text": f"🚫 今日无高分好文，最高分 {max_score} 分。明天见！",
        "paper_id": None,
    }


def format_error_alert(error_brief):
    """格式化系统故障警报。"""
    return {
        "text": f"⚠️ 系统故障：{error_brief}，今日淘金任务失败。",
        "paper_id": None,
    }
