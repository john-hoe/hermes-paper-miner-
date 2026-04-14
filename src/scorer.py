"""PM-002.3 + PM-002.4 + PM-002.5: LLM 打分、JSON 解析容错、机构识别"""

import json
import logging
import os
import re
import urllib.request

logger = logging.getLogger("paper_miner")

# 大厂/顶尖高校名单
TOP_INSTITUTIONS = [
    "Meta", "Facebook", "FAIR",
    "Google", "DeepMind", "Google Brain", "Google Research",
    "OpenAI", "Anthropic",
    "Microsoft", "Microsoft Research",
    "Apple",
    "Nvidia", "NVIDIA",
    "Amazon",
    "Stanford",
    "MIT", "Massachusetts Institute",
    "UC Berkeley",
    "CMU", "Carnegie Mellon",
    "Princeton",
    "Caltech",
    "清华", "Tsinghua",
    "北大", "Peking",
    "上海交大", "Shanghai Jiao Tong",
    "浙大", "Zhejiang",
]


def call_deepseek(prompt, api_key, api_url, model="deepseek-chat",
                  max_tokens=2048, temperature=0.3, timeout=60):
    """调用 DeepSeek API。"""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(api_url, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    return result["choices"][0]["message"]["content"]


def parse_llm_json(raw_text):
    """从 LLM 输出中稳健提取 JSON（处理 markdown 包裹、多余文本等）。"""
    # 策略1: 直接解析
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # 策略2: 提取 ```json ... ``` 块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 策略3: 提取第一个 { ... } 块
    m = re.search(r"\{[\s\S]*\}", raw_text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"JSON 解析全部失败，原始输出: {raw_text[:200]}")
    return None


def score_paper(paper, prompt, api_key, api_url, model="deepseek-chat",
                max_retries=2):
    """对单篇论文进行打分。包含重试机制。"""
    for attempt in range(max_retries + 1):
        try:
            raw = call_deepseek(prompt, api_key, api_url, model)
            result = parse_llm_json(raw)
            if result and "score" in result:
                return result
            logger.warning(f"第 {attempt+1} 次尝试：LLM 输出缺少 score 字段")
        except Exception as e:
            logger.warning(f"第 {attempt+1} 次尝试失败: {type(e).__name__}: {e}")
    
    return None


def detect_institution(authors_str):
    """从作者信息中识别机构（简单关键词匹配）。
    注意：主要依赖 LLM 在评分时输出 institution 字段，这里是辅助验证。
    """
    matched = []
    for inst in TOP_INSTITUTIONS:
        if inst.lower() in authors_str.lower():
            matched.append(inst)
    return matched if matched else None
