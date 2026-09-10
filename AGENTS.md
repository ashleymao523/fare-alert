# AGENTS.md — 在本仓库工作的人机共同守则

> 无论人类贡献者还是 AI 编码代理（Codex/Claude 等），改代码前先读完本文件。
> 本文件与 `docs/验收规范.md`、`docs/迭代路线图.md` 配套使用。

## 项目一句话

FareAlert：自部署的机票/动车低价监控组件。含税支付口径 + 12306 学生票对比 + Bark/微信推送。

## 红线（违反任何一条即回滚）

1. **不破解接口签名、不绕过验证码**。遇到需要签名的接口：记录研究结论后放弃，改用合规替代方案（参考 docs/迭代路线图.md 的研究归档区）。
2. **低频只读**。任何新数据源默认 `interval_minutes >= 30`、`timeout_seconds <= 30`、失败退避；不做并发轰炸。
3. **隐私不入库**。`config.json`（含推送 key）与 `data/` 已 gitignore；任何真实密钥、个人信息不得进入提交。
4. **估算价只做展示**。插值(`interp`)与临近日参考(`nearby-ref`)不得触发提醒、不得参与最低价/均价/TOP5 统计。后端与前端两侧都要守住。

## 环境事实（Windows PowerShell 5）

- 无 `&&`，无 `head`；多命令用分号或分开执行。
- python 单行内联转义极易踩坑：复杂逻辑写临时脚本 `tools/*_tmp.py`，用完删除。
- 中文文件一律 UTF-8 读写；PowerShell 控制台显示乱码 ≠ 文件损坏。
- 修改 `webui/static/` 下任何文件后，必须同步升 `index.html` 的 `?v=` 缓存版本号和右上角版本徽章，以及 `tools/dump_dom.cmd`、`tools/shot.cmd` 的 URL。

## 开发-验收工作流（每次改动必须走完）

1. 改代码（后端 py / 前端 js+css / 文档）。
2. G0 静态检查：`python -m compileall` + `node --check`。
3. G1 单元测试：`python tests/test_core.py`。
4. G3 展示断言：`tools\dump_dom.cmd` → `tools\ui_check.py`（改动 UI 时必跑）。
5. 总验收：`python tools/acceptance.py`，全绿才可提交。
6. 提交信息格式：`vX.Y: 一句话摘要`（用户可见功能）或 `eng: ...`（工程与文档）。

## 模块验收

新增模块按 `docs/验收规范.md` 的 G0-G6 门禁 + `docs/迭代路线图.md` 中该里程碑的 DoD（完成定义）与测试实例逐条验收；不达标不算完成，先修再进下一模块。

## 探针研究工作流

研究新数据源时：临时探针放 `tools/*_tmp.py` → 结论写入路线图“研究归档区” → 删除探针。结论必须包含：端点、是否需签名、反爬表现、合规替代方案。

## Git 协作与会话接续

### 分支规范

- `master` = 稳定线，任何时刻验收全绿，禁止半成品直推。
- 功能开发开分支 `codex/<里程碑>-<主题>`，如 `codex/m1-mcp-server`，完成后走 PR 合入。
- 里程碑完成即打 tag（`v0.11`、`m1`…），tag 指向该里程碑最后一个提交。

### 接力开发协议（新会话恢复上下文的三步）

任何新会话（包括 AI 上下文用尽后重开）按序执行：
1. 读 `AGENTS.md`（本文件）→ `docs/迭代路线图.md`。
2. `git log --oneline -10` 看最近进展，跑 `python tools/acceptance.py` 确认基线全绿。
3. 从路线图第一个未完成项继续，不重做已完成模块。

每次开发结束的固定动作：过验收 → 提交 → 更新路线图勾选状态 → `git push`（含标签）。

### GitHub 推送规范（隐私红线）

- 本地 git 无需任何权限，Agent 可正常 commit/tag。
- 推送凭据由 gh CLI 管理（本机已 `gh auth login` 完成，含 workflow scope）；**Agent 永不经手、不询问、不存储任何 token/密码**，直接 `git push` 即可；若凭据失效，由人类本人重新 `gh auth login`。
- 外部贡献标准流：fork → 功能分支 → PR → CI 全绿 → 人工 review → 合入。
