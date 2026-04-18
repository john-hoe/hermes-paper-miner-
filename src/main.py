"""PM-004.1: Paper Miner 主入口 — 串联所有模块

改版：逐篇推送 + inline keyboard 反馈
主流程：拉取 → 去重 → 打分 → 筛选 → 逐篇推送 → 记录已读
运行方式：由 Hermes cronjob 每日 8:00 自动触发
"""

import json
import logging
import os
import sys
from datetime import datetime

# 确保能 import 同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_daily_papers, fetch_modelscope_papers, dedup_cross_source, get_error_message
from dedup import load_seen_papers, filter_seen, mark_as_seen
from preferences import load_preferences, build_scoring_prompt, should_remind_preferences, get_reminder_text
from scorer import score_paper
from formatter import format_single_paper, format_no_high_digest, format_error_alert
from pusher import deliver_output, format_alert_message, send_paper_message, send_summary_message, send_no_papers_message
from feedback import record_feedback
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

        # ── Step 1: 双源拉取数据 ──
        logger.info("Step 1: 拉取论文数据...")
        
        # 源1: HuggingFace Daily Papers
        hf_papers, hf_error = fetch_daily_papers(config["hf_api_url"])
        if hf_error:
            logger.warning(f"HF 拉取失败: {hf_error}")
        
        # 源2: ModelScope 最新论文
        ms_papers, ms_error = fetch_modelscope_papers(config)
        if ms_error:
            logger.warning(f"ModelScope 拉取失败: {ms_error}")
        
        # 合并双源
        all_papers = []
        if hf_papers:
            all_papers.extend(hf_papers)
        if ms_papers:
            all_papers.extend(ms_papers)
        
        logger.info(f"双源合并: HF {len(hf_papers)} 篇 + ModelScope {len(ms_papers)} 篇 = {len(all_papers)} 篇")
        
        # 跨源去重（同 arxiv_id 保留 HF 版本）
        all_papers = dedup_cross_source(all_papers)
        
        if not all_papers:
            deliver_output(format_no_high_digest(0)["text"])
            logger.info("无论文数据")
            return

        # 过滤陈旧论文（只保留180天内的）
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=180)
        fresh_papers = []
        for p in all_papers:
            pub = p.get("published", "")
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    if pub_dt >= cutoff:
                        fresh_papers.append(p)
                except ValueError:
                    fresh_papers.append(p)  # 解析失败则保留
            else:
                fresh_papers.append(p)
        if fresh_papers:
            logger.info(f"新鲜度过滤：{len(all_papers)} → {len(fresh_papers)} 篇（180天内）")
            papers = fresh_papers
        else:
            deliver_output(format_no_high_digest(0)["text"])
            logger.info("180天内无新论文")
            return

        # 限制每次最多打分篇数（避免超时）
        max_papers = config.get("max_papers_per_run", 15)
        if len(papers) > max_papers:
            logger.info(f"截取 top {max_papers} 篇（共 {len(papers)} 篇）")
            papers = papers[:max_papers]

        # ── Step 2: 去重 ──
        logger.info(f"Step 2: 去重过滤（共 {len(papers)} 篇）...")
        seen_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", config["dedup"]["seen_papers_path"])
        seen_ids = load_seen_papers(seen_path)
        new_papers = filter_seen(papers, seen_ids)
        
        if not new_papers:
            deliver_output(format_no_high_digest(0)["text"])
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

        # ── Step 5: 筛选 ──
        scored_results = [r for r in all_results if r.get("score", 0) >= threshold]

        if not scored_results:
            max_score = max((r.get("score", 0) for r in all_results), default=0)
            send_no_papers_message(config)
            logger.info(f"无高分论文，最高分 {max_score}")
            # 即使没有高分，也记录所有已处理的论文（避免重复打分）
            # 持久化打分结果（供反馈分析用）
            scoring_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "scoring_results.jsonl")
            os.makedirs(os.path.dirname(scoring_log_path), exist_ok=True)
            with open(scoring_log_path, "a", encoding="utf-8") as sf:
                for r in all_results:
                    record = {
                        "paper_id": r.get("paper", {}).get("id", ""),
                        "score": r.get("score", 0),
                        "title": r.get("paper", {}).get("title", ""),
                        "institution": r.get("institution", ""),
                        "preference_hit": r.get("preference_hit"),
                        "one_liner": r.get("one_liner", ""),
                        "why_read": r.get("why_read", ""),
                        "deep_take": r.get("deep_take", ""),
                        "scenarios": r.get("scenarios", []),
                        "timestamp": datetime.now().isoformat(),
                    }
                    sf.write(json.dumps(record, ensure_ascii=False) + "\n")
            all_paper_ids = [p["id"] for p in new_papers]
            mark_as_seen(seen_path, seen_ids, all_paper_ids)
            return

        # 按分数降序排列
        scored_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # ── Step 6: 逐篇推送 ──
        logger.info(f"Step 6: 逐篇推送（{len(scored_results)} 篇高分）...")
        
        pushed_count = 0
        for i, result in enumerate(scored_results):
            msg_id = send_paper_message(result, config)
            if msg_id:
                pushed_count += 1
                logger.info(f"  ✅ [{i+1}/{len(scored_results)}] 已推送: {result['paper']['title'][:40]}... (msg_id={msg_id})")
                # 预记录到 feedback（方便后续 callback 关联打分结果）
                record_feedback(result["paper"]["id"], "sent", result)
            else:
                # Telegram 推送失败，回退到 stdout
                fallback = format_single_paper(result)
                deliver_output(fallback["text"])
                pushed_count += 1
                logger.warning(f"  ⚠️ [{i+1}] Telegram 推送失败，回退 stdout")

        # ── Step 7: 发送总结 ──
        send_summary_message(scored_results, config, remind_text)

        # ── Step 8: 持久化打分结果（供反馈分析用）──
        scoring_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "scoring_results.jsonl")
        os.makedirs(os.path.dirname(scoring_log_path), exist_ok=True)
        with open(scoring_log_path, "a", encoding="utf-8") as sf:
            for r in all_results:
                record = {
                    "paper_id": r.get("paper", {}).get("id", ""),
                    "score": r.get("score", 0),
                    "title": r.get("paper", {}).get("title", ""),
                    "institution": r.get("institution", ""),
                    "preference_hit": r.get("preference_hit"),
                    "one_liner": r.get("one_liner", ""),
                    "why_read": r.get("why_read", ""),
                    "deep_take": r.get("deep_take", ""),
                    "scenarios": r.get("scenarios", []),
                    "timestamp": datetime.now().isoformat(),
                }
                sf.write(json.dumps(record, ensure_ascii=False) + "\n")

        # ── Step 9: 记录已推送 ──
        pushed_ids = [r["paper"]["id"] for r in scored_results]
        mark_as_seen(seen_path, seen_ids, pushed_ids)

        logger.info(f"=== Paper Miner 完成：推送 {pushed_count}/{len(scored_results)} 篇 ===")

        # ── Step 10: Reddit Watcher（可选，feature flag 控制）──
        if config.get("reddit_watcher", {}).get("enabled", False):
            try:
                from reddit_watcher import run_watcher
                run_watcher()
            except Exception as e:
                logger.warning(f"Reddit watcher 运行异常（不影响主流程）: {e}")

    except Exception as e:
        logger.exception("Paper Miner 运行异常")
        deliver_output(format_alert_message(f"{type(e).__name__}: {str(e)[:50]}"))


if __name__ == "__main__":
    run()
