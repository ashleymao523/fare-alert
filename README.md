# FareAlert · 低价出行提醒组件

[![CI](https://github.com/ashleymao523/fare-alert/actions/workflows/ci.yml/badge.svg)](https://github.com/ashleymao523/fare-alert/actions/workflows/ci.yml)
[![Daily Check](https://github.com/ashleymao523/fare-alert/actions/workflows/daily-check.yml/badge.svg)](https://github.com/ashleymao523/fare-alert/actions/workflows/daily-check.yml)

监控未来 N 天 **机票最低价(含机建燃油,即最终支付口径)**,低于你的心理价位就推送到 iPhone;同时对比 12306 列车全席位票价(二等座/卧铺/普速,含学生票估算),帮你选出**出行最优方案**。自带 Web 仪表盘,单文件依赖极简,适合部署在私人设备上长期运行。

> 个人比价参考工具:数据来自公开接口的低频查询,不破解任何签名/验证码,购票始终跳转官方/平台页面人工完成。

> 📖 **新手建议先看 [使用指南.md](使用指南.md)** —— 组件介绍 / 从零搭建 / 推送配置 / 日常使用,一条龙图文教程。

## 功能特性

- ✈️ **机票低价监控**:去哪儿价格日历(免登录公开接口),一次拉取未来数月每日最低价+航班号,总价=裸价+机建+燃油(可配置)
- 🔔 **低于心理价位即推送**:Bark(iPhone 通知)+ ServerChan(微信)双通道,带去重/冷却/降价再提醒,不轰炸
- 🚄 **列车对比(全席位)**:12306 票价接口(免登录),接口查到什么席位就展示什么(二等座/一等座/商务座/硬卧/软卧/动卧/硬座…),含学生票估算,识别夕发朝至车次
- 🧳 **托运行李标注**:按航司标注是否含免费托运,廉航/特价舱自动加 ⚠️ 提示
- 🧠 **联想输入**:城市/车站全部从数据源字典联想选择(中文/全拼/首字母,如 hzd→杭州东),不依赖手输精确文字,不会因偏差走模糊搜索
- 📊 **Web 仪表盘**:60 天价格热力日历、价格趋势图、"出行最优"卡片对比(机票/动车/学生动车/卧铺)、配置全可视化编辑
- ⚙️ **一切皆可配**:出发/到达城市、窗口天数、心理价位、税费、数据源开关、查询频率——页面上直接改
- 📦 **多线路**:支持同时监控任意多条线路(如 杭州→重庆、成都→杭州 …)
- 🔁 **往返模式**:按"去程+返程合计总价"判定阈值,主趋势图显示往返合计、另附返程独立趋势,日历热力按合计着色
- 🌍 **国际航线**:免 Key 即可用——自动接入去哪儿国际特价日历(稀疏但真实的含税促销价);配置免费 Amadeus Key 后升级为全日期覆盖 + 真实起降时刻(数据源页内置 3 步配置向导 + 一键测试连接)
- 🕐 **航班时刻与时长(v0.19 跨日班期补全)**:详情卡起飞→落地时间轴;杭州出发/到达线路自动经机场官网公开班期板沉淀「航班号+星期几」计划时刻库(零密钥、6h 缓存),目标星期未沉淀时自动借用同号航班其他班期时刻(「跨日班期·参考」徽标),仅有起飞时落地按大圆估算(~ 前缀);配置 Amadeus 后优先实时刻
- 📱 **PWA(v0.20)**:PNG 图标 + Service Worker 离线壳(静态资源缓存优先、接口网络优先+离线兜底),iPhone Safari「添加到主屏幕」后获得独立图标与最近一屏数据的离线阅读;数据源页新增「时刻库沉淀进度」七天可视化,时刻缺口原因一目了然
- 🩹 **缺价日自动补全**:去哪儿日历缓存没价的日期(返回空价)自动用 Amadeus 含税最低价补洞,日历/趋势/最优卡打「Amadeus补」徽标,补全结果缓存 24 小时保护免费额度;未配密钥时优雅跳过
- 📐 **无价日插值估算(v0.11)**:两侧 14 天内都有真实价的空洞日按距离线性插值(琥珀色斜纹+≈前缀,取整到 10 元);插值/参考价一律不触发提醒、不参与最低价/均价/TOP5 统计,趋势图估算点为琥珀空心圆
- 🕸 **爬虫监控**: 每次抓取逐步实时可视化——数据源/动作/耗时/条数/缓存命中/错误,保留最近 20 次运行历史; 手动查询时自动 2 秒轮询刷新
- 🫀 **数据源健康自愈(v0.12)**: 每轮抓取自动聚合各源健康分(滑动窗口),单轮≥2步失败或连续3轮失败即降级并展开诊断(候选原因+修复动作),恢复后自动解除;爬虫监控页顶部常驻绿/琥珀/红徽标,MCP snapshot_get 同步透出降级源供 Agent 自助排障
- 🧭 **预算找目的地(v0.13)**: "¥X 以内从 A 出发能去哪"——逐候选查价格日历,按含税总价升序返回可去列表(日期/航司/直达购票链接/实时·缓存新鲜度徽标);实发请求有硬预算(默认8,上限15,缓存命中不耗预算),结果缓存 6 小时;Web UI 新增「预算找目的地」页,MCP 新增 reverse_search 工具
- 📈 **洞察周报(v0.14)**: 每轮查询自动归档每日线路指标(最低含税价/均价/低价天数,保留180天),周报汇总本周最低·均价·环比上周·最佳出发日,每个数字可从历史重算;Web UI 新增「洞察周报」页(周度走势图+摘要卡),推送默认关闭(push.weekly_enabled 开启后每 7 天自动推一次)
- 🔗 **一键直达购票**: KPI 卡、对比卡、车次表全部可点——机票直达去哪儿下单页, 车次直达 12306 预填查询页(自动带入日期/车站)
- 🔒 **本地优先**:数据只落在本机 data/ 目录,推送 key 只存在本机 config.json(不入库)

## 界面预览

Web 仪表盘(v0.8 设计系统:Skyscanner 式浅色+城市图鉴+低价柱状图,移动端自适应并带浮动低价提醒横幅,iPhone 可"添加到主屏幕"当 App 用):

v0.29 起新增 **/v2 前后端分离版**(web/ 下的 Vite+Preact 工程,构建产物由后端同源托管,使用者无需 Node;开发者改界面见使用指南第十一节)。

| 仪表盘 | 配置编辑 |
| --- | --- |
| KPI 卡片 / 价格热力日历 / 趋势图 / 出行最优判定 | 线路 CRUD / 数据源开关 / 推送设置 |

## 快速开始

### Windows

1. 安装 Python 3.10+(勾选 Add to PATH)
2. 安装依赖:

   ```powershell
   pip install -r requirements.txt
   ```

3. 双击 `start_windows.bat`,浏览器自动打开 http://127.0.0.1:8765
4. 在"提醒推送"页填入 Bark Key(iPhone App Store 下载 Bark,复制 Key),点"发送测试推送"验证
5. 想要后台自动监控:以管理员运行 `deploy/register_task.ps1`(计划任务每 45 分钟静默查询一次,满足条件即推送)
6. 想要开机自启(面板+抓取循环):运行 `tools/install_autostart.ps1`(写 HKCU Run 键,免管理员,默认装 webui+worker 双条目;`-Components webui` 仅面板;`-Uninstall` 卸载;已在运行时自动跳过)。worker 循环持续采集班期板,星期覆盖 7 天长满后起飞时刻缺口自动收敛

### macOS / Linux

```bash
pip3 install -r requirements.txt
bash start_mac.sh
# 或后台常驻: python3 main.py --loop
```

### Docker(推荐用于 NAS / 云主机 / 长期无头部署)

v0.69 起提供容器化部署:镜像内置生产级 WSGI 服务器(waitress),数据与配置全部挂载在宿主机,容器随删随建:

```bash
# 首次:准备 config.json(可先 cp config.example.json config.json 改好再起)
docker compose up -d --build
# 查看面板
open http://127.0.0.1:8765
# 升级:git pull 后重建
docker compose up -d --build
```

容器内 Web 面板与 Windows 本机同模型:内置监督线程自动拉起/热换 `main.py --loop` 采集进程,无需额外配置 worker 容器。`data/` 持久化班期库/快照/历史,`config.json` 改动重启容器即生效。

### iPhone 上怎么用?

iPhone 不跑 Python 后端,它的角色是**接收推送 + 查看面板**:

- **推送**:装 Bark → 复制 Key 填入配置,低于价位秒收通知,通知可直接跳购票页
- **面板**:把 Windows/Mac 上 config.json 的 `webui.host` 改为 `0.0.0.0`(并在防火墙放行 Python),手机 Safari 访问 `http://电脑局域网IP:8765`,分享→添加到主屏幕,即得到一个全功能 App 图标

## 配置说明

首次运行自动生成 `config.json`(个人配置,已 gitignore);模板见 `config.example.json`,所有项均可在 Web UI 修改:

| 配置 | 说明 | 默认 |
| --- | --- | --- |
| routes[].from_city / to_city | 出发/到达城市(必须中文城市名) | 杭州 / 重庆 |
| routes[].trip_type | 行程类型:oneway 单程 / roundtrip 往返(按合计价判定) | oneway |
| routes[].intl + from_iata / to_iata | 国际航线开关 + IATA 三字码(intl 时必填,如 HGH/NRT) | false / 空 |
| routes[].window_days | 查询窗口天数 | 60 |
| routes[].threshold_total | 心理价位(总价口径,含机建燃油) | 500 |
| routes[].train_compare.station_pairs | 动车对比车站对,如 杭州东|重庆北 | 杭州东/杭州西→重庆北/重庆西 |
| tax.airport_fee + fuel_surcharge | 机建+燃油(当前合计 120) | 50+70 |
| push.bark_key / serverchan_sendkey | 推送通道(留空禁用) | 空 |
| schedule.interval_minutes | 轮询间隔(分钟) | 45 |
| sources.enabled | 数据源开关(可用/规划中) | 全开 |
| sources.amadeus | 国际数据源(env=test/prod + client_id + client_secret,在 Web UI 数据源页填写) | test / 空 |

## 数据源与合规

| 源 | 状态 | 说明 |
| --- | --- | --- |
| 去哪儿·价格日历 | ✅ 可用 | 免登录免签名的公开接口,一次返回 365 天每日最低价(挂牌价,不含 OTA 券后;与券后实付通常只差小几十,可接受) |
| 12306·票价查询 | ✅ 可用 | 免登录低频查询,结果缓存 24h;全席位(含卧铺/普速 K/T/Z);学生票按 动车二等75折/硬座5折/硬卧=卧铺-硬座半价 估算(以下单页为准) |
| 去哪儿·国际特价日历 | ✅ 可用(免 Key) | 国际线路的兜底数据源:返回稀疏但真实的含税促销价(每月约 3-5 个日期),配 Amadeus Key 后自动合并、同日取更低 |
| Amadeus·低价日历(国际+补全) | ✅ 可用(需免费 Key) | developers.amadeus.com(注意复数)注册 Self-Service,用 /v1/shopping/flight-dates/cheapest 查含税最低价;国际线路全量使用,国内线路缺价日自动补洞(缓存24h) |
| Amadeus·航班时刻表 | ✅ 可用(需免费 Key) | /v1/schedules 按月查询真实起降时刻,匹配航班号自动填充详情卡;24h 缓存 |
| 机场班期·参考时刻 | ✅ 可用(免 Key) | 杭州机场官网公开班期板(与浏览器同源只读接口),按 航班号+星期 沉淀计划起降时刻库;目标星期未沉淀时跨日借用同号航班班期(v0.19),详情卡打「计划时刻·机场班期/跨日班期·参考」徽标,Amadeus 配置后自动让位实时刻 |
| Wikipedia·城市图片 | ⚠️ 视网络而定 | /api/city-photo 经 REST summary 取城市实拍图(缓存24h,失败负缓存);大陆网络下 Wikimedia 域名常不可达,自动回退到内置旅行海报剪影(离线可用) |
| 临近日参考价(内置) | ✅ 可用(免 Key) | 源日历"查价"空洞日自动镜像最近有价日的价格作展示参考(7 天内紧参考/45 天内远参考,标注距离天数);仅用于补全日历显示,**不触发提醒、不参与最优价判定**,点击直达当日实查 |
| 插值估算价(内置) | ✅ 可用(免 Key) | v0.11:空洞日两侧 14 天内均有真实价时按距离线性插值;**仅展示用,不触发提醒、不参与统计**,详情卡标注参考航班号 |
| 携程 H5 / 航司官网 | 🚧 规划中 | 备选交叉验证源 |

原则:**不破解签名、不绕过验证码、低频查询(分钟级)、只读公开数据、购票永远人工**。请将本工具用于个人比价,勿改造为商业爬虫。

## 项目结构

```
fare-alert/
├── main.py            # 后端核心:查询→判定→推送 流水线
├── webui.py           # Web 仪表盘(Flask)
├── core/
│   ├── config.py      # 配置加载/合并
│   ├── flights.py     # 去哪儿价格日历
│   ├── trains.py      # 12306 票价+车站字典
│   ├── alerts.py      # 阈值判定/去重/消息组装
│   ├── notify.py      # Bark/ServerChan 推送+历史
│   ├── crawl.py       # 抓取遥测(爬虫监控数据)
│   └── report.py      # 静态 HTML 报告(旧版)
├── webui/             # 前端(原生 JS,无构建步骤)
├── deploy/            # Windows 计划任务注册/卸载
├── tools/             # 接口侦查脚本(开发用)
└── data/              # 快照/状态/日志/提醒历史(运行时生成)
```

## 开发路线图

- [x] **v0.1 实现**:双源查询、含税总价、阈值推送、托运标注、计划任务
- [x] **v0.2 可视化**:Web 仪表盘、热力日历、趋势图、出行最优判定、可视化配置
- [x] **v0.3 全席位+联想输入**:12306 全席位(卧铺/普速)、城市/车站拼音联想选择、快捷线路模板、多线路编辑器、学生卧铺估算
- [x] **v0.4 爬虫监控+直达购票**: 抓取步骤实时可视化(耗时/条数/缓存/错误)、KPI/对比卡/车次表一键直达购票页、车次时刻+历时展示、航班时刻字段预留
- [x] **v0.5 高级趋势图**: 平滑曲线、渐变面积/描边、悬浮十字线提示、周末底纹、阈值线与低价点高亮
- [x] **v0.6 浅色重设计+往返+国际**: shadcn 风格浅色主题、趋势图浅色化并新增返程趋势、往返合计判定、Amadeus 国际线接入
- [x] **v0.6.1 缺价补全**: 去哪儿日历空洞自动用 Amadeus 含税价回填、来源徽标、24h 缓存、内置城市→IATA 映射
- [x] **v0.7 国际免Key+航班时刻+UI精修**: 去哪儿国际特价日历免 Key 兜底、Amadeus 时刻表增强(真实起降+时长)、时长大圆估算、详情卡起降时间轴、Amadeus 配置向导+测试连接、v0.7 设计系统(渐变强调色/热度日历/时刻卡片)
- [x] **v0.8 缺价补全+Skyscanner式UI+移动提醒**: 临近日参考价补全(7天紧/45天远二级半径+距离标注+≈标记,日历 60/60 无空洞)、v0.8 设计系统(Skyscanner 配色/城市图鉴 Hero/低价柱状图视图/日历柱状一键切换)、移动端浮动低价提醒横幅+震动+系统通知授权按钮、城市旅行海报剪影(6 种 SVG 场景离线渲染,Wikipedia 实拍图网络可达时自动叠加)、Amadeus 官方域名修正(developer→developers)、中转行程按航段匹配真实时刻、无时刻状态"时刻待接入"徽标
- [x] **v0.9 扁平趋势图+API指引**: Google Flights 式扁平趋势(去渐变/辉光/动画,均价点线,最低价标注)、Amadeus 注册直达与推送指引
- [x] **v0.10 TOP5+目的地情报**: 低价日 TOP5 表、目的地天气(Open-Meteo)/汇率情报卡、Amadeus 隐私说明
- [x] **v0.11 插值补全**: 无价日期两侧真实价线性插值(琥珀标识,不参与统计)、趋势图估算空心点
- [x] **eng 工程化**: AGENTS.md 人机守则、G0-G6 验收门禁(tools/acceptance.py)、核心单测、CI
- [x] **M1 Agent接入**: 自研零依赖 MCP Server(stdio)五工具 fare_search/train_search/watch_add/watch_del/snapshot_get、"一句话建监控"意图解析(12组单测+8项协议自测+独立E2E验收)
- [x] **M2 源健康自愈**: 健康分/双阈值降级/诊断报告/UI徽标/MCP透出(单测 7/7)
- [x] **M3 反向搜索(首版)**: 预算过滤含税口径/请求硬预算+限速/6h结果缓存/UI页签+直达链接/MCP工具(单测 5/5,多城市并行与节假日联动留 M3.1)
- [x] **v0.18 零密钥航班时刻**: 萧山机场公开班期板→周班期时刻库(核心/sched_board),Amadeus 未配置时兜底填充起降时刻并打徽标,含共享航班号索引/到达板双时刻优先/15项单测;周报自动推送增加无渠道守卫(不再空耗 7 天计时器)。复核修复:时刻库合并改「双时刻整替/残缺行只填不删」防丢时刻、每板每日抓取硬上限落地(≤2次/日)、库文件原子写+坏库先备份、推送渠道非 200 显式标 ERR、周报全失败 6h 退避防 45 分钟风暴、非杭州线路跳过班期抓取
- [x] **v0.19 跨日班期时刻补全**: 班期板无日期参数(官网页面无日期选择,?date= 与路径段探测均无效,按日期回填否决)→改跨日借用:日历价已证明航班号当日执飞,board_lookup_x 先精确星期再跨星期借用同号时刻(优先双时刻条目),「跨日班期·参考」徽标;仅有起飞时新增落地估算 arr_est(大圆+滑行,~ 前缀+虚线样式,不写入 arr_time 防混源);时刻仍纯展示不影响提醒。新增 9 项单测(42+8 全绿),dump_dom 改同步等待版防半写
- [x] **v0.20 真 PWA + 时刻库透明度**: 新增 tools/gen_icons.py(PIL 渐变底+纸飞机,可复现)产出 512/192/180/32 与 maskable 图标,manifest 补 PNG(iOS apple-touch-icon 不支持 SVG 的空白主屏图标修复);sw.js 离线壳(/static 缓存优先、?v= 版本 busted;/api GET 网络优先+缓存兜底);/api/sched-stats + 数据源页七天沉淀进度 widget(回答「为什么这天没时刻」);周报推送无渠道时自动跳转推送页并高亮输入框。新增 2 项单测(44+8 全绿)
- [ ] **M4-M5**: 洞察周报/插件生态(见 docs/迭代路线图.md)
- [x] **v0.21 时刻覆盖仪表 + 自启 + selftest 隔离**: snapshot 每线路写入 time_coverage(起飞/落地时刻 精确/借用/估算/缺失 四档统计,剔除邻近日参考价),数据源页新增「本轮时刻覆盖体检」分组条形图,时刻质量从黑盒变仪表;mcp_server 支持 FAREALERT_HOME 环境变量,selftest 改临时目录副本运行(修复并发验收假 FAIL,真实 config.json 零触碰+校验);tools/install_autostart.ps1 一条命令装开机自启(HKCU Run 键,免管理员,8765 已监听自动跳过,-Uninstall 卸载,-Mode task 备选计划任务);周报页无推送渠道时「立即推送」按钮直接禁用并提示,不再点了才报错。新增 5 项单测(49+8 全绿)
- [x] **v0.22 经停友好时刻借用 + 按字段来源 + 推送修复**: board_lookup_x 城市匹配改四层分级(双城>仅出发侧=经停>仅到达侧>拒绝),经停航班(杭州→克拉玛依经停郑州类)不再被整体误杀,跨 dow 借用只认双城/经停两档;FlightDeal 拆出 dep_src/arr_src 独立字段,「起飞精确+落地借用」混合态可表达,前端徽章按段显示;测试推送重复告警去重+test-push 标记;autostart wrapper 读 config webui.port 不再写死 8765。新增 4 项单测(53+8 全绿)
- [x] **v0.23 趋势图重画 + 全站去装饰渐变**: 趋势主线从 AI 感靛紫统一为品牌蓝并加 7% 面积填充,新增顶部图例行(低于价位/高于价位/含税总价/30日均价/插值估算),最低价标签改绿色胶囊,点位色收敛为绿/灰两档,悬停点统一品牌蓝;全站清理 20 处装饰性渐变(品牌名渐变字/按钮/日历格/角标/城市海报底色改纯色),仅保留功能性纹理与遮罩。视觉对齐 Skyscanner 式克制风格。
- [x] **v0.24 沉淀进度 ETA + 周报推送三步引导**: 时刻库沉淀进度 widget 增加「预计全覆盖日期」推算(按当前星期推算剩余 dow 的入库日期,覆盖 N/7 天·预计 M/D 全覆盖,每个 dow 悬停可见预计入库日);周报页推送引导从单条警示升级为按缺口动态生成的分步清单(无渠道/未启用两维检测,/api/weekly-report 新增 channel_ready 字段,一键跳转提醒推送页),修复用户 config 缺 weekly_enabled 键时周报静默不推且无引导的问题;CSS 引入 4 级间距变量(--sp-1~4),容器 1100→1160px、卡片/网格间距统一收口,版面呼吸感更接近开源旅行产品。
- [x] **v0.24.1 API v1 版本化别名**: 全部 /api/* 路由自动镜像为 /api/v1/*(同 endpoint 同方法,旧路径一等公民不受影响),为未来独立前端/原生 App 提供可钉住的稳定契约——前后端物理分离的「留缝」落地;新增 tests/test_api_v1.py 4 项契约测试(路由镜像完备性/v0-v1 响应等价/POST 方法保持/新字段),并修复测试文件直跑时项目根不在 sys.path 的问题。tools/probe_ota_times.py 留档本日时刻源勘探结论(去哪儿日历接口无起降时刻字段,思路关闭)。
- [x] **v0.25 同航线真实时长先验**: 落地时刻估算从「大圆圈几何模型」升级为「数据驱动」——萧山到达板每天 1600+ 行双时刻(前站起飞 preschtime + 落地 jhsj)沉淀出 83 城真实飞行时长中位数,直飞航线的 arr_est 与时长文本改用同航线实测值(重庆 140min/成都 155min/郑州 100min/曼谷 240min,几何模型普遍高估 10-30 分钟);国际前站城市名归一化(「曼谷素万那普机场」→「曼谷」)+ 前缀合并查询取最繁忙机场;经停航线保持几何+中转模型(先验只覆盖单段,不能映射多段)。tools/probe_dest_boards2.py 留档目的地机场勘探负结论(郑州 DNS 失败/重庆官网域名停放/成都 403,大陆目的地机场板数据源关闭),返程方向(落地杭州)时刻可由萧山到达板精确命中,开启往返线路即自然生效。
- [x] **v0.26 无号日历价参考班次 + Docker 部署修复**: Amadeus 日历价无航班号的日期(曼谷 48/50)按城市+星期从萧山板库补「当日参考班次」chips(exact/cross-dow 标记, 只展示不触发提醒); Docker start.sh 补 --loop 修复调度假死, 端口统一 8765; 顶栏新增「提醒未配置」健康徽标直达推送页。全套 43+9 单测全绿。
- [x] **v0.26.1 参考班次补挂修复**: nearby-ref 日期在 enrich 之后才补齐导致挂载点失效, 新增幂等 _attach_alt_times 在 fill 后补挂(只挂去程), 曼谷 48/50 日期获得起飞时刻参考; 同轮修复测试归位/徽标实时刷新/start.sh 优雅关停。全套 43+11 单测全绿。
- [x] **v0.27 覆盖率合并口径 + 部署可观测**: KPI 覆盖大数字改精确+参考合并口径(副文案拆分); /api/health 一站式健康端点(快照新鲜度/板库沉淀/推送就绪, 供外部 uptime 监控轮询); 顶栏更新时间带绿/黄/红新鲜度状态色。
- [x] **v0.32 落地时刻精确化 + v2 默认入口**: 出发板 nextschtime 提取为精确落地时刻(经停存 via 元数据)+ 离线回填 backfill_from_cache + 快照再富化工具 reenrich_times.py, 双时刻条目 3253→6075(重庆真实落地 22/39, 此前全 0); / 根路径 302 至 /v2/, 经典版转 /classic 维护模式; Docker HEALTHCHECK。85 单测全绿。(v0.28–v0.31 设计令牌/web 前端工程/三波 tab 迁移详见 docs/迭代路线图.md)
- [x] **v0.33 中转/经停透明化 + CI 前端门禁**: 联程票首段到达+中转城市、经停票经停站+到达时刻从板库透传至日详情时间线(「中转 武汉 · 08:55 到」), 四线 81 天获得说明, 估算落地不再是无解释的孤数; ci.yml 新增 frontend job(npm ci+build+git diff --exit-code, dist 与提交强制同步)。87 单测全绿。
- [x] **v0.34 部署工业化: worker 自启 + 心跳可观测**: 「时刻显示不全」的机制根因=抓取循环无人拉起、班期 dow 覆盖停在手动运行那两天。autostart_worker.ps1 单实例守卫 + install_autostart.ps1 升级双组件(-Components webui,worker); main.py 每轮写心跳、/api/health 暴露 worker 存活年龄; 无时刻文案按换季/联程段细化原因。92 单测全绿。
- [x] **v0.35 调度心跳面板化 + 板库 API 勘探归档**: v2 数据源页新增「调度心跳」卡——/api/health 的 worker 状态(运行中脉冲/心跳过期/未启动三态 + 最近轮次成败与分钟年龄)从命令行知识变成面板可视化, 未启动时直接给出 autostart_worker.ps1 启动指引; tools/probe_hbh_date.py 归档板库 API 勘探负结论(无 date 参数, keywords 仅航班号, 只服务当天 → dow 覆盖唯一路径=worker 每日积累, v0.34 自启方向实证正确)。92 单测 + ui_check(新增 v0.35 断言) 全绿。
- [x] **v0.36 UI 质感专项: 排版放大 + 趋势图重做**: 「不够高级」的根因之一=字号系统偏小(正文 13px/KPI 数字 22px)。v2 专属排版令牌层(--fs-body2/title2/hero2/kpi2, 正文 14/标题 16/Hero 28/KPI 30) + 趋势图重做(Catmull-Rom 平滑曲线、去掉 60 个噪声点只留信息点、最低价绿色胶囊标签、周末淡色底带、心理价位文案标签、悬浮卡片阴影升级) + tab 导航改分段控制器 + Hero 去 emoji(无照片显示城市首字、纸飞机换 SVG)。92 单测 + ui_check(新增 v0.36 断言) 全绿。

- [x] **v0.37 agent 自主验收闭环: verify_release MCP 工具**: 多 agent 协作的最后一块拼图——子 agent 改完代码可自助跑验收链, 不再依赖主 agent 手工转述。新增 MCP 工具 verify_release(steps=unittest/ui_check/build/health, 默认 unittest+ui_check+health), 返回结构化 {all_ok, steps:[{step,ok,seconds,tail}]}; health 步骤读 config 探活 /api/health 并给 worker 三态语义(alive/stale/none)。mcp_selftest 扩到 10 项(含真实 tools/call verify_release), 新增 5 个全 mock 单测, 全套 97 全绿。

- [x] **v0.38 部署硬化: worker 每日自愈机制**: 「起飞时间显示不全」的机制根因=自启只在登录时触发, 桌面数周不重登则 worker 死后无人拉活, dow 覆盖冻结(实测 2/7)。双层自愈: ① webui 进程内守护线程(每日 07:00 窗口探测 main.py --loop, 缺失则拉起; 纯 Python 跨平台, 不依赖任务计划权限——本机 Register-ScheduledTask 实测拒绝非提权会话); ② install_autostart.ps1 尽力注册每日计划任务(允许的宿主生效, 拒绝则告警不失败)。/api/health 暴露 revive 双层状态(supervisor+task), v2 数据源页心跳卡新增自愈状态行。106 单测 + ui_check(v0.38 断言) 全绿。

- [x] **v0.41 时刻回写闭环 + catch-up 自愈 + 迁移备份**: ① 每日巡检后离线回写快照起降时刻(core/reenrich, 零网络请求, 无变化跳写+滚动备份, 面板当日反映班期库增长), 数据源页巡检行显示回写覆盖; ② 迟到开机 catch-up——错过 07:00 窗口的桌面在 worker 心跳 >6h 且当日未补拉时仍探测+拉起一次(修复周末关机后班期 dow 覆盖冻结 2/7 的根因, 实测重启当日 2/7→3/7); ③ tools/backup.py + restore.py 一键备份/跨设备还原(config+快照+班期库+提醒状态+缓存+周报历史, 白名单精确匹配+realpath 纵深防御防 zip 穿越, 单坏成员不中断整包还原)。133 单测 + ui_check(v0.41 断言) + acceptance 全绿; Zeno 评审 PASS-with-notes, P1(zip-slip 前缀旁路)当轮修复。(v0.39–v0.40 推送可诊断化/巡检定时化详见 docs/迭代路线图.md)
- [x] **v0.42 公务舱低价监控 + 共享航班时刻兜底**: ① cabin_watch 配置块(默认目的地杭州可改, 多出发地白名单, 独立阈值+冷却), core/cabin_monitor.py 环形历史(data/cabin_history.json, 同日同舱最新价覆盖) + 阈值命中走既有推送通道; ② 公务舱报价走 Amadeus flight-offers(travelClass=BUSINESS, 窗口内均匀采样≤8天, 无 key 安全跳过), 去哪儿低价日历实测仅经济舱地板价、列表页需签名不可用; ③ 共享航班号(SC2114/SC2135/G5虚拟号)班期库零收录导致的时刻空白, 现挂同日同航线已知班次作参考(alt_times 语义不变不造假), reenrich 变更检测含 alt_times(修复 coverage 不变时跳写的盲区), 实测 12/12 天补上参考班次; ④ /api/cabin + v2 公务舱监控卡(历史最低/样本数/阈值状态/最近提醒)。单测 133→145。
- [x] **v0.43 公务舱精确时刻 + 监控面板编辑**: ① fetch_cabin_offers 解析 flight-offers itineraries.segments 的 departure.at/arrival.at, 公务舱行带上当日精确起降时刻+航班号(多段联程拼 MU5458/CZ3383 并标中转机场), time_src=amadeus 为最强源; ② 修复 v0.42 真 bug——经济舱日历无缺口时 "if not gaps: return" 早退导致公务舱采集被整体跳过, 采集块前移到补全早退之前, 且 gap 覆盖集只统计经济舱行(公务舱行不再干扰经济舱补全判定); ③ _enrich_flight_times 加 offer-exact 守卫(多段/单段的 schedules 匹配不再覆盖 flight-offers 精确时刻); ④ /api/config 校验 cabin_watch(enabled/cabins/default_to_city/threshold_total/cooldown_hours/watch_from_cities, 出发城市列表去空去重), v2 CabinCard 面板可视化编辑(启用开关/目的地/阈值/冷却/出发城市列表, 保存走既有 config POST 通道)。单测 145→153。
- [x] **v0.44 经济舱 offer 精确兜底 + Amadeus 用量透明**: ① 时刻覆盖推广到经济舱——cheapest-dates 也补不到的缺口日期, 用 flight-offers(ECONOMY, max=3) 逐日兜底, 一并拿到精确起降时刻+航班号+中转信息, 与公务舱共用 _best_offer/_cabin_offer_times 解析; ② 兜底结果按日期缓存 24h(含负缓存: API 无报价的日期当天不再重试), 45 分钟轮询循环下配额安全; ③ Amadeus 调用按日计数(14 天滚动), /api/amadeus-usage + 数据源页"今日调用 N 次"让配额消耗可见; ④ 公务舱监控表加近 10 样本 sparkline 走势列(对齐主趋势图 accent 风格)。单测 153→158。
- [x] **v0.45 监控城市点选 + 覆盖率趋势**: ① 公务舱监控编辑卡输入升级——目的地与监控出发城市不再手打顿号分隔文本, 目的地复用 AcField 城市库联想下拉, 出发城市改为 chips 点选输入(城市库过滤+回车自由添加+Backspace 删末尾+点 × 移除, 留空=全部出发地), 与路线页同一份城市数据源, 杜绝手输偏差; ② 时刻覆盖率从瞬时值升级为历史趋势——每日 KPI 归档新增 cov{dx,db,dm} 起飞时刻计数, core.history.coverage_trend 纯函数聚合成日线序列, /api/coverage-trend + 数据源页覆盖体检卡顶部趋势小图(扁平填充无渐变, 首尾占比/跨日参考/缺失占比标注, 单点日显示"基线已记录"), 让"起飞时刻全覆盖"目标的推进进度可见; ③ 存量 history.json 无 cov 的旧记录安全跳过不画 0%。单测 158→164。
- [x] **v0.46 班期板按行内真实日期入档**: 机场板接口单次返回跨两天(今天+明天)的航班行, 旧逻辑把整板按抓取日星期入档——次日航班错进错误星期档, 既产生错误“精确命中”又浪费免费次日数据。① 每行改从自身 jhsj 日期(leave=起飞日/arrive=到达日)解析真实 weekday 入档, 解析失败回退抓取日, 一次抓取可沉淀两个星期档; ② 存量库格式迁移(fmt=2 标记): 旧格式错档无法就地修复, 发现即清空并用 7 天板缓存离线重放重建(零网络), 幂等; ③ 本地实测: 星期覆盖 3/7→5/7(工作日档全齐), 剩余两档随本周轮询自然补齐, board_lookup 精确命中率上升 → 起飞时刻精确占比上涨的直接根因修复。单测 164→166。
- [x] **v0.47 公务舱多目的地监控 + 采集节奏可视**: ① cabin_watch 目的地从单值升级为 to_cities 列表(默认杭州, 随时增删改), 旧配置 default_to_city 自动派生列表并保持同步, route_qualifies 按列表匹配任意目的地; ② /api/cabin 新增 refresh(每轮间隔+上轮/下轮时间, 来自 worker 心跳)与 qualifying_routes(当前正在采集的路线), 卡片上直接可见“每 45 分钟一轮 · 上轮 xx:xx · 下轮 ≈xx:xx”与采集路线标签, 无匹配路线时提示去路线页添加; ③ 编辑面板目的地改 CityPicker 多选标签。单测 166→172。
- [x] **v0.48 起飞时刻全覆盖(参考班次提升)**: 240 张有价票中 116 张不显示起飞时间, 诊断发现其中 103 张(nearby-ref/国际日历行)的 alt_times 里已存真实班次时刻却从未提升到 dep_time, 另 13 张(斜杠中转串如 SC2114/SC2135 + 插值行)连参考班次都没挂。① core/sched_board.promote_alt_time 纯函数: 从 city_dep_times 列表选最优参考班次(同星期精确优先, 再按最早起飞), 提升 dep_src="alt-ref"; ② _attach_alt_times 对"有 alt 无 dep_time"的行直接提升(reenrich 离线回放同样生效), _enrich 斜杠段两段都查不到时回退挂同航线当日参考班次并提升; ③ 双 UI 新增“参考班次”琥珀徽标(标注非本航班号, 仅供参考), KPI 覆盖口径把 alt-ref 归入"参考"桶不冒充精确, time_coverage 归入 borrow 桶。实测离线回放: 缺起飞 116→0, 真实票覆盖 90/98→98/98(100%), 全程零新增网络请求。单测 172→174。

- [x] **v0.49 返程起飞时刻对称覆盖**: 去程 alt-ref 提升只服务 outbound, 往返模式切回程(return_deals)依旧 --:--。① sched_board.city_dep_times 泛化为 _ref_deps 共享内核, 新增 city_return_dep_times 直接读到达板 preschtime(=外地→杭州起飞时刻), 零新增请求; ② _attach_alt_times 增加 from_city 返程模式, _enrich_flight_times 增加 direction="ret" 使城市敏感查询(板库/时刻/斜杠回退/无号行)全部改走返程口径(leg_from/leg_to/leg_fi/leg_ti 反转); ③ reenrich 离线回放覆盖 raw_ret 块, TIME_FIELDS 写回+变更检测同步生效。快照当前 4 路线全 oneway(return_deals 为空)属前瞻性覆盖——切往返后返程同样具备时刻提升能力。单测 174→176, acceptance 13/13。

- [x] **v0.50 公务舱监控自动反采(镜像腿)**: "出发地历史最低公务舱价+目的地默认杭州可改+定时刷新"在 v0.42~v0.47 已成型, 但存量路线全是"杭州→外地"方向, to_cities=[杭州] 时一条都不匹配——此前必须手动添加反向路线才会真正采集。① cabin_leg 纯函数: 路线 to_city 被监控→直采本腿, from_city 被监控→自动派生镜像腿(外地→杭州), watch_from_cities 按监控腿自身出发城市过滤; ② 采集块 direction=out 独占(顺带修复往返模式下 ret 调用会采错方向的历史问题), 镜像腿换 IATA 对调后 fetch_cabin_offers(购票链接自动指向正确方向), 镜像行经 cabin_out 独立通道回传——绝不混入经济舱 deals(不污染 cheapest/告警口径); ③ 历史记录键 "<id>-rev" 与经济舱路线 id 不冲突, 提醒文案用监控腿城市("公务舱低价 重庆到杭州"); ④ /api/cabin qualifying_routes 改报真实监控腿+mirror 标记, CabinCard 加"镜像"徽标; ⑤ 实测开启后存量 4 路线自动派生 重庆/郑州/曼谷/成都→杭州 四条镜像采集腿。单测 176→179, acceptance 13/13。

- [x] **v0.51 部署对齐: worker 代码版本热替换**: 修复"页面反复看不到起飞时间"的真根因——旧 worker 进程(PID 15300, 早于 v0.48 启动)一直活着, autostart 只在无 loop 时拉起、revive 只救死 loop, 升级永远传不到活进程, 每轮用旧逻辑覆盖快照(293 有价票 110 缺起飞)。① core/version.py 单一版本源, worker 心跳盖章 code_ver, /api/health 暴露 code_synced; ② revive 守护每轮先比心跳版本(文件比对零成本), 落后即热替换 kill+relaunch(30 分钟冷却+心跳时间戳守卫防误杀长首轮), supervisor 快照记录 last_stale_restart; ③ 数据源页心跳卡"Worker 代码落后"琥珀警告+已热替换 vX→vY 提示; ④ tools/restart_worker.ps1/restart_all.ps1 一键强杀重拉(部署后必跑); ⑤ 实测 restart_all 后 code_synced=true, 缺起飞 110→0。单测 179→188, acceptance 13/13。

- [x] **v0.52 公务舱历史新低提醒**: "出发地历史最低公务舱价"此前只对照固定阈值——创了历史新低但仍在阈值上方时不会提醒。① record_low 记账时打 record 标(首样本不算, 防引导期全量误报), 携带前低 record_prev; ② record_alert_candidate 纯函数: 新低必须严格低于"已提醒过的最低价"才再提醒(alerted_low 持久化于 state.json, 同价重观测永不重复提醒); ③ main 提醒优先级: 历史新低 > 阈值命中, 文案"公务舱历史新低 重庆到杭州 · 10-02 ¥1650 (前低 ¥1800)", 若同时低于阈值追加标注; ④ cabin_watch.alert_record_low 开关(默认开, /api/config 校验+回显), CabinCard 编辑面板复选框, 表格历史最低列"新低"徽标(最近一轮创新低时), 最近提醒行显示提醒类型; ⑤ 实测 /api/cabin 回显 alert_record_low=true, 4 条镜像腿(重庆/郑州/曼谷/成都→杭州)在采。单测 188→192, acceptance 13/13。
- [x] **v0.53 手机局域网可达闭环**: iPhone 上看板+提醒此前卡在两处隐性知识——webui 默认绑 127.0.0.1(改 config+防火墙+重启三步手工), 手机上也不知道该输哪个地址。① /api/lan-info: 返回绑定 host/port、本机局域网 IP(UDP connect 探路由, 零发包)、lan_open 与拼好的手机 URL; ② PushView 手机访问卡: chip 展示"局域网已开放/仅本机可访问"+可直接抄的 URL, 未开放时提示一键脚本; ③ tools/enable_lan.ps1 一键开放(改绑定 0.0.0.0+防火墙规则+重启 webui, 打印手机地址), -Revert 一键收回; ④ PWA 已有(添加到主屏幕即 App 图标), Bark 推送不依赖页面在线。单测 192→195(lan-info 契约/开放拼 URL/仅本机隐藏 URL), ui_check v0.53×2, acceptance 13/13。
- [x] **v0.54 班期库浏览器**: 时刻库(3711 班号)是 alt-ref 参考起飞时刻的引擎, 但此前完全不可查——"为什么这天是参考班次""周三到底飞什么"无从回答。① /api/board: 按城市对(子串匹配)/航班号(大小写不敏感)检索班期库, 代表条目取跨 dow 众数起飞时刻(个别一天的时刻漂移不污染常态), 返回航司/机型/起降/班期 dow 列表, 按起飞时间排序, limit≤200; ② SourcesView 时刻库沉淀卡内嵌 BoardExplorer: 出发/到达城市输入+班期查询, 结果表格 7 个 dow 迷你徽标直观展示班期(周一~周日哪些飞), 命中数与空态引导; ③ .dow-mini 复用设计令牌(零硬编码色过 STRUCT 门禁)。单测 195→200(契约/城市过滤/排序/航班号检索/dow 排序/limit), ui_check v0.54×2, acceptance 13/13。
- [x] **v0.55 较昨日降价追踪+骤降提醒**: 阈值提醒的盲区——600→400 的大幅阴跌只要没破线就一直静默。① core/history.day_drops: 对比最近两个归档日的每路线窗口最低价, sharp 需同时过双闸(相对≥drop_pct% 且 绝对≥drop_abs 元), 旧测试小票面误报/低基数百分比误报都拦住; ② main.run_once 归档后即比价, 骤降即推送"骤降提醒 杭州到重庆: 窗口最低 ¥480 较昨日 -20.0% (¥-120)", state["_drop"] 按 route+date 去重防重跑重复提醒; ③ /api/drops 端点+配置 alert.drop_pct(默认15)/drop_abs(默认50, /api/config 校验); ④ 仪表盘最低价 KPI 加"较昨日 ▼¥120 (-20%)"涨跌徽标(降=绿/涨=琥珀), 数据一眼可感。单测 200→205(双闸/涨不算/新路线跳过/API 契约), ui_check v0.55×2, acceptance 13/13。
- [x] **v0.56 骤降提醒配置面板**: v0.55 的双闸参数此前只能手改 config.json, 推送页零入口。① PushView 新增"骤降提醒"卡: 降幅百分比/降幅金额两个数字输入(缺省回显 15%/¥50), alert 节点合并保存不覆盖 cooldown/top_n 等既有键; ② 实时预演——下方逐路线列出环比(前值→现值/Δ/百分比/升降配色), isSharp 用未保存的输入值客户端重算双闸, 每行 chip 即时显示"会提醒/未达双闸", 调参即刻看到效果而非等下轮; ③ 空态引导"归档两个查询日后显示逐日环比"。单测 205→209(默认填充/合法值直通/越界钳制/字符串数字容错), ui_check v0.56×1, acceptance 13/13。
- [x] **v0.57 周报「本周值得关注」**: 周报页此前只有逐路线环比卡, 缺跨路线速览层。① core/weekly.week_highlights 纯函数——从同一归档重算本周最大降幅(周窗口最低价 vs 上周)、双闸骤降(扫本周相邻归档日, 与 /api/drops 同口径 15%/¥50)、当前破线路线(最新快照 days_below), 输出结构化板块+可断言文本, 平稳周返回"本周价格平稳"; ② build_weekly 返回体新增 highlights, /api/weekly-report 自动透传(推送文案保守不动, 只做 API+UI); ③ WeeklyView 在总览卡与路线卡之间渲染「⭐ 本周值得关注」: 最大降幅行(前低→本周低/Δ/百分比)、破线行(窗口内 N 天≤阈值·最低价)、骤降行(日期+前值→现值)。单测 209→213(降幅/骤降/破线三态+空历史安全), ui_check v0.57×1, acceptance 13/13。
- [x] **v0.58 周报推送正文接入速览 + 推送预览**: v0.57 的「本周值得关注」只在网页端可见, 手机收到的周报正文仍是逐路线流水账。① core/weekly.push_text 纯函数——正文头部(📊 行下)插入 highlights 速览行, 平稳周也带安抚性结论, 无 highlights 原样透传, build_weekly 返回体新增 push_text 字段; ② worker 定时周报(main.py)与手动推送(webui /api/weekly-push)两个入口统一改走 push_text, 线上格式一致; ③ WeeklyView 新增「预览推送正文」按钮——展开即见手机实际收到的完整正文(头行+速览行+逐路线), 所见即所得再点推送。单测 213→218(头部插入/平稳周/无 highlights 透传/无头部前置/build_weekly 暴露), ui_check v0.58×1, acceptance 13/13。
- [x] **v0.59 公务舱监控运维闭环**: 监控已建成(v0.42 采集环形库/v0.47 多目的地/v0.50 镜像腿/v0.52 历史新低提醒), 但运维链路有三个断点——手动刷新接口 /api/run 无人调用、刷新间隔只展示不可改、Amadeus 密钥未配置时采集空转无提示。① CabinCard 新增「立即刷新」按钮, 打通 /api/run(trigger=manual)→刷新完成回显, 不再等 45 分钟下一轮; ② 编辑表单开放「刷新间隔(分钟)」字段, 随监控配置一并保存(写入 schedule.interval_minutes, 后端钳制 ≥5 分钟); ③ /api/cabin 新增 amadeus_ready 就绪标志, 卡片在启用+未配置密钥时显示琥珀色「公务舱数据源未配置」徽标, 空转不再静默。单测 218 全绿(既有 shape 测试增补 amadeus_ready 契约断言), ui_check v0.59×1。
- [x] **v0.60 提醒历史分类治理**: alerts.json 200 条记录全是 title='t' 手动测试噪音, 真实提醒(阈值/公务舱/骤降/周报/巡检)被淹没且无法区分。① core/notify.classify_alert 纯函数——按标题模式分类 test/weekly/cabin-record/cabin/drop/patrol/threshold/other, ≤2 字符标题直接判 test(无任何生产调用点会产出这么短的标题, 't'/'b' 垃圾一并归入); ② push_all 新增 kind 参数, 全部 8 个调用点(main.py×6/webui.py×2)显式传类, _record_alert 存档 kind(缺省回退 classify); ③ /api/alerts GET 给无 kind 的存量行回填分类+返回全量 counts; 新增 DELETE /api/alerts 只清 test 类行(其他类型原样保留); ④ PushView 提醒历史卡重做——7 个过滤 chips(全部/低价破线/公务舱[含新低]/骤降/周报/巡检/测试)带实时计数, 每行类型徽标, 「清理测试」按钮一键去噪(confirm 确认)。单测 218→222(classify 模式/存档 kind 双路径/API 回填+counts/DELETE 只清测试), ui_check v0.60×1。
- [x] **v0.61 多路线总览看板**: 路线一多, 跨线对比只能逐个点 route-tab 人肉翻。① 新组件 web/src/components/OverviewCard.jsx——聚合 snapshot 全部路线, 按 cheapest_total/threshold_total 比值升序(最接近/已破线的排最前, 无报价沉底), 行内含 城市对(单程→/往返⇄)/窗口最低价+日期/徽标(已破线 N 天[绿]·差 ¥X(+Y%)[灰]·暂无报价)/环比箭头(对接 /api/drops, ▼降▲升)/源异常 chip(flight_source_status 以 error 开头时提示); ② app.jsx 在 route-tabs 上方挂载, 点击行 setRouteId+清空 selDate 直达该路线仪表盘; rows<2 自动隐藏, 单路线零打扰; ③ app.css 新增 .ov-list/.ov-row(:hover/:current)/.ov-arrow 全走设计令牌零硬编码。ui_check v0.61×1(源码/构建产物/DOM 三层断言)。
- [x] **v0.62 公务舱历史低价榜**: 采集环形库早就在存每轮观察值, 但面板只报一个光秃秃的最低数——什么时候的票? 现在离记录还差多少? 都要人肉翻。① core/cabin_monitor.history_board 纯函数——逐监控腿聚合: 历史最低+所属乘机日期(low_date)/最新观察(latest, 按 ts 排序同日重写语义)/距新低差值(gap)/样本数, 无有效价的腿跳过, 按最低价升序(最优出发地领跑); ② /api/cabin 返回体新增 board 字段, 前端不再自行推导; ③ CabinCard 表格升级为「🏆 历史低价榜」——历史最低列带日期副标(如 10-05)+最近一轮新低徽标, 新增「最新」列(现价+距新低 +¥X), 走势 spark/样本/阈值状态保留, 旧后端快照走本地回退推导; ④ .cw-date 副标样式全令牌。单测 222→225(board 三态: 最低带日期+最新+gap 排序跳空腿/空历史安全), ui_check v0.62×1。
- [x] **v0.63 总览看板时刻+走势**: 起降时刻此前已覆盖明细卡/日历/TOP5/结论卡, 总览看板是最后一个只报价不报时刻的界面。① OverviewCard 每行新增 ov-times 副标——最优价航班的 起飞-落地 时刻(如 19:45-22:25), title 悬浮完整起降信息, 数据缺失时退化为仅起飞或整行隐藏; ② 新增 OvSpark 迷你走势线——60 天窗口全部有价日按日期序连成折线, 最低价点高亮圆点, 复用 cabin 卡 spark-line/spark-min 类两处视觉对齐, <2 个价点自动隐藏; ③ .ov-spark/.ov-times 样式全令牌(tabular-nums 对齐时刻数字)。ui_check v0.63×1(源码/dist/DOM 三层断言 ov-times)。
- [x] **v0.64 全局最优推荐**: 总览看板按行对比仍要用户自己扫一遍挑出到底该买哪班。① OverviewCard 顶部新增「🏆 全局最优」hero 行——rows 本就按 cheapest/threshold 比值升序, 队首即跨全部监控路线的性价比最高班, 行内含 城市对/最低价+日期/起降时刻(复用 ov-times)/距出发天数(客户端本地日历差)/破线或差距徽标; ② 点击 hero 直达该路线并选中该日期(onPick 扩展为 (id, date), app.jsx setSelDate(date) 直接打开当日详情), 普通行行为不变; ③ .ov-best/.ov-best-tag 绿系令牌(green-d/green-bg/card2)与破线语义同色。ui_check v0.64×1(源码/dist/DOM 三层断言 全局最优)。
- [x] **v0.65 周报推送全局最优行**: v0.64 的「全局最优」hero 只在网页总览可见, 手机端收到的周报正文仍是逐路线流水账, 唯一答案没有到达最终消费端。① core/weekly.global_best(snapshot) 纯函数——跨路线取 窗口最低价/心理价位 比值最小一班(最接近或已破线者优先, 同比值再比低价, 坏阈值/非数值价安全跳过), 返回城市对/日期/总价/起降时刻/阈值与差额; global_best_line(gb) 单行文案「🏆 全局最优 杭州→重庆 09-20 ¥380 (19:45-22:25) 比心理价低¥120」(超线时改报距心理价差额); ② attach_global_best(report, snapshot)——推送正文 📊 头行之后插入该行(已存在不重复插), 同时写 report['global_best'] 供 API 透出; ③ worker 定时周报(main.py)与 /api/weekly-report、/api/weekly-push 手动推送两个入口统一附加, /api/snapshot 顺带透出 global_best——服务端一处计算, 网页/手机/接口三端一致, 与 hero 行同规则(比值升序队首), 永不互相矛盾。单测 225→230(比值择优含时刻/坏数据返回 None/单行格式破线+超线/插入表头后且不重复/无 best 或无头行安全), ui_check v0.65×1(纯后端断言: 函数+双入口接线), 版本 0.65 四处盖章。
- [x] **v0.66 公务舱出发城市独立巡检**: 用户追加「出发地历史最低公务舱价提醒+目的地默认杭州可改+定时刷新」——v0.42~v0.62 已建齐环形库/多目的地/镜像腿/历史新低提醒/历史低价榜, 但出发城市仍只能从存量路线镜像推导, 想监控一条没有路线的出发地必须手动添加反向经济舱路线; 且公务舱数据只在整轮路线扫描时顺带刷新。① core/cabin_monitor.patrol_legs(cw, routes) 纯函数——watch_from_cities×to_cities 全叉积开独立监控腿, 自动剔除已由路线直采/镜像覆盖的城市对与同城对, 结果排序稳定; ② main.py 采集+告警内核抽取为 _cabin_absorb(路线腿与巡检腿共用同一历史键/冷却/推送语义), 新增 cabin_patrol_once——无 Amadeus 密钥/无巡检腿安全跳过并记录原因, 巡检腿历史键 patrol-<from>-<to>; ③ 定时双轨: run_once 每轮顺带巡检(手动刷新也覆盖), --loop 按 cabin_watch.refresh_minutes(默认30, 钳5-720)在两轮扫描之间独立补跑(睡眠切片≤60s, 无额外线程, state 写入保持单线程); ④ /api/cabin 新增 patrol 块(节奏/腿清单/上轮时间与状态), CabinCard 显示「独立巡检 每 N 分钟」+巡检腿 chips(区别于镜像徽标), 编辑表单开放独立巡检间隔。单测 230→237(叉积去重排序/路线覆盖剔除/禁用与空输入/同城对/refresh 默认与钳制/API patrol 契约), ui_check v0.66×1(核心函数+main 接线+webui 键+源码/dist 独立巡检断言), 版本 0.66 四处盖章。
- [x] **v0.67 灰色日期精点补全**: 用户判断「查不到飞行数据源的日期并非没票, 直接按日期精点查询能查到」——侦察实锤两个根因: ① offer 精点补全被 gap_dates[:6] 截断, 洞>6 时排位靠后的日期永远轮不到点查(饿死); ② qunar-intl 促销日历常只回 1-2 条尾部真实价, 头部日期距最近锚点>45 天超出参考价半径, 整段头空白。修复: ① _cached_fill_offers 改为轮转预算制——每轮只点查缓存缺失/过期的洞(≤6 个/轮), 负缓存即轮转游标, 后续洞自动轮入, 全窗口洞最终都会被逐日 flight-offers 精点(需 Amadeus 密钥), 新增 stats 出参(holes/probed/deferred); ② _fill_reference_deals 半径 45→75, 单一尾部锚点即可参考覆盖整个 60 天窗口(仍仅展示、不触发提醒/统计); ③ 数据源页 offer fill 步骤显示「缺N天·本轮点查M·待轮转K」。单测新增轮转跨批覆盖+参考价头部可达(30 文件全绿), ui_check v0.67 断言, 版本 0.67 四处盖章。
- [x] **v0.68 参考班次落地时间补全**: 用户痛点「航班只显示起飞时间、落地一直 --:--」——侦察实锤 dep_time 已 100% 覆盖, 真缺口是 arr_time(国际线 60/60 全缺, 国内 24~47/60 缺); 班期库 flight_sched_db.json(3711 班)的 dow 条目本就同时含 dep+arr, 但 _ref_deps 只透传 dep 把 arr 丢了。修复: ① sched_board._ref_deps 条目新增 arr 透传; ② promote_alt_time 校验并携带 arr(垃圾值置空); ③ main._attach_alt_times 拆 need_dep/need_arr——缺落地的行从提升的参考班次直接补 arr_time(arr_src=alt-ref, 不覆盖已有值), _flight_dict 序列化 alt_times 携带 arr; ④ DayDetail 参考班次 chip 显示「航班号 起飞→落地」。全程零请求零密钥, Amadeus 密钥接入后仍会升级为精查时刻。单测新增 arr 搭车+落地参考回填(15+55 全绿), ui_check v0.68 断言, 版本 0.68 四处盖章。
- [x] **v0.69 当日班期表 + 生产级部署**: 用户反馈「还是看不到航班班次的具体起飞时间」+「部署太轻量」。数据侧复核: 快照 240 行 miss_dep=0/miss_arr=0, DOM 零占位符——痛点实质是「只看得到最低价那一班」而非数据缺失。① 新增 /api/day-schedule?from&to&date 零密钥接口: 按城市对+星期列出班期库全部班次(no/dep→arr/exact 徽标, 出发杭州走离港板, 其余城市走到达板反查); ② DayDetail 详情卡内嵌「当日班期表 · N班」chips 条, 无报价日期也展示, 一次点击看全该日每个班次的起飞→落地; ③ webui 主进程从 Flask dev server 升级为 waitress 生产级 WSGI(8 线程, ImportError 优雅回退保持零依赖可启动); ④ Dockerfile+docker-compose.yml: python:3.13-slim, 数据/配置宿主机挂载, HEALTHCHECK 走 /api/health, 容器内监督线程同 Windows 模型自动拉起 worker。单测新增 day-schedule 契约 5 例(缺参 400/坏日期 400/去程含 arr/返程走到达板/未知城市对空而 ok), ui_check v0.69 断言, 版本 0.69 四处盖章。
- [x] **v0.70 班期直达 + 省% + CI**: ① 当日班期表每个班次 chip 升级为深链——dayListUrl 复用任意已有 deal url 模板替换 goDate(国际城市拼写以真实 deal 为准), 无 deal 时按城市名构造, 点击任一班次直达去哪儿当日航班列表; ② 全局最优卡破线 chip 从「已破线 ¥X」升级为「已破线 ¥X · 省 Y%」; ③ 新增 .github/workflows/ci.yml: ubuntu+windows 双平台跑全量单测与 compileall, web-build 任务 npm ci+build 验证前端可构建, docker-build 任务构建镜像验证 Dockerfile; README 顶部挂 CI 徽章并修正 CI 范围文案(单测+构建级, 完整 acceptance 仍本地)。
- [x] **v0.71 班期航司机型 + ghcr 镜像发布**: ① sched_board._ref_deps 透传 airline/craft(板库 v0.26 起每行就存 chinese_hs/jxzs, 组装参考列表时被丢弃, 同 v0.68 arr 修法), /api/day-schedule rows 与 alt_times 序列化同步带出; ② DayDetail 班期表/参考班次 chip 追加机型弱化标注 .ft-alt-craft, 悬浮 title 显示「航司 机型」; ③ CI 新增 docker-publish 任务: push master 自动构建并发布 ghcr.io/ashleymao523/fare-alert:latest 与 :sha 双标签——任意设备只需 Docker + docker-compose.yml 即 pull 迁移, 无需本地构建工具链。新增单测 test_airline_craft_ride_along(透传 + 旧库无字段回退空串), ui_check v0.71 断言, 版本 0.71 四处盖章。
- [x] **v0.72 当日班期 24 小时时间线**: 回应早期反馈「没有 24 小时计时的时间线」——DayDetail 班期区升级双层: 上层 .tl-rail 时间线(0-24h 横轴, 3h 细刻度/6h 主刻度, 每班起飞时刻百分比落位打点, 当日班期实心/跨日参考空心, 上下双车道避让, hover 放大), 打点即深链直达去哪儿当日列表, 悬浮显示班次/起降/航司/机型; 下层保留完整 chips 列表, 分布与明细互补。纯前端复用 /api/day-schedule, 零新增请求; CSS 全设计令牌零硬编码色值。ui_check v0.72 断言, 版本 0.72 四处盖章。
- [x] **v0.73 当日班期全量 + 经停标注**: 数据侦察实锤——杭州-成都单航线去重后 25-27 班/天, 而 /api/day-schedule 沿用 limit=12 只出一半班次; 板库 3716 条 dow 记录中 1008 条带经停信息(via/via_arr), 管道源头同样丢弃。① sched_board._ref_deps 透传 via(经停)字段, limit=None 时返回全量去重列表(默认 limit=4 行为不变); ② /api/day-schedule 改 limit=None 全量取, 响应新增 total/has_more(>30), rows 截前 30 条防超大响应; ③ main._flight_dict 与 core/reenrich 的 alt_times 序列化同步透传 via(三处同步, 幂等检测不误报); ④ DayDetail 班期标签改用 sched.total 计数, 时间线打点/班期 chip title 追加「经停X」, 无落地但带 via 的 chip 正文弱化标注经停, has_more 时追加「+另有N班」直达深链。单测新增 via 透传+全量 limit 与 day-schedule total/via 契约, ui_check v0.73 断言, 版本 0.73 四处盖章。
- [x] **v0.74 班次历时 + tag 发布链路**: ① core/sched_board.flight_duration 纯函数——真实起降时刻直接换算「2h45m」历时(落地早于起飞按跨零点 +1 天), 缺任一时刻/经停行(无最终落地)返回空串绝不编造; /api/day-schedule rows 新增 dur 字段; ② DayDetail 班期 chip 追加历时弱化标注, 时间线打点/芯片 title 加「历时X」, 与动车侧历时列对齐; ③ CI 加 tag 触发: 推 v* tag 自动发 GitHub Release(generate_release_notes) + docker 镜像追加 :vX.Y 版本标签(latest/sha 保留); ④ 新增 tools/upgrade.ps1 一键升级(git pull → npm build → restart_all)。复探归档: 机场板 API 的 GET/POST 日期参数与路径段全被忽略(v0.35 负结论互证), dow 覆盖唯一路径仍是每日运行自然沉淀。单测新增历时矩阵与 day-schedule dur 契约, ui_check v0.74 断言, 版本 0.74 四处盖章。
- [x] **v0.75 起降区间时间线 + 精确历时回填 + 每日自动备份**: ① 时间线从「起飞单点」升级为「起飞→落地」起降区间条(.tl-span): 有落地时刻的班次渲染区间条(红眼航班画到 24:00 且 title 标「次日到达」, 最短 0.6% 保证可点), 无落地(经停行/缺数据)保留原打点; ② main._attach_alt_times 新增精确历时回填——起降时刻都真实且 dur 为空或带「(估)」时, 用 sched_board.flight_duration_hm 的精确值替换估算(估算仅落地缺时按大圆生成); ③ 新增 core/auto_backup: 每日首轮调度前自动 zip 备份 config+data(标记 data/auto_backup.json 防重, 保留最近 7 份, 异常只记状态不抛出), run_once 接线, /api/health 暴露 backup{count,last,last_ts}; 长期部署设备升级/误删不再丢班期库。单测新增 test_auto_backup(created/skip/保留7份)与 flight_duration_hm 元组断言, ui_check v0.75 断言, 版本 0.75 四处盖章。

- [x] **v0.76 PWA 补全 + 部署自检 doctor + 精点补查通道**: ① v2 界面补全 PWA(manifest.webmanifest + apple-touch-icon, iPhone「添加到主屏」即得图标+全屏运行); ② 新增 tools/doctor.py 部署自检——本机模式体检 webui/快照/worker/代码同步/班期库/备份/推送/间隔红线/dist 构建产物/PWA 共 10 项, --url 模式支持局域网远程设备(仅 API 检查), PASS/WARN/FAIL 三级, exit code 可接 uptime 包装; ③ 灰色「查价日」问题实证收案: qunar 低价日历这些日期服务端即无缓存价(快照与线上一致, 非无票非 bug), 按日精点 API(touchInner/touchInter) 被 Bella 签名+浏览器指纹风控挡死(直调/无头/内嵌真实浏览器三途径全 1999, 证据存档 tools/point_probe.py); ④ 双轨补全方案落地——track A: Amadeus 按日 offers(代码就绪, 密钥未配), track B: 新增 core/point_fill 精点缓存模块(真实浏览器抓到价 POST /api/point-fill, TTL 48h, 每轮爬取重放覆盖 interp/nearby-ref 参考价行, 真实行永不覆盖), GET /api/point-gaps 列出待补日期, POST 后快照热补立即生效。单测新增 test_point_fill(7 用例: 落盘/TTL/真实行保护/热补/缺口窗口)与 test_doctor(24 断言三级矩阵), ui_check v0.76 断言, 版本 0.76 四处盖章。

- [x] **v0.77 全功能容器 + 借班透明化 + 部署指南**: ① Docker 镜像升级为全功能单容器——新入口 run_all.py 同容器监督 webui + worker 循环(子进程崩溃 3s 自动重生, 日志合并进 docker logs), FA_ROLE=all|webui|worker 可选角色; 旧镜像只跑 webui 无爬虫, 容器部署下班期库永不沉淀、时刻永远靠借——这正是「页面总是没有起飞时间」的部署侧根因; ② 跨 dow 借用时刻透明化——board_lookup_x 借用分支返回拷贝并标记 borrow_dow(源星期几), FlightDeal/序列化/前端全链路透传, 徽标从模糊的「跨日参考」细化为「借周三参考」, title 说明沉淀满 7 天后自动升级「班期精查」; ③ doctor 新增 check_deploy 部署形态检测(容器 FA_ROLE 不含 worker 时 WARN 提示班期库不会沉淀); ④ 新增 docs/部署指南.md——Windows 本机常驻/Docker 全功能(NAS/旧机/树莓派)/局域网+PWA+iPhone Bark 三形态、数据迁移、班期沉淀机制(每天存 2 个 dow, 常驻 7 天=7/7 全覆盖)一页讲清。单测新增 test_run_all(9 断言角色矩阵)与 test_sched_board borrow_dow 2 用例(借用标记+库不被污染+exact 无标记), test_doctor 补 deploy 断言, ui_check v0.77 断言, 版本 0.77 四处盖章。

- [x] **v0.78 精点补查 UI + 时刻沉淀透明卡**: ① 运维页新增「精点补查 · 缺价日期回填」卡——GET /api/point-gaps 按路线列出聚合日历未出价的日期(已回填绿 chip), 点击 chip 展开回填表单并附去哪儿单日精查直达链接(与日详情同款 deep link), 填「最终付款价(含税)+航班号+起降时刻(选填)」POST /api/point-fill 后快照热更新, 卡内明示口径(自动扣机建+燃油/缓存 48h/真实源优先); ② 新增「时刻沉淀 · 按路线透明度」卡——各路线起飞时刻精确/借用双色占比条(snapshot time_coverage), 七星期班期覆盖格 + 缺口自动补齐预测(板库每轮沉淀当日+次日, 周三/周日何时长满直接给日期)。验证: ui_check v0.78 断言(精点补查/nextRunForDow/两 api helper 源码+dist), 版本 0.78 四处盖章。

- [x] **v0.79 精点回填书签 + 开机自启体检**: ① 运维页「精点补查」卡新增书签脚本区块——GET /api/bookmarklet 生成绑定当前面板地址的 bookmarklet(手机从局域网 URL 生成即指向台式机), 添加到收藏栏后在去哪儿精查页点击, 从渲染 DOM 挖最低价(¥ 2-5 位 + 50-99999 过滤, 尽力抓航班号/起降时刻), no-cors text/plain POST 回填, 抓不到价弹窗手输, 页角 toast 反馈结果; ② /api/point-fill 支持 from_city/to_city 城市对自动解析 route_id(bookmarklet 只知城市名), 歧义/未知返回 400; ③ doctor 新增 check_autostart——Windows HKCU Run + 计划任务双路探测 webui/worker 自启是否齐装, 未装/不完整 WARN 并给安装命令, 重启存活从「口头相信」变成可验证。验证: 新增 test_bookmarklet(生成器形状/origin 注入/城市对解析 200+400/端点契约), test_doctor +autostart 断言, ui_check v0.79 断言, 版本 0.79 四处盖章。
- [x] **v0.80 反向缓存榜 + 借班转正预告 + compose 健康检查**: ① 「预算找目的地」页新增 GET /api/reverse-latest——纯读 6 小时 reverse 缓存(零网络请求), 按 含税总价 升序回最近扫描命中线路(城市/日期/航班号/航司/裸价/直达链接/新鲜度), 前端首屏即渲染「最近扫描 · 命中 N 条线路」卡片榜, 该 tab 从空表单变成默认有内容; ② time_coverage 新增 promote_on/promote_dow——对每条借班行按 borrow_dow 推「该星期几的下一个日历日」, 取最早者, 时刻覆盖 KPI 直接显示「MM/DD 起借班转精查」, 把「为什么是参考时刻」变成带截止日的透明承诺; ③ docker-compose 补 healthcheck 声明(与镜像内置双保险), unhealthy 容器触发 unless-stopped 重启。验证: test_time_coverage +3(下个周日/最早 dow/无借班), 新增 test_reverse_latest(排序/税口径/字段/空缓存), ui_check v0.80 断言, 版本 0.80 四处盖章。
- [x] **v0.81 时刻覆盖条 + 逐日矩阵 API + 每日巡检**: ① 仪表盘日历卡片新增 TimeStrip——60 格逐日时刻质量热力条(绿=板库真实/蓝=跨周借班/金=邻近参考/灰=无价格), 悬停显示该日航班号+起降时刻, 借班格附转精查日期, 图例区实时汇总四类计数并预告「周X MM/DD 板库轮询补齐」; ② 新增 GET /api/time-coverage——把快照逐 deal 展开成逐日 kind 矩阵, 同时从班期库 dow 直方图推导 heal 自愈预告(缺失星期几的下一个日历日), 前端一次拉取全线路复用; ③ 新增 .github/workflows/daily-check.yml——每天 09:30 定时跑全套测试+前端构建(部署分量: 仓库不只在 push 时过 CI, 而是每天自证一次, 依赖漂移/API 变化一天内暴露)。验证: 新增 test_time_coverage_api(形状/计数/heal/借班不虚诺), /v2 DOM 断言 tstrip 渲染, 版本 0.81 四处盖章。

- [x] **v0.82 精点直达一键化 + 自启落装(MSIX 注册表遮蔽攻关)**: ① 运维页「精点补查」缺价 chip 从「点选中再找链接」升级为 anchor 直达——一点即开去哪儿单日精查页(新标签)并同步选中回填表单, 未回填 chip 一律带 ↗, 已回填 chip 保持绿态提示有效期与让位规则; ② 回填面板每 20 秒自动重拉 /api/point-gaps——书签是 no-cors fire-and-forget 无法回调面板, 轮询让「点书签 → 面板变绿」无需手动刷新; ③ 本机自启真正落装并查清一例疑难: 安装脚本写的 HKCU Run 项在真实注册表里(reg.exe 可证), 但本机日常 python 是 Microsoft Store MSIX 版——MSIX 注册表虚拟化把 HKCU Run 的读遮蔽/写拒绝, doctor 因此假阴性。新增 tools/install_autostart.py: 在用户 Startup 文件夹(shell:startup)落一个 FareAlertStartup.cmd(文件系统不受 MSIX 遮蔽, 双包装器幂等自守不重复拉起), doctor.check_autostart 增加 Startup 文件夹探测并在检出 MSIX 时注明「Run 项以此为准」, 本机 verdict 回到 0 FAIL(worker 与 webui 同版 0.82, 班期库照常沉淀, 9-16/9-20 自愈节点不依赖手动拉起)。验证: ui_check 新增 v0.82 断言(anchor 直达/20s 轮询/启动文件夹探测/MSIX 注记), 版本 0.82 四处盖章。

## 常见问题

- **机票起降时刻从哪来?** 去哪儿低价日历只返回每日最低价+航班号(列表页需签名,按合规原则不破解)。v0.18 起杭州相关线路自动用机场官网公开班期板按「航班号+星期几」沉淀计划时刻(零密钥);v0.19 起目标星期未沉淀时自动借用同号航班其他班期时刻(跨日班期·参考),仅有起飞时落地按大圆估算(~ 前缀);配置 Amadeus 后优先实时刻。车次时刻/历时来自 12306, 原生即有。

- **为什么按"总价"而不是裸价判定?** 你下单付的就是裸价+机建+燃油,以最终支付口径对比心理价位才有意义。
- **和 OTA 券后价有偏差?** 日历接口是挂牌价,不含平台券;偏差通常几十元内,收到提醒后点进下单页看券后实付即可。
- **学生票准吗?** 12306 查询接口不区分学生价,这里按 动车二等座75折/硬座5折/硬卧=卧铺-硬座半价 估算(略偏低),优惠区间/资格以下单页为准。
- **推送没收到?** 先在 Web UI 点"发送测试推送";Bark 确认 Key 正确、通知权限开启;Windows 计划任务看"日志"页排查。

## 开发与验收

每轮改动(无论人还是 AI)都必须走同一条验收流水线,全绿才算完成:

```powershell
python tools/acceptance.py
```

- 门禁覆盖 G0 静态检查 / G1 单测 / G2 API 契约 / G3 DOM 断言 / G4-G6 红线(提醒、隐私、估算价)。
- 人机协作守则见 [AGENTS.md](AGENTS.md),逐条门禁定义见 [docs/验收规范.md](docs/验收规范.md),里程碑与 DoD 见 [docs/迭代路线图.md](docs/迭代路线图.md),API 契约见 [docs/API.md](docs/API.md)。
本仓库已接入 GitHub Actions CI(push/PR 自动跑双平台单测 + 前端构建 + Docker 镜像构建);完整 acceptance 门禁(含运行中面板的 API/DOM 契约)仍在本地执行,本地全绿 + CI 全绿才可合入。

- [x] **v0.83 精查回填养板库 + 公务舱监控去 Amadeus 依赖**: ① point-fill 回填行新增舱位标签与城市对, 带航班号+时刻的行同时落入 sched_deposit 队列, worker 每轮 update_sched_db 吸收进持久班期库(按行自身星期分桶, 板库已有行不被覆盖)——班期接口只返回"当日+次日", 周日这类空洞板库自身永远抓不到, 现在用户在精查页点开任意周日航班回填即可即点即补, 起飞时刻显示的最大空洞类从根上可治; ② 公务舱监控原先绑死 Amadeus flight-offers(无密钥=每 30 分钟空转 skip), 现在 /api/bookmarklet 支持 ?cabin=business 生成舱位书签, 舱位筛选页抓到的行带 cabin 标签进 point 缓存, cabin_patrol_once 无密钥时走 absorb_point_cabin 通道——同一套环形历史+历史新低告警无 key 存活, skip 文案改为可执行的 standby 指引; ③ doctor 板库检查对缺失星期具名(如"缺周日")并给出双自愈路径(该星期几运行日自动补 / 精查书签回填立即补)。新增 6 项单测(put_rows 舱位字段、deposit 队列过滤追加、absorb_deposit 补 dow/不覆盖板库行/幂等、absorb_point_cabin 分组过滤 TTL)。

- [x] **v0.84 借班一致性投票 + reenrich 标签修复 + api_push 常备通道**: ① 跨 dow 借班此前"任取一个 dow 的时刻"无一致性校验, 不同星期执行同一航班时刻有偏差时会静默借错——board_lookup_x 借用分支升级众数投票: ≥2 个 dow 同 dep 时刻 → 借该一致时刻并带 borrow_votes 票数(证据越足越可信); 多 dow 分歧无众数 → borrow_unstable=True, DayDetail 徽标三态化(分歧警示?/票数一致 N 票原文案/单候选不标分歧); 单候选视为证据薄而非分歧, 诚实区分"不确定"与"证据少"两种状态; ② v0.77 遗留 bug 修复——reenrich 重查时刻时不回写 borrow_dow/borrow_votes/borrow_unstable 三键, 精确命中后旧借用标签残留造成"来源失真", 现在 TIME_FIELDS 三键齐清, 重查后标签与真实来源一致; ③ 新增 tools/api_push.py 正式推送工具(参数化 TAG, OLD=origin/master 自动推导, worktree clean 门禁, credential fill 取 token, 本地 annotated tag 解析重建)——github.com:443 不通而 api.github.com 可达的环境从此一条命令完成 commit+tag 推送, v0.83 推送三坑(循环步进/短 sha/TAG 未展开)全部内置修复。验证: TestBorrowConsensus 4 用例(众数+votes+库纯净/分歧 unstable/单候选不 unstable/exact 无投票键), 全套 271 单测绿。

- [x] **v0.85 推送带上起飞时刻 + 可信度标记**: 手机端最需要时刻的三个触点全部补齐——① 阈值提醒标题带可信起降窗口(exact 或 ≥2 票一致才上标题, 单 dow 借用/分歧时刻只留在正文带标记, 不在锁屏冒充事实); ② 提醒正文逐航班行插入 "07:45-10:20(3票)" 式窗口+可信度——exact 无标记 / 跨 dow 一致 N票 / 单 dow 借用或 alt 参考"参考" / dow 分歧"⚠", 无时刻不加噪; ③ 周报全局最优行同步同一套标记 "(19:45-22:25·3票)"; 实现上 core/alerts 新增 dep_arr_text/conf_mark 双态助手(FlightDeal 属性与快照 dict 同一实现), 周报与阈值提醒共享; global_best 提取器补齐 borrow 三键。新增 tests/test_alert_msg.py 10 用例(窗口三态/五种来源标记/dict 形态/标题门控/正文标记/周报三态), 全套 281 单测绿。

- [x] **v0.86 迁移包完整性升级 + Web 一键导出导入**: 「部署分量」与跨设备迁移收口——① v0.41 的备份清单落后于数据演进: history.json(周报/骤降历史)、cabin_history.json(公务舱环形库)、point_fill_cache.json(精点回填缓存)、sched_deposit.json(养板队列)统统不在包里, 迁到新设备会静默丢四大耐久状态, 全部补回 ITEMS; ② 迁移包带 bundle_manifest.json(format/code_ver/逐成员 sha256), restore 先验签再落盘——传输损坏或被改动的包直接拒收(--force 可强行, 自担风险), v0.41 无封条的旧包仍兼容; ③ 导入前自动落 pre-restore-safety-*.zip 安全备份, 坏导入本身一条命令可回滚; ④ 新增 GET /api/bundle/export(浏览器直接下载迁移包, 手机/Mac 无需 SSH)与 POST /api/bundle/import(sha256 校验→安全备份→恢复, 篡改包 409), 运维页新增「📦 备份与迁移」卡片。新增 9 项单测(清单回归/封条覆盖全部成员/篡改拒收/旧包兼容/manifest 不落盘/安全备份/导出流 PK 头/探针往返/非 zip 拒收), 全套 290 单测绿。
- [x] **v0.87 灰点自动补价: Booking 无 key 交叉源(国内+国际)**: 用户点破的关键观察——灰色日期"直接精点其实查得到价"。实证定位: 去哪儿日历网关对 365 天每天都返回行, 但 ~320 行 price 为空(服务端尚未生成缓存底价), 抓取端 if not p: continue 把它们丢成灰点; 逐日列表接口仍被 Bella 签名门禁(v0.76 结论未变)。解法是换攻击面: flights.booking.com/api/flights/LOWEST_PRICE 公开无 key, 3-5 秒一次返回真实可购最低价(含最便宜航司与航班数), 国内国际灰点日期通吃。① 新增 core/booking_fill.py——近日期优先的预算轮询(每轮最多 6 个, 同 v0.67 amadeus 模式), 正缓存 48h/负缓存 24h(兼作轮换游标), 间隔 ≥4s, EUR→CNY 汇率可配(booking_fill.fx_eur_cny, 默认 7.8); ② main.py 国内路径三个 amadeus 短路口(未配密钥/无 IATA/最终返回)与国际路径(promo 之后此前完全没有 offer 级补全)全部接入 _booking_cross_fill——无 Amadeus 密钥的开源部署从此也有自动补价; ③ 口径诚实: booking-ref 加入 NON_REAL_SOURCES(flights/history 双份+前端 cheapestFlight/isRefDeal 同步)——真实报价但属国际渠道参考价, 通常高于国内 OTA, 只展示不触发阈值提醒/不进 KPI/不进历史最低/不作为插值锚; 精点回填(point-fill)可覆盖 booking-ref 行, 去哪儿日历生成缓存价后真实行自然接管; ④ UI: DayDetail「Booking参考」徽标(悬停说明口径), 数据源页新增可开关的 Booking 源(default-on 语义修复: enabled 键缺失不再显示为关闭), 爬取流水 booking-fill 步骤打点。端到端实测: 杭州-重庆 2026-10-14 补到 ¥1238(厦航 MF, 208 班), 偶发失败日期进负缓存次日自动重试。新增 4 项单测(响应解析/预算轮询+缓存回放/仅补缺失日期/NON_REAL 语义+精点让位), 全套 294 单测绿。

- [x] **v0.88 Booking 完整行程: 灰点直出精确时刻 + 偶发失败负缓存分级**: 用户连续点破两个问题——①"精点能查到数据的日期在聚合页是灰的"②"航班起降时刻缺失"。实证定位: ① v0.87 的负缓存不区分"服务端明确无报价(200 且无 minPrice)"和"偶发调用失败(限流/超时/5xx)", 一次 unlucky 调用把日期锁 24h, 而 live 复测证明这些日期大多有价(杭州-重庆 2026-10-13 实测 163.2 EUR 可查); ② LOWEST_PRICE 响应本就携带 flightOffers[15] 完整报价——segments 精确起降 ISO 时刻、marketingCarrier+flightNumber 航班号、totalTime 历时、多段=中转/多leg=经停、planeType 机型、travellerCheckedLuggage 真实托运额度, v0.87 只读了 aggregation.minPrice 把行程全扔了。修复: ① fetch_lowest 对 200 无报价返回 no_data 语义, 负缓存分两级——err(网络类)90 分钟重试、nodata(服务端确认)12 小时, 旧无 kind 负缓存自动按 err 迁移重探, "精点可查"的日期数分钟内自愈; ② 新增 offer_itinerary 解析——灰点 booking-ref 行直出航班号/精确起降/历时/中转/机型/真实托运(dep_src=booking), FlightDeal 增 baggage_note 字段透出到 UI; ③ 新增 attach_times: 有真实价但缺精确起飞的日期, 用同日 Booking 行程钉参考时刻(dep_src=booking-x, 只升级缺失/借班行, amadeus/airport-board/alt-ref 权威保留, 价格与航班号身份不动); ④ main._booking_cross_fill 补完 time_gaps 探测+attach 接线(顺带修复上轮遗留的 docstring 断裂语法错误), _flight_dict 透出真实托运; ⑤ UI: DayDetail 新增「Booking精确」「Booking同日参考」时刻徽标(悬停说明口径), Kpis 时刻覆盖 KPI 排除 booking-ref 行与 booking-x 参考时刻(口径与 alt-ref 对齐)。单测 4→10(fetch no_data/error 语义/负缓存 TTL 分级+旧缓存迁移/err 写回/offer 字段解析/extra_dates 只写缓存后 attach/attach 覆盖策略), 全套 300 单测绿。

- [x] **v0.89 当日实测班次时刻表 + systemd 裸机部署**: 用户核心痛点「页面总是无法显示航班班次的具体起飞时间」的第三层根治——v0.88 只取 Booking 最便宜一班, 但响应本带 ~15 个完整报价(不同航班各带精确时刻)。① core/booking_fill.offer_list: 全班次解析(航班号去重、按起飞排序、含历时/机型/经停), 缓存条目新增 offers 键; ② 灰点行(booking-ref)的 alt_times 直接挂当日实测班次列表(exact+src=booking), 详情卡新增「当日实测班次·N班」区——该日真实可购航班的精确起飞→落地, 非星期推断; ③ 真实价行被钉 booking-x 参考时刻的同时也挂上实测班次列表(alt_times 原为空时), _attach_alt_times 不覆盖已有值所以口径稳定; ④ webui /api/day-schedule 叠加 Booking 实测: 同号航班的当日实测时刻优先于板库星期推断, 板库没有的航班补充进列表, 24小时时间线的 tip 标注「Booking当日实测」; ⑤ 部署升级: 新增 deploy/systemd/(fare-alert.service + install.sh 一键装, 崩溃15s自动拉起)与 deploy/README.md(Docker/NAS/树莓派/Windows 三形态部署指南)。单测 10→12(offer_list 解析去重排序/offers 优先挂载+attach 班次列表断言)。
- [x] **v0.90 遗留缓存实测班次升级轮转**: v0.89 的实测班次覆盖停在 48/240 不再增长——根因是 v0.89 之前写入的 159 个旧正缓存日期只带单班次时刻(dep 有、offers 无), fill_gaps 视为“完整”永久跳过。① 跳过条件收紧为 dep+offers 双全, 无 offers 的旧正缓存重新进入探测轮转(仍受 max_per_cycle 预算节流), 逐轮升级为当日全班次时刻表; ② 升级探测失败保留原参考价(deferred 下轮重试), 绝不把已有正缓存覆盖成负缓存; ③ attach_times 用缓存实测 offers 覆盖无来源标记的板库参考 alts(同日实测 > 星期推断), 已带 booking src 的不重复覆盖。单测 12→15(旧正缓存重探升级/升级失败保价/无源 alts 覆盖)。

- [x] **v0.91 实测班次覆盖监控可见化**: v0.90 的升级轮转在后台静默跑, 用户只能等覆盖慢慢变多。本版把进度变成指标: ① core/booking_fill.coverage_stats 统计新鲜正缓存/已带实测班次/待升级天数/百分比(负缓存与过期条目剔除, 异常桶不崩); ② /api/health 新增 timetable 块, 部署盒子/外部 uptime 监控可直接拉取; ③ 前端“数据源”页调度心跳卡新增覆盖进度条(百分比 + 剩余天数提示, 覆盖完成显示✔)。单测 15→16(混合缓存计数)。

- [x] **v0.92 实测班次直达购票+低价班标记**: 详情卡「当日实测班次」区的每班从纯文本升级为可点链接——点击任意实测班次直达去哪儿当日航班列表购票(原来只有 24h 时间线的点可点); 当日 OTA 最低价航班(deal.flight_no)若在实测列表中, 该班 chip 加绿色「低价」角标高亮——价格、精确起降时刻、购票链接三位一体(匹配不上则不硬造标记); 链接 chip 无下划线、hover 提亮边框, 与既有设计令牌风格一致。
- [x] **v0.93 灰点反饥饿根治**: 用户点破「聚合日历查不到的日期, 精点直查其实有价」——实证定位为三重叠加死锁: ①v0.87 僵尸 worker(升级后进程未换, 16:06 才被 restart 接替)给郑州/成都写了只有 cny 无 dep/offers 的 4 键缓存条目; ②v0.88 起回放门槛收紧为 dep+offers 双全, 4 键条目永远不回放, 快照重建后退回灰点; ③v0.90 升级轮转本该救它们, 但 targets 把灰点日期与时刻升级日期混合排序, 每轮 6 个探测预算被近端 time-gaps 吃光, 远端灰点永久饥饿(live 实证: 单独喂杭州-重庆 6 个灰点日期 6/6 立即探测成功)。修法两刀: fix A 灰点日期在探测队列绝对优先于时刻升级(组内仍近日期优先); fix B 僵尸 4 键条目(连 dep 键都没有)在灰点日期直接回放参考价——真实 GDS 参考价远比 interp 合成行可信, 时刻由升级轮转后补; 探测失败也回放旧价兜底并刷新 ts 获得 48h 冷却(防每轮重试风暴)。带 dep 无 offers 的 v0.89 条目保留 v0.90 升级语义不受影响。线上验证: 杭州-重庆 11-05~11-12 六个灰点全部转为 booking-ref 行(¥1738-2520, 带精确时刻+6 班当日时刻表), 郑州/曼谷 10-28 同步自愈; 郑州 11-03~05/成都 11-01~06 的僵尸条目与曼谷 11 月未探测日期由新预算顺序按轮自动补齐。单测 18 用例全绿(新增僵尸回放/预算优先级 2 例, 失败兜底断言升级), 版本 0.93 五处盖章。
- [x] **v0.94 逐班参考价**: 详情卡「当日实测班次」此前只显示每班的时刻/机型, 价格只有一个日期地板价——用户无法直接对比 3U2581 与 GJ8827 哪班便宜。live 探测实证 LOWEST_PRICE 的 flightOffers 里每个 offer 都带 priceBreakdown.total(units+nanos, EUR 含税总价, 与 aggregation.minPrice 同构), 且 offers 本身按价格升序。链路: offer_list 解析 price_eur(非 EUR/缺字段兼容为 0) → 缓存 offers 自动带上 → _deal_from/attach_times 的 alt_times 按 fx(booking_fill.fx_eur_cny, 默认 7.8)折算出 price(CNY) → /api/snapshot alt_times 透出 → DayDetail.jsx 实测班次 chip 显示「¥参考价」+ title 提示。旧缓存 offers 无 price_eur 不显示价格(不报错), 升级轮转 48h 内自然带上; 参考价为 GDS 国际渠道 EUR 折算, 通常高于国内 OTA 实付, 仅展示不进提醒/KPI。单测 19 用例全绿(price 解析/无价兼容/fx 折算/attach 透传 4 处断言新增), 版本 0.94 五处盖章。
- [x] **v0.95 逐班价全量回填 + 部署自愈加固**: 两处收尾。① 回填工具化——v0.94 的逐班价只有新探测的日期才有, 存量 240 条缓存要等 48h TTL 过期后按 6/轮慢慢轮转(约 2 天才能全部带价); 新增 core.backfill_prices + `tools/backfill_offer_prices.py` CLI: 跳过已带价/负缓存条目(负缓存 TTL 语义不动), 失败探测绝不覆盖正条目, 每 10 条做一次 entry 级磁盘合并保存(reload 磁盘再覆盖 touched 条目, 与并发 worker 轮次互不丢写), >=4s 限速, 支持 --max/--interval/--routes。② 部署三层自愈——运行 tools/install_autostart.py 安装登录自启(Startup 文件夹 .cmd 防 MSIX 注册表面纱 + HKCU Run 双保险), 尽力注册每日 07:30 的 FareAlertWorkerRevive 计划任务(硬内核主机可能拒绝, 拒绝时靠 webui 内置 07:00 supervisor 线程兜底), /api/health 的 revive.task 可观测安装状态。单测 20 用例全绿(新增回填合并/跳过/预算 3 例), 版本 0.95 五处盖章。

- [x] **v0.96 当日最低参考班徽章**: 详情卡「当日实测班次」按起飞时刻排序展示, 用户要比价得逐班扫一遍价格——现在后端 `_alt_times_with_best_ref` 在 booking 来源且 price>0 的班次里选出参考价最低者标 `best_ref`, 前端该班 chip 加琥珀色「最低参考」角标; 时刻排序保持不动(比价看徽章, 赶时间看顺序两不误), 无价/非 booking 班次永不中标, 并列取首个。实测: 杭州-重庆 09-16 的 3U2579(¥1296) 压过 HU7421(¥2101) 中标。回填验收: 4 路由 x 60 天 = 240/240 全部带价, 印证「灰点日期精点必有价」。

- [x] **v0.97 周报亮点带起降时刻**: 归档层(core/history._route_metrics)此前只存价格统计, 最优班的 dep/arr/no/dur 在归档边界被丢掉——周报亮点与推送从归档生成, 自然显示不了「几点飞」。现在归档透传时刻, week_highlights 的 sharp_drops/below_threshold 行携带 dep_time/arr_time/flight_no, 前端骤降/破线行渲染时刻 chip, 推送亮点文本「06:50起飞」; 明日首个新归档日后生效(今日已归档的 4 条 meta 无时刻, 属预期)。

- [x] **v0.98 运行时看门狗(第 4 层自愈)**: 前三层(07:00 supervisor/Startup/.cmd/07:30 计划任务)都只负责「启动」, 运行中死亡要等 6h 追赶或次日窗口。① core/revive 心跳 >=90min(2 个采集周期)立即探活+复活, 每小时限 1 次防风暴, 进程在而心跳老只记 note 不 kill; ② tools/watchdog.py 外部守护 webui 本体(每 15min 计划任务 FareAlertWatchdog, 连续 2 次探活失败才重启, 30min 冷却), 状态落 data/watchdog_state.json 并入 /api/health; ③ 修复 register_revive_task.ps1 路径反斜杠丢失(toolsautostart_worker.ps1 -> tools/autostart_worker.ps1, 原任务明早首跑必失败), 两任务已重注册验证 Ready。
- [x] **v0.99 ECB 每日汇率**: 灰点日期的精点补价(booking.com 单日报价)此前用写死 7.8 换算 EUR, 是参考价最大误差源。① core/fx.py 每日 ECB 参考汇率链: frankfurter.app(ECB 免 key 镜像) -> ECB 官方 SDW CSV -> 隔夜缓存(stale 标记) -> 固定汇率兜底, 12h 刷新, 全链路不抛异常; ② booking 缓存条目新增 eur 原值, 回放时按当前汇率重算 cny(旧条目兼容直通), fill_gaps/backfill_prices 统一走 _resolve_fx; ③ config 新增 booking_fill.fx_mode(ecb/fixed, 默认 fixed 零网络), /api/health 新增 fx 观测块。test_fx 6 例。
- [x] **v1.00 推送当日参考班+看门狗绝对路径修复**: ① 阈值推送正文新增「当日班次参考」行——best_ref_alt 镜像 UI 端 v0.96 best_ref 语义(alt_times 中 src==booking 且 price>0 的最低价班次), OTA 最低价行缺可信起飞时刻时, 推送仍点名具体班次+精确起降窗+参考价(「当日班次参考: 3U2579 06:50-09:25 参考¥1296」), 无窗/无价自然跳过; ② 实弹修复: FareAlertWatchdog 计划任务 action 裸 python.exe 在任务会话解析到 WindowsApps 存根别名, 每 15min 触发全部 0x80070002 静默失败(注册以来从未真正跑过, 昨晚 state 全靠手动运行)——register_watchdog_task.ps1 改为注册时解析 sys.executable 绝对路径+Test-Path 校验, 重注册后 schtasks /run 实测 exit 0、watchdog_state.json 刷新、/api/health 回到 healthy。test_alert_msg +3 例。

## 免责声明

本项目仅聚合公开接口数据做个人出行比价提醒,不保证价格实时准确,不构成购票建议;购票请以航司/12306/平台下单页为准。请遵守各数据源服务条款,合理控制查询频率。

## License

[MIT](LICENSE) © FareAlert contributors
