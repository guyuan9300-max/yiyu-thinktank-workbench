# 益语飞书 OAuth Relay

这是官网域名下的轻量授权中转服务，只做飞书成员文档授权的 `code/state` 短暂中转。

## 关键边界

- 不保存飞书 app secret、user access token、refresh token、文档内容、客户或组织资料。
- `code/state` 只保留 5-10 分钟，组织云领取后即清理。
- nginx 日志必须使用不含 query string 的格式，避免 OAuth `code/state` 进入日志。

## 服务

- 当前可用入口：`https://yiyu.love/oauth`
- 预留独立子域名：`https://oauth.yiyu.love`（需先补 DNS 和证书）
- 本机端口：`127.0.0.1:47840`
- 数据库：`/var/lib/yiyu-oauth-relay/relay.sqlite3`
- systemd：`yiyu-oauth-relay.service`

## 验证

实际健康检查在服务器本机执行：

```bash
curl -fsS http://127.0.0.1:47840/healthz
```

公网链路用“注册 session -> 模拟 callback -> claim code”的三步测试，不能只用 GET 打开 `sessions`。
