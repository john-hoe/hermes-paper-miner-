# Paper Miner - AI 论文淘金器

每日自动抓取 Hugging Face Daily Papers，用 DeepSeek 大模型进行多维度打分与落地场景分析，推送到 Telegram。

## 项目结构

```
hermes-paper-miner-/
├── src/
│   ├── config.json              # 全局配置
│   ├── main.py                  # 主入口
│   ├── fetcher.py               # HF 数据拉取
│   ├── dedup.py                 # 去重模块
│   ├── scorer.py                # LLM 打分 + Prompt
│   ├── formatter.py             # 日报格式化
│   ├── pusher.py                # Telegram 推送
│   ├── notion_sync.py           # Notion 看板同步
│   └── preferences.py           # 偏好管理与保鲜
├── data/
│   ├── user_preferences.json    # 用户偏好配置
│   └── seen_papers.json         # 已推送论文ID库
├── logs/                        # 运行日志
├── PLAN.md                      # 执行方案
└── README.md
```

## 配置说明

所有 API Key 通过环境变量注入，不硬编码在代码中：
- `DEEPSEEK_API_KEY`: DeepSeek 大模型
- `NOTION_API_KEY`: Notion 看板同步

## 运行

```bash
python src/main.py
```
