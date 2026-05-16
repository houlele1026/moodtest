# 长期情感陪伴能力远程网页实验台

这是一个可远程部署的小型网页应用，用于比较两个模型的原生长期情感陪伴能力。

本目录已经把实验需要的主要材料收拢到一个路径下：

- `app.py`：Flask 应用入口
- `config/`：模型配置
- `data/`：episode、评分模板、历史摘要模板
- `docs/`：实验约束、pilot 草案、测试者说明、日志格式说明
- `templates/`：网页模板
- `storage/`：运行过程中生成的日志、评分和活跃 session 状态
- `requirements.txt`：本实验台的最小依赖

## 1. 适用场景

- 异地测试者通过浏览器访问实验台
- 你在服务器端统一管理 API key
- 测试者不需要安装 IDE，也不需要接触脚本

## 2. 快速启动

### 2.1 安装依赖

```bash
pip install -r experiments/longterm_companion_web/requirements.txt
```

### 2.2 配置模型

复制：

- `config/model_config.example.json`

为：

- `config/model_config.json`

然后填写模型信息。

推荐使用环境变量保存 key，而不是把真实 key 写进文件中。

示例：

```bash
export MODEL_A_API_KEY="your_key"
export MODEL_B_API_KEY="your_key"
```

Windows PowerShell:

```powershell
$env:MODEL_A_API_KEY="your_key"
$env:MODEL_B_API_KEY="your_key"
```

### 2.3 运行

开发环境：

```bash
python experiments/longterm_companion_web/app.py
```

默认地址：

- `http://127.0.0.1:5055`

## 3. 远程部署建议

### 3.1 最简方式

在服务器上运行：

```bash
waitress-serve --port=5055 experiments.longterm_companion_web.app:app
```

然后通过反向代理或端口开放，让测试者通过公网地址访问。

### 3.2 推荐部署思路

- 用一台公网可访问服务器
- API key 只放在服务器环境变量中
- 使用 `waitress` 提供应用服务
- 用 Nginx 或其他代理提供 HTTPS

## 4. 运行逻辑

1. 测试者输入 `tester_id`
2. 进入 dashboard 选择 `episode/session/model`
3. 根据页面显示的 brief 开始聊天
4. S2/S3 可由实验管理员提供标准化历史摘要文本
5. 结束后填写 session 评分
6. 每个 episode 的 3 个 session 完成后填写 episode 评分
7. 所有日志和评分自动保存到 `storage/logs/`

## 5. 日志位置

- `storage/logs/tester_<tester_id>/<episode_id>/<session_id>/<model_blind_id>/session_log.json`
- `storage/logs/tester_<tester_id>/<episode_id>/<session_id>/<model_blind_id>/transcript.md`
- `storage/logs/tester_<tester_id>/<episode_id>/<session_id>/<model_blind_id>/session_rating.json`
- `storage/logs/tester_<tester_id>/<episode_id>/<session_id>/<model_blind_id>/episode_rating.json`

## 6. 注意事项

- 本 pilot 不纳入高风险危机场景
- 测试者只能接触盲测标识 `A/B`
- S2/S3 的历史摘要建议由实验管理员统一整理
- 若后续要扩为正式实验，建议增加：
  - 管理员后台
  - 账号系统
  - 数据库
  - 调度与排期
