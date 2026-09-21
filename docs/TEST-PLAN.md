# 插件跨客户端安装与更新测试

## 目标与边界

测试一个离线插件 `update-probe` 在 Codex Desktop、Cursor IDE、VS Code 的
GitHub Copilot Agent Plugins 中的安装、Skill/MCP 可用性和远端更新。
**VS Code 的 Copilot 插件页不是 Codex IDE 扩展；不要混用结果。**

只测试这个演示插件，不修改或卸载现有业务插件，不接入公司 API、SSO、MCP Tunnel。
需要客户端能运行 `python`（Python 3.10+）；无 pip/npm 依赖。模型调用仍可能产生客户端费用。
首版为 `0.1.0 / BLUE / probe-010-blue-20260921`。本次只发布首版，收到首版记录后才发布下一轮。

## 1. 首版结构与实验解释

| 层 | 首版文件 | 目的 |
|---|---|---|
| 通用包 | 插件内 `plugin.json`、`skills/`、`mcp.json` | Agent Plugins 1.0 的 Skill + MCP |
| Codex 兼容 | `.agents/plugins/marketplace.json`、插件内 `.codex-plugin/plugin.json` 和 `.mcp.json` | 市场发现和现有 Codex 加载路径 |
| VS Code 市场 | `.github/plugin/marketplace.json` | 指向同一份通用插件包 |
| Cursor 兼容 | `.cursor-plugin/marketplace.json`、插件内 `.cursor-plugin/plugin.json` 和 `mcp.cursor.json` | 市场发现与 Cursor 路径变量 |

只有一个插件、一份 Skill、一份 MCP 实现。兼容描述由 `scripts/sync_manifests.py` 生成。
没有 Claude 回退市场，避免第一轮无法判断哪个入口生效。
通用 MCP 使用规范规定的默认插件根目录，不依赖 Cursor 尚不展开的 `${PLUGIN_ROOT}`。
`loader_route` 显示实际使用的配置：`portable-default-cwd`、`codex-relative-cwd` 或 `cursor-native-root`。
它不能单独证明所有 manifest 解析细节，需要结合宿主日志。第一轮是**兼容组合包**，不是纯通用格式认证。

## 2. 来源与隔离

- GitHub：`https://github.com/whyuds/agent-plugins-test.git`
- GitLab：`ssh://git@gitlab.qiyi.domain:10022/wangyudong/agent-plugins-test.git`
- 两端跟踪分支均为 `master`，首版标签 `v0.1.0`。测试更新时跟踪 **master 分支**，不能固定标签或 commit。
- 两仓库首版内容相同、插件名和市场名相同。**同一客户端一次只启用一个来源。**
- 推荐先完成 GitHub 三端安装及升级，再测试 GitLab；切换前在客户端卸载演示插件并移除演示市场，记录截图。
- 不清理全局缓存、不卸载业务插件。卸载或重新安装属于最后的恢复手段，不算正常更新通过。
- 不打开演示仓库作为测试对话的工作区；选一个中性空目录，避免 Agent 直接读取源码而绕过安装包。
- 不把本地路径市场的结果冒充远端市场结果；本地安装只能作为独立诊断。

Cursor 的团队远端市场需要对应套餐和仓库接入权限。GitLab 网络/认证受限记 `blocked`，不要记插件格式失败。
GitLab 自托管服务本机能访问，不代表 Cursor 的服务端导入可访问。不要为本测试把内部仓库或凭证公开。

## 3. 先记录环境（每个客户端/来源各一份）

记录：日期时间及时区、OS、客户端完整版本、账号套餐/团队、插件相关策略、来源URL、分支、
安装作用域（用户/项目）、安装方式（远端直连/团队市场/本地诊断）、自动更新设置、是否需管理员。
截图保留插件列表、插件详情/版本和工具列表。不要截图凭证、token、SSH 私钥。
本地工具回执的 `installed_root` 可能包含用户名；公开分享前脱敏。

## 4. 首次安装：当前要做的步骤

### Codex Desktop

1. 插件 → 市场 → 添加 Git 仓库，输入 GitHub URL，或添加 GitLab SSH URL。选择/跟踪 `master`。
2. 在 `agent-plugins-test` 市场安装 `update-probe`，记录显示的名称/版本和有无异常权限请求。
3. 新建任务，选中该插件，再执行下面的统一提示词。
4. 若 GUI 不能添加，可用以下 CLI 建市场，然后回到 GUI 安装。**记录使用了 CLI，不声称 GUI 添加成功。**

```powershell
# 二选一，不要同时执行
codex plugin marketplace add https://github.com/whyuds/agent-plugins-test.git --ref master
# 或
codex plugin marketplace add ssh://git@gitlab.qiyi.domain:10022/wangyudong/agent-plugins-test.git --ref master
```

本轮不预先执行 `marketplace upgrade` 或重新安装，否则会破坏被动更新观察。

### Cursor IDE

1. 先记录当前版本、套餐，以及 Customize/Plugins 是否有远端仓库导入入口。
2. 若有客户端直接导入 Git URL 的入口，可先测一次并标注为 `direct-git`；不要把团队市场的结论套到它。
3. 官方团队市场路径：Dashboard → Plugins & MCPs → Team Marketplaces → Add Marketplace → Import from Repo。
   输入 GitHub/GitLab 仓库 URL，跟踪 `master`，按提示接入仓库。在 Customize 安装插件。
4. 记录 GitHub Auto Refresh 开关状态。GitLab 先按手动 Refresh 路径测试，不预设它支持 push 自动刷新。
5. 新建对话运行统一提示词。无团队权限且无直接远端入口时记录 `blocked/unsupported`，先反馈，不强行换本地安装。

### VS Code / GitHub Copilot

1. Agent Customizations → Plugins → Install from Source，输入远端 Git URL。先测 GitHub，再单独测 GitLab。
2. 若不能持久登记市场，在用户设置中**追加**到现有 `chat.plugins.marketplaces` 列表，不覆盖其他条目：

```json
"chat.plugins.marketplaces": ["https://github.com/whyuds/agent-plugins-test.git"]
```

GitLab 用提供的 SSH URL另行测试。记录 URL 是否被接受；客户端文档没承诺每种自托管 SSH URL 的解析行为。
可先用 `git ls-remote <URL>` 区分 Git 访问失败与市场格式失败，不修改 SSH 配置来掩盖首次结果。
3. 安装 `update-probe`，查看 Skills 和 MCP Servers，记录是否要求信任/启用。
4. 新建 Copilot Agent 对话，执行统一提示词。记录 `extensions.autoUpdate` 原值，不为了通过而预先改动。

### 三端统一提示词（不告诉模型预期版本）

每次更换 nonce；例如 `github-cursor-install-20260921-01`。

```text
请使用已安装插件 update-probe 的 update-probe-check 技能做安装验收。
本次 nonce：github-codex-install-20260921-01。
读取已安装的 Skill 并报告它声明的 marker；实际调用插件的 probe_release，
再调用 probe_sum 计算 7+5，两次使用相同 nonce。
列出实际 skill marker、MCP version/build_id/marker、loader_route、instance_id、
started_at、package_sha256、disk_matches_startup、回显 nonce 和运算结果。
如果技能或工具不可用，原样报告，不要下载仓库、手动运行脚本、安装其他副本或用心算替代工具。
```

首版核对：Skill=`SKILL-010-BLUE`，MCP=`0.1.0 / BLUE / probe-010-blue-20260921`，
nonce与本次一致，sum=12，两个工具可见并真实调用，`disk_matches_startup=true`。
不要只凭助手说“成功”或插件详情中的版本判通过。保留真实工具调用展开内容。

## 5. 更新实验：等首版确认后分轮推送

**每轮都先记录旧版本，再由维护者推送。不要一次把后续版本全推掉。**

| 轮次 | 唯一重点变化 | 观察问题 |
|---|---|---|
| U1（下一步） | `0.1.0 → 0.1.1`，BLUE→GREEN；Skill 与 MCP 标记同步变，工具名/schema不变 | 常规版本升级能否发现、提示、更新并生效 |
| U2（可选独立实验） | 保持已安装数字版本，改变 build_id/marker/内容；先不改构建后缀 | 实际按提交、内容、SemVer还是版本字符串识别；无更新也可能符合宿主策略 |
| U3（可选） | 数字版本不变，仅增加/改变 SemVer `+build` 后缀 | 构建后缀是否作为缓存键；不能预设 SemVer 优先级会变 |
| U4（可选） | 升到 `0.2.0`，增加新工具/参数和新技能 | MCP schema 与 Skill 列表缓存能否刷新 |

GitHub 升级时先不推 GitLab，保留 GitLab 首版做独立来源轮次。用户完成 GitLab 首版后再同步升级。
U2/U3不是推荐发布方式，而是诊断缓存策略的隔离实验。每次只运行一轮；得到确认才执行下一次发布。

### 每轮按这个顺序记录

1. **被动观察**：推送后保持旧对话/应用，记录 T+0、T+10分钟、T+30分钟是否有更新提示、版本变化。
   不反复点击刷新。Cursor GitHub后台索引有节流；VS Code文档的自动检查周期可到24小时，30分钟无提示不能判自动更新永久失败。
   要验证完整自动周期可选次日检查，必须保持原始设置并记录是否退出客户端。
2. **回到窗口**：切走再回来，观察有无提示；不点击升级，先截图。
3. **主动检查**：Codex市场“升级/刷新”；Cursor团队市场 `Refresh`；VS Code命令面板
   `Extensions: Check for Extension Updates`。精确记录动作时间和是否直接改变了运行版本。
   Codex CLI备选：`codex plugin marketplace upgrade agent-plugins-test`，不要无参数刷新全部市场。
4. **提示与安装分开**：有 Update按钮先记录是否自动安装、是否需要确认，再执行更新。
   市场已更新不代表插件已更新；无按钮但插件已静默更新也应单独记录。
5. **旧对话**：用新 nonce 重测，记录它仍旧版本还是热更新；旧会话不变不直接判失败。
6. **新对话**：不重启应用，重测。比较 Skill marker、MCP版本、进程instance、包哈希和工具schema。
7. **重启后新对话**：前步未生效才执行 Reload Window/完整重启，重测，记录最小生效动作。
8. **最后恢复**：只有前面都失败才卸载重装本演示插件。记录“重装可用，正常更新未通过”，不能覆盖前面的失败。

## 6. 格式控制实验（安装/更新主线完成后再做）

不要在 U1 过程中同时更换 manifest 格式。必要时建立独立格式分支/市场ID，分别验证：

- F1：纯通用 `plugin.json + skills + mcp.json`，保留该客户端必要的市场目录；去掉插件级兼容描述。
- F2：首版兼容包（当前方案），与 F1 比较插件发现、路径解析和工具可用性。
- F3：仅保留 Codex市场文件，验证其他客户端“找不到市场”是否可重现。

格式实验本轮尚未发布，不要把 F2 成功当作 F1 成功。失败时保存精确入口、客户端版本及错误；
不直接改本地配置再把结果记到原格式。用干净客户端 profile 或移除**演示插件**后测试，其他插件保持不动。

## 7. 记录与结论

复制 `docs/results-template.csv` 到本机 `results/`（已被 git 忽略）。截图/回执也放这里，不自动上传。
发现、安装、Skill、MCP、提示、更新、生效动作分别记录，不合成一个模糊“成功”。

状态可用：`pass`、`fail`、`blocked`、`unsupported`、`not_observed`、`pending`。
提示单独记录：`badge/dialog/silent/none_in_window/not_tested`。
区分根因：网络/认证、套餐/组织策略、市场发现、插件格式、Python环境、MCP启动、更新检测、旧会话缓存。

完成 U1 的标准：每个可运行客户端/来源都记录了首版证据、升级后的提示方式与实际运行版本、所需最小动作；
受阻路径保留阻塞原因，不伪造通过。自动化单测不替代客户端实测。

## 8. 维护与依据

新版本只编辑 `plugins/update-probe/release.json`（必要时修改功能代码），运行：

```powershell
python scripts/sync_manifests.py
python scripts/sync_manifests.py --check
python -m unittest discover -s tests -v
git diff --check
```

这些命令不安装插件、不刷新市场、不 push。当前基线不改版本、不自动重装，不预先发布后续版本。

官方依据（2026-09-21核对，客户端行为以实测为准）：

- [Agent Plugins 格式边界](https://agent-plugins.org/)
- [标准 MCP 路径与默认工作目录](https://agent-plugins.org/plugin-authors/mcp-servers)
- [Codex 插件与市场](https://developers.openai.com/plugins/build/plugins)
- [Cursor 插件、团队市场和更新](https://cursor.com/docs/plugins)
- [Cursor 格式与路径变量](https://cursor.com/docs/reference/plugins)
- [VS Code 插件安装及更新](https://code.visualstudio.com/docs/agent-customization/agent-plugins)
