# Paper Miner - 执行方案 (V1)

## 1. 核心验收标准 (TDD Test Cases)

### 成功用例 (Happy Path)
每日早 8:00，成功抓取 HF Daily Papers，去重后筛选出 ≥85 分论文，合并为单条"今日 AI 淘金日报"推送：

```
⛏️ 今日 AI 淘金日报 | 2026-04-15

━━━━━━━━━━━━━━━━━━

📄 [92分] [Meta AI] Voicebox-V2：零样本极速声音克隆
🔗 [论文链接] | [代码库: ✅已开源]
🎯 命中偏好：[多模态出片 / Agent 协作]

💡 这是啥：提出了一种新的 flow matching 算法，极大地缩短了 zero-shot 语音克隆的时间和底噪。

🛠 落地场景预测（你可以怎么用）：
 1. 出海短视频配音：批量生成外语配音。
 2. AI NPC 游戏客服：零延迟拟真客服。

⚠️ 落地劝退点：单卡 24GB 显存起步，边缘设备不可用。

━━━━━━━━━━━━━━━━━━

📄 [88分] [Stanford] Matryoshka Attention...
（第二条论文）

━━━━━━━━━━━━━━━━━━
共 2 篇高分好文 | 数据源：Hugging Face Daily Papers
```

### 边缘用例
- **无高分**: 推送 `🚫 今日无高分好文，最高分为 XX 分，已跳过推送`
- **系统异常**: 捕获异常，仅推送 `⚠️ 系统故障：[错误简述]，今日淘金任务失败`
- **偏好保鲜**: 每 14 天在日报底部追加提醒更新偏好

## 2. 架构设计与数据流

```
[HuggingFace API] → [去重过滤(seen_papers.json)] → [LLM 打分(Gemini/GLM-5.1)] → [筛选(≥85分)] → [合并格式化] → [Telegram 推送]
```

### 核心模块
1. **Fetch + Dedup**: 抓取 HF Daily Papers，对比 seen_papers.json 去重
2. **Dynamic Preferences**: 读取外置 user_preferences.json，命中偏好加分并标记 🎯
3. **LLM Scoring**: 调用云端 API（Gemini 或 GLM-5.1），强制输出 JSON（打分+场景+劝退点）
4. **Format + Push**: 合并为单条日报，通过 Telegram 推送

## 3. 打分权重
- 满分 100 分 + 附加分
- **工程落地性 (40%)**: 是否有代码？复现门槛？
- **痛点解决度 (30%)**: 解决真实痛点 vs 跑分刷榜
- **创新性 (20%)**: 思路新颖度
- **出圈潜力 (10%)**: 商业产品化可行性
- **附加分 (+5~10分)**: 大厂 (Meta, Google, OpenAI 等) 或顶尖高校

## 4. 翻译纪律 (极严)
专有名词必须保留英文原词（RAG, MoE, Agent, Transformer, LoRA, fine-tuning 等），
严禁翻译成"检索增强生成"、"专家混合"等生硬中文。

## 5. 算力来源
默认调用外部云端 API：Gemini + GLM-5.1（如有新增，John 会主动告知更新）。
不使用本地 Mac mini 算力。

## 6. 任务拆解 (TODO)
- [ ] Task 1: 编写数据拉取 + seen_papers.json 去重逻辑 + 异常捕获框架
- [ ] Task 2: 建立 user_preferences.json + 设计 LLM Prompt（融合偏好权重）+ JSON 解析
- [ ] Task 3: 编写日报合并格式化 + Telegram 推送 + 偏好保鲜提醒机制
- [ ] Task 4: 挂载 Cronjob 定时任务(每日早8点) + Notion 状态同步
