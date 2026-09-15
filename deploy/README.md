# 部署指南

fare-alert 是一个长期运行的私人比价助手, 三种部署形态按需选择:

| 形态 | 适合 | 一句话 |
|---|---|---|
| Docker Compose | NAS / 云主机 / VPS | 数据全在宿主机, 容器随删随建 |
| systemd (Linux 裸机) | 小主机 / 树莓派 | deploy/systemd/install.sh 一键装 |
| Windows | 台式 / 笔记本 | tools/install_autostart.ps1 注册开机自启 |

## Docker Compose(推荐)

```bash
git clone https://github.com/ashleymao523/fare-alert && cd fare-alert
# 编辑 config.json: 路线/阈值/推送
docker compose up -d --build
```

- 镜像发布在 ghcr.io/ashleymao523/fare-alert:latest, compose 里把
  build: . 换成 image: ghcr.io/ashleymao523/fare-alert:latest 即可免构建
- 状态落盘: ./data(班期库/缓存/快照)与 ./config.json 都是宿主机挂载
- 健康: 容器 HEALTHCHECK 与 compose healthcheck 都走 /api/health

## systemd(Linux 裸机)

```bash
cd fare-alert
sudo bash deploy/systemd/install.sh /opt/fare-alert
```

安装器做四件事: 复制代码、建 venv 装依赖、注册 systemd 单元、enable --now。
崩溃 15 秒自动拉起, 开机自启, 日志走 journalctl -u fare-alert -f。

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_autostart.ps1
```

注册 webui + worker 双组件开机自启; 升级代码后跑
tools/restart_all.ps1 热替换 worker。

## 升级与迁移

- 升级: git pull 后重启容器/服务; worker 代码版本由心跳盖章, 落后自动热替换
- 迁移: Web「数据源」页一键导出迁移包, 新设备一键导入; 或直接打包
  data/ 与 config.json
- 备份: 每日首轮自动 zip 备份(保留 7 份), 位于 data/auto_backups/

