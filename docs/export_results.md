# 管理员导出脚本

## 1. 作用

该脚本用于把网页实验台保存到 `storage/logs/` 下的原始结果导出为便于分析的汇总文件。

它会生成：

- `all_session_ratings.csv`
- `all_episode_ratings.csv`
- `all_session_logs.csv`
- `all_session_logs.jsonl`

默认输出目录：

- `experiments/longterm_companion_web/storage/exports/`

## 2. 使用方式

在实验目录下执行：

```bash
cd /home/ubuntu/longterm_companion_web
source .venv/bin/activate
python scripts/export_results.py
```

如果你本地运行，则进入本地实验目录后执行同样命令即可。

## 3. 自定义目录

如果日志目录或输出目录不同，可以这样：

```bash
python scripts/export_results.py \
  --log-dir /home/ubuntu/longterm_companion_web/storage/logs \
  --output-dir /home/ubuntu/longterm_companion_web/storage/exports
```

## 4. 输出内容说明

### 4.1 `all_session_ratings.csv`

汇总所有 session 级评分，包括：

- tester_id
- episode_id
- session_id
- model_blind_id
- 各项 likert 评分
- best moment / worst moment / one-sentence impression

### 4.2 `all_episode_ratings.csv`

汇总所有 episode 级评分，包括：

- tester_id
- episode_id
- model_blind_id
- continuity / trust / stability / repair 等评分
- paired preference

### 4.3 `all_session_logs.csv`

汇总每次 session 的核心信息，包括：

- tester_id
- episode_id
- session_id
- model_blind_id
- 起止时间
- 历史摘要文本
- 对话轮数
- 对话全文文本

### 4.4 `all_session_logs.jsonl`

保留完整结构化 session log，适合后续写程序继续分析。

## 5. 推荐导出流程

实验结束后：

```bash
cd /home/ubuntu/longterm_companion_web
source .venv/bin/activate
python scripts/export_results.py
```

然后打包导出目录：

```bash
cd /home/ubuntu/longterm_companion_web/storage
tar -czf exports.tar.gz exports
```

再下载到本地。
