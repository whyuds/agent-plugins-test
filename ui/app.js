import { App } from '@modelcontextprotocol/ext-apps';

const release = __PROBE_RELEASE__;
const el = (id) => document.getElementById(id);
const app = new App({ name: 'Update Probe UI', version: release.version });
let connected = false;
let busy = false;
let lastEvidence;

function status(message, state = '') {
  el('status').textContent = message;
  el('status').dataset.state = state;
}
function controls() {
  for (const id of ['refresh', 'sum']) el(id).disabled = !connected || busy;
}
function display(result) {
  if (result.isError) throw new Error(result.content?.find((c) => c.type === 'text')?.text || 'MCP 调用失败');
  const data = result.structuredContent ?? JSON.parse(result.content?.find((c) => c.type === 'text')?.text ?? '{}');
  if (data.plugin !== 'update-probe' || !data.version || !data.ui_marker) throw new Error('非 Update Probe 的有效工具回执');
  lastEvidence = data;
  el('server-version').textContent = data.version;
  el('server-marker').textContent = data.ui_marker;
  el('receipt').textContent = JSON.stringify({ ui: release, server: data }, null, 2);
  if (Number.isInteger(data.sum)) el('answer').textContent = `${data.a} + ${data.b} = ${data.sum}`;
  const same = data.version === release.version && data.build_id === release.build_id && data.ui_marker === release.ui_marker;
  if (!same) status('版本不一致：卡片与 MCP 服务不是同一构建。请保留这个结果，记录缓存问题。', 'error');
  else if (!data.disk_matches_startup) status('进程仍是旧快照：磁盘文件已变化，但当前 MCP 尚未重新加载。', 'error');
  else status(`UI / MCP 构建一致 · nonce: ${data.nonce} · 第 ${data.call_count} 次调用`, 'ok');
}
function safeDisplay(result) {
  try { display(result); } catch (error) { status(error.message, 'error'); }
}
app.ontoolresult = safeDisplay;
app.ontoolinput = ({ arguments: args }) => {
  if (typeof args?.nonce === 'string') el('nonce').value = args.nonce;
};
app.ontoolcancelled = () => status('宿主取消了工具调用；未自动重试。', 'error');
app.onhostcontextchanged = (context) => {
  if (['light', 'dark'].includes(context.theme)) document.documentElement.dataset.theme = context.theme;
};

async function call(name) {
  if (!connected || busy) return;
  busy = true;
  controls();
  try {
    const nonce = el('nonce').value;
    if (!nonce || nonce.length > 120) throw new Error('测试标记必须为 1–120 个字符');
    const args = { nonce };
    if (name === 'probe_sum') {
      el('answer').textContent = '—';
      for (const key of ['a', 'b']) {
        const text = el(key).value;
        if (!/^-?\d+$/.test(text) || Math.abs(Number(text)) > 1000000) throw new Error('A 和 B 必须为 -1000000 到 1000000 之间的整数');
        args[key] = Number(text);
      }
    }
    status('正在通过宿主调用真实 MCP 工具…');
    display(await app.callServerTool({ name, arguments: args }, { timeout: 15000 }));
  } catch (error) {
    status(`调用未完成：${error.message}。没有自动重试。`, 'error');
  } finally {
    busy = false;
    controls();
  }
}
el('refresh').addEventListener('click', () => call('probe_release'));
el('sum').addEventListener('click', () => call('probe_sum'));
const hint = setTimeout(() => {
  if (!connected) status('尚未连接到 MCP Apps 宿主。直接打开 HTML 不会调用工具；请在客户端调用 probe_ui。', 'error');
}, 7000);
try {
  await app.connect(undefined, { timeout: 15000 });
  connected = true;
  clearTimeout(hint);
  const context = app.getHostContext();
  if (context?.theme) app.onhostcontextchanged(context);
  if (app.getHostVersion()?.name === 'update-probe-test-harness') el('preview-note').hidden = false;
  if (!lastEvidence) status('已连接宿主。点击“刷新服务版本”读取真实 MCP 回执。');
  controls();
} catch (error) {
  clearTimeout(hint);
  status(`无法连接 MCP Apps 宿主：${error.message}。工具是否可用与 UI 是否支持应分别记录。`, 'error');
}
