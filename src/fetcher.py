"""PM-001.2: HuggingFace Daily Papers 数据拉取模块"""

import json
import logging
import urllib.request
from datetime import datetime

logger = logging.getLogger("paper_miner")


def fetch_daily_papers(api_url, timeout=30):
    """从 HuggingFace 拉取今日 Daily Papers。
    
    Returns:
        list[dict]: 论文列表，每篇包含 id, title, summary, url, authors, published_upvotes
        str: 错误信息（如果失败）
    """
    try:
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "PaperMiner/1.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode())
        
        if not raw or not isinstance(raw, list):
            return [], "empty_data"
        
        papers = []
        for item in raw:
            paper = {
                "id": item.get("paper", {}).get("id", ""),
                "title": item.get("paper", {}).get("title", "未知标题"),
                "summary": item.get("paper", {}).get("summary", ""),
                "url": f"https://huggingface.co/papers/{item.get('paper', {}).get('id', '')}",
                "authors": [a.get("name", "") for a in item.get("paper", {}).get("authors", [])],
                "published": item.get("paper", {}).get("published", ""),
                "upvotes": item.get("paper", {}).get("upvotes", 0),
            }
            if paper["id"]:
                papers.append(paper)
        
        logger.info(f"成功拉取 {len(papers)} 篇论文")
        return papers, None

    except urllib.error.HTTPError as e:
        if e.code == 429:
            logger.error("HF API 限流 (HTTP 429)")
            return [], "rate_limited"
        logger.error(f"HTTP 错误: {e.code}")
        return [], f"http_error_{e.code}"
    except urllib.error.URLError as e:
        logger.error(f"网络超时: {e.reason}")
        return [], "timeout"
    except json.JSONDecodeError:
        logger.error("HF API 返回非 JSON 数据")
        return [], "json_error"
    except Exception as e:
        logger.error(f"未知异常: {type(e).__name__}: {e}")
        return [], f"unknown: {type(e).__name__}"


def get_error_message(error_code):
    """将内部错误码转换为用户友好的提示。"""
    messages = {
        "empty_data": "今日数据源为空",
        "rate_limited": "数据源请求过于频繁",
        "timeout": "网络连接超时",
        "json_error": "数据源返回格式异常",
    }
    return messages.get(error_code, "数据源异常")
