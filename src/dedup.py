"""PM-001.3: seen_papers.json 去重模块"""

import json
import os
import logging

logger = logging.getLogger("paper_miner")


def load_seen_papers(filepath):
    """读取已推送论文 ID 列表。"""
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set()
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"读取 seen_papers 失败，将使用空集: {e}")
        return set()


def save_seen_papers(filepath, seen_ids):
    """持久化已推送论文 ID 列表。"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen_ids)), f, indent=2, ensure_ascii=False)
    logger.info(f"已保存 {len(seen_ids)} 条去重记录")


def filter_seen(papers, seen_ids):
    """过滤掉已推送过的论文。返回新论文列表。"""
    new_papers = [p for p in papers if p["id"] not in seen_ids]
    skipped = len(papers) - len(new_papers)
    if skipped > 0:
        logger.info(f"去重过滤: 跳过 {skipped} 篇已推送论文")
    return new_papers


def mark_as_seen(filepath, seen_ids, paper_ids):
    """将新推送的论文 ID 追加到去重库。"""
    seen_ids.update(paper_ids)
    save_seen_papers(filepath, seen_ids)
    return seen_ids
