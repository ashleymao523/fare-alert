# FareAlert API 契约 (v1)

> v0.28 起固化。所有 `/api/*` 路由自动镜像为 `/api/v1/*`(同 endpoint 同方法);
> 独立前端 / 原生 App / 第三方集成**只应钉住 /api/v1/***。旧路径继续可用(PWA 缓存兼容),
> 但新字段只增不删, 破坏性变更只允许发生在 /api/v2。

## 约定

- 全部 JSON; 时间戳为本地时间 ISO 字符串(`2026-09-11T13:56:06`), 日期为 `YYYY-MM-DD`。
- 金额字段均为**含税费最终支付口径**(票价+机建+燃油), 单位元。
- 读端点只读文件系统, 不触发抓取; 写/触发端点在表中标明。
- 密钥类字段响应中一律掩码, 布尔由各端点的 `*_set`/`channel_ready` 体现。

## 端点总览

| 方法 | 路径 | 职责 | 副作用 |
|---|---|---|---|
| GET | / | WebUI 单页(index.html) | 无 |
| GET | /api/snapshot | 最新一次抓取快照: 各线路逐日票价/KPI/提醒徽标(`push_pending`) | 无 |
| GET | /api/crawl-status | 各数据源逐次抓取明细(成功/失败/耗时) | 无 |
| GET | /api/cities | 城市联想列表(机场/火车站聚合) | 无 |
| GET | /api/stations | 12306 站名→电报码映射 | 无 |
| GET | /api/city-photo | 城市图片代理(缓存, 不暴露上游 key) | 无 |
| GET | /api/dest-intel | 目的地情报: 天气/汇率/低价 TOP5 | 无 |
| GET | /api/config | 配置读取(掩码 + `secrets_set` + 数据源元信息) | 无 |
| POST | /api/config | 配置保存; 响应含 `push_pending`(v0.27.1 起徽标保存即刷新) | 写 config.json |
| POST | /api/run | 立即触发一轮抓取(`push`: 是否允许推送) | 抓取+可能推送 |
| POST | /api/test-push | 向已配渠道发测试消息 | 推送一条 |
| POST | /api/reverse-search | 预算反查: "X 元以内从 A 能去哪" | 受限抓取 |
| POST | /api/amadeus-test | Amadeus 密钥连通性验证 | 无(仅鉴权请求) |
| GET | /api/alerts | 低于阈值提醒历史 | 无 |
| GET | /api/history | 每日 KPI 归档(周报数据源) | 无 |
| GET | /api/weekly-report | 周报预览(本地重算, 不推送) | 无 |
| POST | /api/weekly-push | 立即发送周报并重置 7 天计时 | 推送+写计时器 |
| GET | /api/sched-stats | 机场班期板库统计(沉淀进度) | 无 |
| GET | /api/health | 一站式健康检查: 快照新鲜度/板库/推送就绪 | 无(uptime 轮询安全) |
| GET | /api/log | 运行日志尾部 | 无 |
| GET | /report/&lt;path&gt; | report/ 静态产物 | 无 |

## 关键端点字段

### GET /api/v1/health
```json
{"ok": true,
 "snapshot": {"updated_at": "2026-09-11T13:56:06", "age_min": 5.8},
 "board": {"flights": 3628, "weekdays_covered": 2, "dows": {"3": 3210, "4": 3238}},
 "push_pending": true}
```
`push_pending=true` = 周报开关开着但 Bark/ServerChan 均未配密钥。

### GET /api/v1/snapshot
`snapshot.routes[]` 每线路含: `deals[]`(逐日 `date/price_total/depart_time/arrive_time/duration_min/alt_times/source/interp`)、
KPI(`time_coverage` 为严格口径: 剔除插值/nearby-ref)、`trains[]`(12306 对比)。
`alt_times` 为板库参考班次(仅展示, 不触发提醒)。

### POST /api/v1/config
请求体即完整配置(读取时的掩码值会被服务端还原, 不必脱敏回传)。
响应: `{ok, config(掩码), secrets_set, sources, push_pending}`。

### POST /api/v1/run
`{push: true|false}`。执行 15-20s, 响应含新快照与 `push_pending`。
频率自律: 手动触发同样计入每板每日请求预算。

## 稳定性承诺

1. `/api/v1/*` 路径、方法、既有字段名**不删不改**; 新字段随时可加, 消费方须忽略未知字段。
2. `price_total` 恒为含税最终口径, 不拆字段。
3. 变更流程: 改契约先改本文件, 再改实现, 同一 commit 落地。
