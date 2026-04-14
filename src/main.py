"""PM-004.1: Paper Miner 主入口 — 串联所有模块

主流程：拉取 → 去重 → 打分 → 筛选 → 格式化 → 推送 → 记录已读
运行方式：由 Hermes cronjob 每日 8:00 自动触发，stdout 自动 deliver 到 Telegram
"""

import json
import logging
import os
import sys
from datetime import datetime

# 确保能 import 同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_daily_papers, get_error_message
from dedup import load_seen_papers, filter_seen, mark_as_seen
from preferences import load_preferences, build_scoring_prompt, should_remind_preferences, get_reminder_text
from scorer import score_paper
from formatter import format_daily_digest, format_no_high_digest
from pusher import deliver_output, format_alert_message
from notion_sync import update_notion_task_status

# 配置日志
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"{datetime.now():%Y-%m-%d}.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger("paper_miner")


def load_config():
    """加载配置文件。"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_api_key(env_name):
    """从环境变量获取 API Key。"""
    key = os.environ.get(env_name, "")
    if not key:
        # 尝试从 .env 文件读取
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{env_name}="):
                        key = line.split("=", 1)[1]
                        break
    return key


def run():
    """主执行流程。"""
    try:
        config = load_config()
        logger.info("=== Paper Miner 开始运行 ===")

        # ── Step 1: 拉取数据 ──
        logger.info("Step 1: 拉取 HuggingFace Daily Papers...")
        papers, error = fetch_daily_papers(config["hf_api_url"])
        if error:
            alert = format_alert_message(get_error_message(error))
            deliver_output(alert)
            logger.error(f"拉取失败: {error}")
            return

        if not papers:
            deliver_output(format_no_high_digest(0))
            logger.info("无论文数据")
            return

        # ── Step 2: 去重 ──
        logger.info(f"Step 2: 去重过滤（共 {len(papers)} 篇）...")
        seen_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", config["dedup"]["seen_papers_path"])
        seen_ids = load_seen_papers(seen_path)
        new_papers = filter_seen(papers, seen_ids)
        
        if not new_papers:
            deliver_output(format_no_high_digest(0))
            logger.info("全部论文已推送过，无新论文")
            return

        logger.info(f"去重后剩余 {len(new_papers)} 篇新论文")

        # ── Step 3: 加载偏好 ──
        prefs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", config["preferences"]["path"])
        preferences = load_preferences(prefs_path)
        remind = should_remind_preferences(preferences, config["preferences"]["refresh_interval_days"])
        remind_text = get_reminder_text(preferences) if remind else None

        # ── Step 4: LLM 打分 ──
        logger.info(f"Step 4: 开始打分（{len(new_papers)} 篇）...")
        api_key = get_api_key(config["llm"]["api_key_env"])
        if not api_key:
            alert = format_alert_message("DeepSeek API Key 未配置")
            deliver_output(alert)
            logger.error("API Key 未找到")
            return

        threshold = config["scoring"]["push_threshold"]
        all_results = []  # 记录所有打分结果（不论是否达标）

        for i, paper in enumerate(new_papers):
            logger.info(f"  打分中 [{i+1}/{len(new_papers)}]: {paper['title'][:50]}...")
            prompt = build_scoring_prompt(paper, preferences)
            result = score_paper(
                paper, prompt, api_key,
                config["llm"]["api_url"],
                config["llm"]["model"],
            )
            if result:
                result["paper"] = paper
                total = result.get("score", 0)
                logger.info(f"    → {total} 分 | {result.get('one_liner', '')[:40]}")
                all_results.append(result)

        # ── Step 5: 筛选与格式化 ──
        scored_results = [r for r in all_results if r.get("score", 0) >= threshold]

        if not scored_results:
            max_score = max((r.get("score", 0) for r in all_results), default=0)
            deliver_output(format_no_high_digest(max_score))
            logger.info(f"无高分论文，最高分 {max_score}")
            # 即使没有高分，也记录所有已处理的论文（避免重复打分）
            all_paper_ids = [p["id"] for p in new_papers]
            mark_as_seen(seen_path, seen_ids, all_paper_ids)
            return

        # 按分数降序排列
        scored_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(f"Step 5: 格式化日报（{len(scored_results)} 篇高分）...")
        digest = format_daily_digest(scored_results, remind_text)

        # ── Step 6: 推送 ──
        deliver_output(digest)

        # ── Step 7: 记录已推送 ──
        pushed_ids = [r["paper"]["id"] for r in scored_results]
        mark_as_seen(seen_path, seen_ids, pushed_ids)

        logger.info(f"=== Paper Miner 完成：推送 {len(scored_results)} 篇 ===")

    except Exception as e:
        logger.exception("Paper Miner 运行异常")
        deliver_output(format_alert_message(f"{type(e).__name__}: {str(e)[:50]}"))


if __name__ == "__main__":
    run()
