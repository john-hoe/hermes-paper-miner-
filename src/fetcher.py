"""PM-001.2: HuggingFace Daily Papers + ModelScope 双源数据拉取模块"""

import json
import logging
import urllib.request

logger = logging.getLogger("paper_miner")


def fetch_daily_papers(api_url, timeout=30):
    """从 HuggingFace 拉取今日 Daily Papers。
    
    Returns:
        list[dict]: 论文列表
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
            p = item.get("paper", {})
            paper = {
                "id": p.get("id", ""),
                "title": p.get("title", "未知标题"),
                "summary": p.get("summary", ""),
                "url": f"https://huggingface.co/papers/{p.get('id', '')}",
                "authors": [a.get("name", "") for a in p.get("authors", [])],
                "published": p.get("publishedAt", ""),
                "upvotes": item.get("upvotes", p.get("upvotes", 0)),
                "github_repo": p.get("githubRepo", ""),
                "ai_summary": p.get("ai_summary", ""),
                "ai_keywords": p.get("ai_keywords", []),
                "source": "huggingface",
                "arxiv_id": p.get("id", ""),
            }
            if paper["id"]:
                papers.append(paper)
        
        # 按热度降序排列
        papers.sort(key=lambda x: x["upvotes"], reverse=True)
        logger.info(f"[HF] 成功拉取 {len(papers)} 篇论文")
        return papers, None

    except urllib.error.HTTPError as e:
        if e.code == 429:
            logger.error("[HF] API 限流 (HTTP 429)")
            return [], "rate_limited"
        logger.error(f"[HF] HTTP 错误: {e.code}")
        return [], f"http_error_{e.code}"
    except urllib.error.URLError as e:
        logger.error(f"[HF] 网络超时: {e.reason}")
        return [], "timeout"
    except json.JSONDecodeError:
        logger.error("[HF] API 返回非 JSON 数据")
        return [], "json_error"
    except Exception as e:
        logger.error(f"[HF] 未知异常: {type(e).__name__}: {e}")
        return [], f"unknown: {type(e).__name__}"


def fetch_modelscope_papers(config, timeout=30):
    """从 ModelScope 拉取最新论文。
    
    API: https://modelscope.cn/api/v1/papers?PageNumber=1&PageSize=N
    
    Returns:
        list[dict]: 论文列表（统一格式）
        str: 错误信息（如果失败）
    """
    ms_config = config.get("modelscope", {})
    if not ms_config.get("enabled", False):
        logger.info("[ModelScope] 未启用，跳过")
        return [], None
    
    api_url = ms_config.get("api_url", "https://modelscope.cn/api/v1/papers")
    page_size = ms_config.get("page_size", 20)
    min_innovation = ms_config.get("min_innovation_score", 450)
    
    try:
        url = f"{api_url}?PageNumber=1&PageSize={page_size}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "PaperMiner/1.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode())
        
        if raw.get("Code") != 200:
            logger.error(f"[ModelScope] API 返回错误: {raw.get('Message', '')}")
            return [], "api_error"
        
        papers_data = raw.get("Data", {}).get("Papers", [])
        if not papers_data:
            return [], "empty_data"
        
        papers = []
        for p in papers_data:
            arxiv_id = p.get("ArxivId", "")
            innovation_score = p.get("InnovationScore", 0)
            impact_score = p.get("ImpactScore", 0)
            
            # 预筛：创新分低于阈值直接跳过，减少 LLM 打分成本
            if innovation_score < min_innovation:
                logger.debug(f"[ModelScope] 跳过低分论文: {p.get('Title', '')[:40]} (Innovation={innovation_score})")
                continue
            
            # 提取 AI 评分评语
            extra = p.get("Extra", {})
            rank_dict = extra.get("comment_and_rank_dict", {})
            final_score = rank_dict.get("final_score", {}).get("score", 0)
            final_comment = rank_dict.get("final_score", {}).get("comment", "")
            innovation_comment = rank_dict.get("innovation", {}).get("comment", "")
            
            # AI 摘要（中文优先）
            summary = p.get("AbstractCn", "") or p.get("AbstractEn", "") or ""
            # ModelScope 自带的章节级 summary 更详细
            ai_summary = extra.get("summary", "")
            
            paper = {
                "id": f"ms_{p.get('Id', '')}",  # 用 ms_ 前缀避免与 HF ID 冲突
                "title": p.get("Title", "未知标题"),
                "summary": summary[:2000],  # 截断过长的摘要
                "url": p.get("ArxivUrl", "") or f"https://modelscope.cn/papers/{p.get('Id', '')}",
                "authors": p.get("Authors", "").split(", ") if p.get("Authors") else [],
                "published": p.get("PublishDate", ""),
                "upvotes": int(impact_score),  # 用 ImpactScore 近似热度
                "github_repo": p.get("CodeLink", ""),
                "ai_summary": ai_summary[:1500] if ai_summary else "",
                "ai_keywords": p.get("Type", [])[:10] if isinstance(p.get("Type"), list) else [],
                "source": "modelscope",
                "arxiv_id": arxiv_id,
                # ModelScope 独有字段
                "ms_id": p.get("Id"),
                "ms_innovation_score": innovation_score,
                "ms_impact_score": impact_score,
                "ms_tech_depth_score": p.get("TechnicalDepthScore", 0),
                "ms_final_score": final_score,
                "ms_final_comment": final_comment,
                "ms_innovation_comment": innovation_comment,
            }
            papers.append(paper)
        
        # 按 ModelScope 评分降序
        papers.sort(key=lambda x: x.get("ms_innovation_score", 0), reverse=True)
        logger.info(f"[ModelScope] 拉取 {len(papers_data)} 篇，预筛后 {len(papers)} 篇 (Innovation>={min_innovation})")
        return papers, None

    except urllib.error.HTTPError as e:
        logger.error(f"[ModelScope] HTTP 错误: {e.code}")
        return [], f"ms_http_error_{e.code}"
    except urllib.error.URLError as e:
        logger.error(f"[ModelScope] 网络超时: {e.reason}")
        return [], "ms_timeout"
    except json.JSONDecodeError:
        logger.error("[ModelScope] API 返回非 JSON 数据")
        return [], "ms_json_error"
    except Exception as e:
        logger.error(f"[ModelScope] 未知异常: {type(e).__name__}: {e}")
        return [], f"ms_unknown: {type(e).__name__}"


def dedup_cross_source(papers):
    """跨源去重：如果同一 arxiv_id 出现在 HF 和 ModelScope，保留 HF 版本（数据更完整）。
    
    Args:
        papers: 合并后的论文列表
    
    Returns:
        list[dict]: 去重后的论文列表
    """
    seen_arxiv = {}
    deduped = []
    
    for p in papers:
        arxiv_id = p.get("arxiv_id", "")
        source = p.get("source", "")
        
        if not arxiv_id:
            # 无 arxiv_id 的论文直接保留（通常是 ModelScope 独有的）
            deduped.append(p)
            continue
        
        if arxiv_id in seen_arxiv:
            # 已存在，保留 HF 版本，丢弃 MS 版本
            existing_source = seen_arxiv[arxiv_id].get("source", "")
            if source == "modelscope" and existing_source == "huggingface":
                logger.debug(f"跨源去重: 跳过 ModelScope 重复论文 {arxiv_id}")
                continue
            elif source == "huggingface" and existing_source == "modelscope":
                # HF 覆盖 MS
                deduped = [x for x in deduped if x.get("arxiv_id") != arxiv_id]
                deduped.append(p)
                seen_arxiv[arxiv_id] = p
                continue
            # 同源重复也跳过
            continue
        
        seen_arxiv[arxiv_id] = p
        deduped.append(p)
    
    skipped = len(papers) - len(deduped)
    if skipped > 0:
        logger.info(f"跨源去重: 跳过 {skipped} 篇重复论文")
    
    return deduped


def get_error_message(error_code):
    """将内部错误码转换为用户友好的提示。"""
    messages = {
        "empty_data": "今日数据源为空",
        "rate_limited": "数据源请求过于频繁",
        "timeout": "网络连接超时",
        "json_error": "数据源返回格式异常",
        "ms_http_error": "ModelScope 数据源 HTTP 错误",
        "ms_timeout": "ModelScope 数据源连接超时",
        "ms_json_error": "ModelScope 数据源格式异常",
        "api_error": "API 返回错误",
    }
    return messages.get(error_code, "数据源异常")
