# 对话日志保存格式

## 1. 日志文件

每一次 session 都会生成：

- `session_log.json`
- `transcript.md`
- `session_rating.json`
- `episode_rating.json`

## 2. 保存目录

```text
storage/logs/
  tester_T01/
    RP1/
      S1/
        A/
```

## 3. 最低必须保存的字段

- `tester_id`
- `episode_id`
- `session_id`
- `part_type`
- `model_blind_id`
- `conversation`
- `started_at`
- `ended_at`
- `history_summary_rendered`
