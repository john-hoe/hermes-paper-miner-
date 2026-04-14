"""PM-003.3 + PM-003.4: Telegram 推送模块（通过 cronjob auto-deliver）

注意：Paper Miner 作为 cronjob 运行时，最终输出会由 Hermes 的 cronjob 机制
自动 deliver 到 Telegram。所以这个模块的核心逻辑是：
1. 正常日报：print 输出，由 cronjob auto-deliver
2. 异常警报：同样 print 输出

但我们也保留直接调用 Telegram Bot API 的能力，以备手动调试使用。
"""

import json
import logging
import urllib.request

logger = logging.getLogger("paper_miner")


def format_alert_message(error_brief):
    """生成单行系统故障警报。"""
    return f"⚠️ 系统故障：{error_brief}，今日淘金任务失败。"


def deliver_output(text):
    """输出最终内容（cronjob 会自动捕获并 deliver 到 Telegram）。"""
    # Hermes cronjob 会自动把 stdout 作为消息内容 deliver
    print(text)


def send_telegram_direct(text, bot_token, chat_id):
    """直接调用 Telegram Bot API 发送消息（手动调试用）。
    
    处理超长消息自动分段（Telegram 单条上限 4096 字符）。
    """
    max_len = 4000
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # 在分隔线处断开
        cut = text.rfind("━" * 10, 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip()

    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                pass
        except Exception as e:
            logger.error(f"Telegram 推送失败: {e}")
