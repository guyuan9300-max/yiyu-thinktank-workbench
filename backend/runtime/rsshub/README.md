# RSSHub 部署指南 · 益语智库公众号自动收录

本目录提供 RSSHub 自部署的 docker-compose 配置，益语智库后端会从这个 RSSHub 实例抓公众号 RSS feed，把每篇文章自动入官方语料池。

## 为什么自部署而不是用 rsshub.app 公共实例

- 公共实例对公众号路由有严格 rate limit，每分钟最多几次
- 公众号路由依赖 puppeteer + browserless，公共实例的 chromium 时常被对方封
- 自部署可以加 `ACCESS_KEY` 防滥用、调大缓存、稳定运行

## 部署步骤（在火山云一台最小 2C2G 机器上即可）

### 1. 装 docker + docker compose

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
```

### 2. 把本目录拷贝到服务器

```bash
scp -r backend/runtime/rsshub/ user@<host>:/opt/rsshub/
ssh user@<host>
cd /opt/rsshub
```

### 3. 生成 ACCESS_KEY 并启动

```bash
# 生成 32 字节 hex key（务必记录, 后端配置要用）
export RSSHUB_ACCESS_KEY=$(openssl rand -hex 32)
echo "RSSHUB_ACCESS_KEY=$RSSHUB_ACCESS_KEY" >> ~/.bashrc

# 启动（首次会拉 3 个镜像, 大约 800MB）
docker compose up -d

# 看日志确认起来了
docker compose logs -f rsshub
```

### 4. 测试 RSS 路由

```bash
# 假设你的 RSSHub 在 http://<host>:1200, ACCESS_KEY 是 ABC123
curl "http://<host>:1200/wechat/cn/ricifoundation?key=ABC123"
```

理论上应该返回一个 RSS XML，含日慈最近若干篇推文。

## 公众号路由选择

RSSHub 公众号有多条路由，按可用性排序：

| 路由 | 说明 | 稳定性 |
|---|---|---|
| `/wechat/cn/<id>` | 微信中文镜像，基于公众号英文 ID | ⭐⭐⭐ 最稳 |
| `/wechat/wemp/<id>` | 微小宝镜像 | ⭐⭐ |
| `/wechat/ths/<key>/<id>` | 天行数据，需 ths key（付费） | ⭐⭐⭐⭐⭐ 商用首选 |

`<id>` 是公众号的英文 ID，比如「日慈公益基金会」的 `ricifoundation`。

### 怎么查公众号英文 ID

1. 微信里搜公众号「日慈公益基金会」→ 进主页 → 点右上 ··· → "查看公众号"
2. 看到的英文字串就是 ID
3. 或者搜狗搜 `weixin.sogou.com/weixin?type=1&query=日慈公益基金会`，结果里有「微信号: ricifoundation」字样

## 集成到益语智库

后端配好 RSSHub 后，前端 BrandMirrorPanel 的「微信公众号」面板传 `rssUrl` 调：

```http
POST /api/v1/intelligence/brand-mirror/wechat-ingest
{
  "clientId": "client_284afd836e",
  "rssUrl": "http://<host>:1200/wechat/cn/ricifoundation?key=<ACCESS_KEY>",
  "maxArticles": 50
}
```

后端会：
1. fetch 这个 URL 拿到 RSS XML
2. 解析所有 mp.weixin.qq.com 文章链接
3. 把链接列表当 seed_urls 提交给现有的 internet_enrichment 异步队列
4. 每篇文章走完整爬虫管线，入 `brand_official_corpus`，跟官网语料同池

## 增量更新

每次调 `/wechat-ingest`：
- RSSHub 自身有缓存（默认 1 小时）
- 文章入库时 `content_hash` 去重，已存在的 hash 跳过
- 所以重复调用不会产生重复数据，只会新增最近的几篇

建议每天定时调用一次（用 macOS launchd / Linux cron）。
