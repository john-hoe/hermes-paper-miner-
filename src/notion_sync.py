"""PM-004.3: Notion 看板状态自动同步"""

import json
import logging
import urllib.request

logger = logging.getLogger("paper_miner")


def update_notion_task_status(api_key, database_id, task_id, new_status):
    """更新 Notion 看板中指定任务的状态。

    Args:
        api_key: Notion Integration Token
        database_id: 看板数据库 ID
        task_id: 任务编号（如 PM-001.2）
        new_status: 新状态（如 🔧 进行中、✅ 已完成）
    """
    # 1. 查询任务
    query_url = f"https://api.notion.com/v1/databases/{database_id}/query"
    query_data = {
        "filter": {
            "property": "任务ID",
            "rich_text": {"equals": task_id}
        }
    }
    req = urllib.request.Request(query_url, data=json.dumps(query_data).encode(), headers={
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read().decode()).get("results", [])
    except Exception as e:
        logger.error(f"Notion 查询失败 ({task_id}): {e}")
        return False

    if not results:
        logger.warning(f"Notion 中未找到任务 {task_id}")
        return False

    # 2. 更新状态
    page_id = results[0]["id"]
    update_url = f"https://api.notion.com/v1/pages/{page_id}"
    update_data = {
        "properties": {
            "状态": {"select": {"name": new_status}}
        }
    }
    req = urllib.request.Request(update_url, data=json.dumps(update_data).encode(), headers={
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }, method="PATCH")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.info(f"Notion 更新成功: {task_id} → {new_status}")
            return True
    except Exception as e:
        logger.error(f"Notion 更新失败 ({task_id}): {e}")
        return False
