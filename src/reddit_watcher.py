"""P1: Reddit Observer — 监控 r/LocalLLaMA 热门论文讨论

设计原则（Karpathy + Taleb）：
1. 完全独立，不碰任何现有代码
2. 只写数据，不改推送逻辑
3. feature flag 默认关闭
4. 14天 TTL 自动停止，代码写死
5. 数据隔离：data/reddit_mentions.jsonl

用法：
  python3 src/reddit_watcher.py          # 手动运行一次
  由 cronjob 自动调用（config: reddit_watcher.enabled）

数据源：Reddit JSON API（无需 PRAW，无需认证）
  https://www.reddit.com/r/LocalLLaMA/hot.json
"""

import json
import logging
import os
import re
import urllib.request
from datetime import datetime, timedelta

logger = logging.getLogger("paper_miner")

# ── 硬编码配置（Taleb 的 antifragile 设计：不读 config.json）──
SUBREDDITS = ["LocalLLaMA"]
POSTS_PER_SUB = 25
TTL_DAYS = 14
TTL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "reddit_watcher_start.json")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "reddit_mentions.jsonl")
USER_AGENT = "PaperMiner/1.0 (research bot)"


def _check_ttl():
    """检查是否超过14天 TTL。超过则自动退出。"""
    os.makedirs(os.path.dirname(TTL_FILE), exist_ok=True)
    
    if os.path.exists(TTL_FILE):
        with open(TTL_FILE, "r") as f:
            data = json.load(f)
        start = datetime.fromisoformat(data["started_at"])
        if datetime.now() - start > timedelta(days=TTL_DAYS):
            logger.info(f"Reddit watcher 已运行超过 {TTL_DAYS} 天，自动停止")
            return False
    else:
        # 首次运行，记录启动时间
        with open(TTL_FILE, "w") as f:
            json.dump({"started_at": datetime.now().isoformat()}, f)
        logger.info(f"Reddit watcher 首次启动，{TTL_DAYS} 天后自动停止")
    
    return True


def _extract_arxiv_ids(text):
    """从文本中提取 arxiv ID。"""
    if not text:
        return []
    # 匹配 2404.12345 或 2404.12345v2 格式
    pattern = r'(?:arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?)'
    return list(set(re.findall(pattern, text)))


def fetch_subreddit_hot(subreddit):
    """获取 subreddit 热门帖子。使用 Reddit JSON API（无需认证）。"""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={POSTS_PER_SUB}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        
        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            posts.append({
                "id": post.get("id", ""),
                "title": post.get("title", ""),
                "selftext": post.get("selftext", "")[:2000],  # 截断避免过大
                "url": post.get("url", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "created_utc": post.get("created_utc", 0),
            })
        return posts
    except Exception as e:
        logger.error(f"Reddit fetch 失败 (r/{subreddit}): {e}")
        return []


def extract_paper_mentions(posts):
    """从帖子中提取论文提及。"""
    mentions = []
    
    for post in posts:
        # 从标题和正文提取 arxiv ID
        title_ids = _extract_arxiv_ids(post["title"])
        text_ids = _extract_arxiv_ids(post["selftext"])
        url_ids = _extract_arxiv_ids(post["url"])
        
        all_ids = list(set(title_ids + text_ids + url_ids))
        
        for arxiv_id in all_ids:
            mentions.append({
                "arxiv_id": arxiv_id,
                "source": "reddit",
                "subreddit": post.get("subreddit", ""),
                "reddit_score": post["score"],
                "reddit_comments": post["num_comments"],
                "reddit_title": post["title"][:200],
                "reddit_url": f"https://reddit.com/comments/{post['id']}",
                "found_at": datetime.now().isoformat(),
            })
    
    return mentions


def run_watcher():
    """主执行流程。"""
    if not _check_ttl():
        return
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    all_mentions = []
    for sub in SUBREDDITS:
        logger.info(f"Reddit watcher: 抓取 r/{sub}...")
        posts = fetch_subreddit_hot(sub)
        mentions = extract_paper_mentions(posts)
        all_mentions.extend(mentions)
        logger.info(f"  r/{sub}: {len(posts)} 帖子 → {len(mentions)} 论文提及")
    
    # 去重：同一 arxiv_id 只保留最高 score 的
    best = {}
    for m in all_mentions:
        aid = m["arxiv_id"]
        if aid not in best or m["reddit_score"] > best[aid]["reddit_score"]:
            best[aid] = m
    
    # 追加写入（不覆盖历史数据）
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for m in best.values():
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    
    logger.info(f"Reddit watcher 完成：{len(best)} 篇独立论文提及已记录")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    run_watcher()
