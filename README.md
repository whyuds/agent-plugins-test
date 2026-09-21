# Agent Plugins Update Probe

用于 **Codex Desktop / Cursor IDE / VS Code Copilot** 的插件安装与更新实验。
不含公司业务代码、凭证、业务数据或网络 API；只需要 PATH 中的 **Python 3.10+**。

## 现在测试什么

当前 UI 基线版本 **0.2.0 / TEAL**，插件名 `update-probe`，市场名 `agent-plugins-test`。
早期无 UI 的 `v0.1.0` 标签保持不变；后续常规更新实验从 **0.2.0 → 0.2.1** 开始。

- 一个技能：`update-probe-check`，标记 `SKILL-020-TEAL`。
- 三个只读 MCP 工具：`probe_release`（版本/进程/哈希）、`probe_sum`（真实计算）和 `probe_ui`（打开交互卡片）。
- 标准 MCP Apps 卡片：自身标记 `UI-020-TEAL`，对照服务版本，输入 nonce，按钮通过宿主调用真实 MCP。
- UI 资源 URI 带构建标记和 HTML 哈希；磁盘变更、旧进程与卡片缓存可分别判断。
- 同一份插件包带 Agent Plugins 标准结构和少量 Codex/Cursor 安装兼容描述。
- 服务进程冻结启动时的版本和哈希，不会读取新文件后冒充进程已升级。
- **安装运行时**无 pip/npm 安装、无登录、无遥测、无外部网络、无自动更新脚本。
  HTML 已内置官方 MCP Apps SDK；维护者构建 UI 才需要 Node.js 与 npm。

## 按这个顺序开始

1. 阅读 [测试计划](docs/TEST-PLAN.md)，先测 GitHub 来源，三端分别安装首版。
2. 在中性工作区新建对话，选中插件后发送下面提示词。
3. 把插件详情截图和真实工具回执发给维护者；**暂时不发布/拉取第二版**。
4. 首版确认后再协同发布下一版，观察提示、主动更新、旧/新会话与重启后的差异。
5. 同一客户端切到 GitLab 前卸载这个演示插件、移除这个演示市场，避免同名来源冲突。

```text
请使用已安装的 update-probe 插件中的 update-probe-check 技能验收。
nonce 使用 github-codex-install-01（按当前客户端和轮次换一个新值）。
报告已加载技能的 marker，实际调用 probe_release 和 probe_sum（7+5），然后调用 probe_ui 打开卡片。
列出版本、build_id、loader_route、instance_id、package_sha256、
disk_matches_startup、回显 nonce 和 sum。
如果工具不可用就报告不可用，不要下载源码或直接运行脚本替代。
工具调用成功不代表卡片已显示；等我点击卡片按钮反馈，不要替我声称 UI 已通过。
```

看到卡片后，手动更改测试标记，点击“刷新服务版本”和“通过 MCP 计算”，应看到相同构建和 `7 + 5 = 12`。
卡片不显示时仍记录 Skill/MCP 结果；UI 单独标记失败、未知或客户端不支持，勿把两者混为一谈。

两仓库均跟踪 `master`，不要固定版本标签来测试更新。
首版源码和发行标签会推到用户指定的两个测试仓库；不同宿主的 GUI 安装与通知结果需要实测，**尚不宣称通过**。
结果模板：[CSV](docs/results-template.csv)。实际截图/回执放本地被忽略的 `results/`，不要提交账户信息。

## 本地开发检查

```powershell
python scripts/sync_manifests.py --check
python -m unittest discover -s tests -v
# 仅维护者构建/测试 UI，最终用户不用执行
npm ci
npm run build
npm run check:ui
npm run test:ui
```

`release.json` 是版本来源，`scripts/sync_manifests.py` 只生成清单及 Skill 标记。
`.agents/plugins/marketplace.json` 由 plugin-creator 脚手架创建；其他格式的市场均指向同一插件目录。
不需要启动常驻网络服务。MCP 由宿主通过 stdio 启停；stdout 只输出 JSON-RPC。
`npm run test:ui` 使用本机 Edge 无头模式和官方 AppBridge SDK 做协议级浏览器测试，
按钮转发到真实 Python MCP。截图/回执写入 `tmp/ui-smoke/`，不冒充三客户端实机验收。
本地可用其他 Chromium 时通过 `PROBE_BROWSER` 指定 Playwright channel。
`installed_root` 仅为了在本机识别真实安装副本，会包含本机路径；公开贴回执前请脱敏。

