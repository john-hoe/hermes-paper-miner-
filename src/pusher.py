"""PM-003.3 + PM-003.4: Telegram 推送模块（逐篇发送 + inline keyboard 反馈）

改版：
- 每篇论文独立一条消息发送
- 附带 👍/👎 inline keyboard 反馈按钮
- 保留 deliver_output() 兼容 cronjob auto-deliver（仅用于无论文/故障等场景）
"""

import json
import logging
import urllib.request

logger = logging.getLogger("paper_miner")

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _get_bot_token(config):
    """从环境变量获取 Telegram Bot Token。"""
    import os
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        token = line.split("=", 1)[1]
                        break
    return token


def _get_chat_id(config):
    """获取推送目标 chat_id。"""
    return config.get("telegram", {}).get("chat_id", "1003520617106")


def format_alert_message(error_brief):
    """生成系统故障警报（兼容旧接口）。"""
    return f"⚠️ 系统故障：{error_brief}，今日淘金任务失败。"


def deliver_output(text):
    """兼容旧接口：print 输出（cronjob auto-deliver 模式）。
    仅用于无论文/故障等降级场景。
    """
    print(text)


def send_paper_message(paper_result, config):
    """发送单篇论文到 Telegram（含 inline keyboard 反馈按钮）。
    
    Args:
        paper_result: format_single_paper() 返回的 dict，含 text + paper_id
        config: 全局配置
        
    Returns:
        message_id: 发送成功的消息 ID，失败返回 None
    """
    from formatter import format_single_paper

    token = _get_bot_token(config)
    chat_id = _get_chat_id(config)
    
    if not token:
        logger.error("Telegram Bot Token 未找到，回退到 stdout")
        print(paper_result["text"])
        return None

    formatted = format_single_paper(paper_result)
    text = formatted["text"]
    paper_id = formatted["paper_id"]

    # 构建 inline keyboard
    keyboard = None
    if paper_id:
        keyboard = {
            "inline_keyboard": [[
                {"text": "👍 有用", "callback_data": f"pm:up:{paper_id}"},
                {"text": "👎 没用", "callback_data": f"pm:down:{paper_id}"},
            ]]
        }

    # 发送消息
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)

    return _call_telegram_api("sendMessage", token, payload)


def send_summary_message(results, config, remind_text=None):
    """发送日报总结消息（分数分布 + 统计）。
    
    在所有论文推送完毕后发送一条总结。
    """
    token = _get_bot_token(config)
    chat_id = _get_chat_id(config)
    
    if not token:
        return None

    scores = [r.get("score", 0) for r in results]
    sources = set()
    for r in results:
        p = r.get("paper", {})
        if p.get("source"):
            sources.add(p["source"])
    
    source_labels = {"huggingface": "HF", "modelscope": "MS"}
    source_str = " + ".join(source_labels.get(s, s) for s in sources) or "HF"

    lines = [
        f"⛏️ <b>今日淘金完毕</b> | 共 {len(results)} 篇高分好文",
        f"📊 分数分布：最高 {max(scores)} 分 | 均分 {sum(scores)/len(scores):.0f} 分 | 最低 {min(scores)} 分",
        f"📡 数据源：{source_str}",
    ]
    
    if remind_text:
        lines.append("")
        lines.append(remind_text)

    payload = {
        "chat_id": chat_id,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
    }
    return _call_telegram_api("sendMessage", token, payload)


def answer_callback_query(callback_query_id, token, text=""):
    """应答 Telegram callback_query（必须，否则按钮会一直转圈）。"""
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
    }
    _call_telegram_api("answerCallbackQuery", token, payload)


def _call_telegram_api(method, token, payload):
    """调用 Telegram Bot API。
    
    Returns:
        message_id on success (for sendMessage), True for other methods, None on failure
    """
    data = json.dumps(payload).encode()
    url = TELEGRAM_API_BASE.format(token=token, method=method)
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                if method == "sendMessage":
                    return result.get("result", {}).get("message_id")
                return True
            else:
                logger.error(f"Telegram API error: {result.get('description', 'unknown')}")
                return None
    except Exception as e:
        logger.error(f"Telegram API 调用失败 ({method}): {e}")
        return None
