# Ubuntu 服务器部署文档

本文档面向第一次把实验台部署到 Ubuntu 服务器上的场景，默认使用：

- Ubuntu 22.04 LTS
- Nginx
- systemd
- Python 虚拟环境
- Waitress 作为 WSGI 服务

## 1. 目标结构

部署完成后，整体关系如下：

```text
公网访问
  -> Nginx (:80 / :443)
  -> Waitress (:5055, 仅本机监听)
  -> Flask 应用 experiments/longterm_companion_web/app.py
```

## 2. 前置条件

在服务器上你需要有：

- 一个 Ubuntu 实例
- 一个可用公网 IP
- 一个可以 SSH 登录的管理员账号
- 已准备好的模型 API key

如果你还没有服务器，可先看本目录外的购买说明，或直接参考腾讯云官方“快速创建 Linux 实例”文档：  
[腾讯云：快速创建 Linux 实例](https://cloud.tencent.com/document/product/1207/44548)

## 3. 登录服务器

在你本地终端执行：

```bash
ssh ubuntu@你的服务器公网IP
```

如果你买的是腾讯云 Lighthouse，首次登录也可能是：

```bash
ssh root@你的服务器公网IP
```

具体取决于你创建实例时设置的用户名和密码/密钥。

## 4. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

## 5. 上传项目

你有两种常见方式：

### 5.1 用 git 拉代码

```bash
cd /opt
sudo git clone 你的仓库地址 MoodBench
sudo chown -R $USER:$USER /opt/MoodBench
cd /opt/MoodBench
```

### 5.2 手动上传

如果你的项目还没推到远程仓库，也可以用 WinSCP、scp、SFTP 上传整个 `MoodBench` 目录到：

```text
/opt/MoodBench
```

## 6. 创建虚拟环境并安装依赖

```bash
cd /opt/MoodBench
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r experiments/longterm_companion_web/requirements.txt
```

## 7. 配置模型

复制配置文件：

```bash
cp experiments/longterm_companion_web/config/model_config.example.json \
   experiments/longterm_companion_web/config/model_config.json
```

然后编辑：

```bash
nano experiments/longterm_companion_web/config/model_config.json
```

填写你要比较的两个模型信息。

## 8. 配置环境变量

推荐通过 systemd 的 EnvironmentFile 来管理密钥。

先复制示例文件：

```bash
sudo cp experiments/longterm_companion_web/deploy/systemd/longterm_companion.env.example \
        /etc/longterm_companion_web.env
```

编辑真实环境变量文件：

```bash
sudo nano /etc/longterm_companion_web.env
```

填入：

```bash
MODEL_A_API_KEY=你的key
MODEL_B_API_KEY=你的key
LTCW_SECRET_KEY=一个足够长的随机字符串
```

## 9. 先本机测试应用

在服务器上执行：

```bash
cd /opt/MoodBench
source .venv/bin/activate
python experiments/longterm_companion_web/app.py
```

如果看到 Flask 启动成功，再开一个终端测试：

```bash
curl http://127.0.0.1:5055/health
```

正常应返回类似：

```json
{"status":"ok","time":"..."}
```

测试完成后，按 `Ctrl+C` 停掉。

## 10. 配置 systemd

复制服务文件：

```bash
sudo cp experiments/longterm_companion_web/deploy/systemd/longterm_companion.service \
        /etc/systemd/system/longterm_companion.service
```

如果你的项目目录不是 `/opt/MoodBench`，请先编辑这个 service 文件，把里面的路径改成你的真实路径。

然后加载并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable longterm_companion
sudo systemctl start longterm_companion
```

查看状态：

```bash
sudo systemctl status longterm_companion
```

查看日志：

```bash
sudo journalctl -u longterm_companion -f
```

## 11. 配置 Nginx

复制配置文件：

```bash
sudo cp experiments/longterm_companion_web/deploy/nginx/longterm_companion.conf \
        /etc/nginx/sites-available/longterm_companion.conf
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/longterm_companion.conf \
           /etc/nginx/sites-enabled/longterm_companion.conf
```

删除默认站点（可选，但通常建议）：

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

测试配置：

```bash
sudo nginx -t
```

重启 Nginx：

```bash
sudo systemctl restart nginx
```

## 12. 放通防火墙和安全组

### 12.1 腾讯云控制台

在 Lighthouse 控制台里放通：

- `80`
- `443`
- `22`

### 12.2 服务器本机防火墙

如果启用了 UFW：

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

## 13. 用公网 IP 访问

浏览器打开：

```text
http://你的公网IP
```

如果页面能打开，就表示最小可用部署已经完成。

## 14. 后续建议：加 HTTPS

如果后面要正式让异地测试者使用，建议加 HTTPS。

可以安装 certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
```

然后在你已有域名的前提下执行：

```bash
sudo certbot --nginx -d 你的域名
```

## 15. 常见问题排查

### 15.1 页面 502

通常表示 Nginx 能工作，但后面的 Waitress/Flask 没起来。

检查：

```bash
sudo systemctl status longterm_companion
sudo journalctl -u longterm_companion -f
```

### 15.2 页面打不开

优先检查：

- 腾讯云安全组/防火墙规则
- Nginx 是否启动
- 公网 IP 是否正确

### 15.3 模型调用失败

优先检查：

- `/etc/longterm_companion_web.env` 是否填对
- `model_config.json` 的 `base_url`、`model_identifier` 是否正确
- 服务器能否访问模型 API
