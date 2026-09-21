import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { build } from 'esbuild';
import { chromium } from 'playwright';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'tmp/ui-smoke');
await mkdir(output, { recursive: true });
const child = spawn(process.env.PROBE_PYTHON || 'python', ['-u', 'plugins/update-probe/scripts/server.py'], { cwd: root, stdio: 'pipe' });
let id = 0;
const pending = new Map();
const lines = createInterface({ input: child.stdout });
lines.on('line', (line) => {
  const message = JSON.parse(line);
  const handler = pending.get(message.id);
  if (!handler) return;
  pending.delete(message.id);
  clearTimeout(handler.timer);
  if (message.error) handler.reject(new Error(message.error.message)); else handler.resolve(message.result);
});
function rpc(method, params = {}) {
  const number = ++id;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(number); reject(new Error(`RPC timeout: ${method}`)); }, 10000);
    pending.set(number, { resolve, reject, timer });
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: number, method, params }) + '\n');
  });
}
let browser;
const calls = [];
const errors = [];
const network = [];
try {
  await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'ui-smoke', version: '1' } });
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  const tools = await rpc('tools/list');
  const uri = tools.tools.find((tool) => tool.name === 'probe_ui')._meta.ui.resourceUri;
  const html = (await rpc('resources/read', { uri })).contents[0].text;
  const initial = await rpc('tools/call', { name: 'probe_ui', arguments: { nonce: 'ui-smoke' } });
  const expected = initial.structuredContent;
  const host = await build({ absWorkingDir: root, entryPoints: ['tests/host.mjs'], bundle: true, write: false, format: 'iife', minify: true });
  browser = await chromium.launch({ channel: process.env.PROBE_BROWSER || 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 820, height: 780 } });
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.route('**/*', (route) => { network.push(route.request().url()); return route.abort(); });
  await page.exposeFunction('realMcpCall', async (params) => {
    calls.push(params);
    assert.ok(['probe_sum', 'probe_release'].includes(params.name));
    return rpc('tools/call', params);
  });
  await page.setContent('<!doctype html><body style="margin:20px;background:#edf3f1"><iframe id="app" title="MCP Apps protocol test host" sandbox="allow-scripts allow-same-origin" style="width:100%;height:660px;border:1px solid #dce8e5;border-radius:16px;background:white"></iframe></body>');
  await page.addScriptTag({ content: host.outputFiles[0].text });
  await page.evaluate(({ html, initial }) => window.mountProbe({ html, initial }), { html, initial });
  const frame = page.frameLocator('#app');
  await frame.locator('#refresh').waitFor();
  await page.waitForFunction(() => document.querySelector('iframe').contentDocument.querySelector('#refresh')?.disabled === false);
  assert.equal(await frame.locator('#ui-version').textContent(), expected.version);
  assert.equal(await frame.locator('#ui-marker').textContent(), expected.ui_marker);
  await frame.locator('#nonce').fill('button-中文-actual-mcp');
  await frame.locator('#refresh').click();
  await frame.locator('#status[data-state="ok"]').filter({ hasText: 'button-中文-actual-mcp' }).waitFor();
  await frame.locator('#sum').click();
  await frame.locator('#answer').filter({ hasText: '7 + 5 = 12' }).waitFor();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].arguments.nonce, 'button-中文-actual-mcp');
  const screenshot = await page.screenshot({ path: path.join(output, 'ui-light.png'), fullPage: true });
  const pngSha = createHash('sha256').update(screenshot).digest('hex');
  await frame.locator('#a').fill('-9');
  await frame.locator('#b').fill('2');
  await frame.locator('#sum').click();
  await frame.locator('#answer').filter({ hasText: '-9 + 2 = -7' }).waitFor();
  assert.equal(calls.length, 3);
  await frame.locator('#a').fill('1.5');
  await frame.locator('#sum').click();
  await frame.locator('#status[data-state="error"]').filter({ hasText: '必须' }).waitFor();
  assert.equal(calls.length, 3, 'invalid input must not call MCP');
  // Deliberately synthetic notifications test diagnostics, not successful server evidence.
  await page.evaluate((result) => window.testBridge.sendToolResult(result), {
    ...initial, structuredContent: { ...expected, version: '99.0.0' },
  });
  await frame.locator('#status[data-state="error"]').filter({ hasText: '版本不一致' }).waitFor();
  await page.evaluate((result) => window.testBridge.sendToolResult(result), {
    ...initial, structuredContent: { ...expected, disk_matches_startup: false },
  });
  await frame.locator('#status[data-state="error"]').filter({ hasText: '磁盘文件已变化' }).waitFor();
  await page.evaluate((result) => window.testBridge.sendToolResult(result), initial);
  await page.evaluate(() => window.testBridge.sendHostContextChange({ theme: 'dark' }));
  await page.setViewportSize({ width: 390, height: 850 });
  await page.waitForFunction(() => {
    const frame = document.querySelector('iframe');
    return frame.clientHeight >= frame.contentDocument.body.scrollHeight;
  });
  await page.screenshot({ path: path.join(output, 'ui-dark-mobile.png'), fullPage: true });
  const standalone = await browser.newPage();
  await standalone.setContent(html);
  await standalone.locator('#status').filter({ hasText: /尚未连接到 MCP Apps 宿主|无法连接 MCP Apps 宿主/ }).waitFor({ timeout: 12000 });
  assert.equal(await standalone.locator('#refresh').isDisabled(), true);
  assert.deepEqual(errors, []);
  assert.deepEqual(network, []);
  const evidence = { source: 'protocol_test_host_not_native_client', verdict: 'pass', version: expected.version,
    ui_resource_uri: uri, ui_sha256: expected.ui_sha256, package_sha256: expected.package_sha256,
    screenshot_sha256: pngSha, observed_at: new Date().toISOString(), real_button_calls: calls,
    checks: ['SDK handshake', 'initial result', 'nonce echo', 'server sum positive/negative', 'invalid input zero calls',
             'synthetic version mismatch', 'synthetic stale process', 'dark/mobile', 'no host disabled', 'zero network requests'],
    native_clients: { Codex: 'pending', Cursor: 'pending', VSCode: 'pending' } };
  await writeFile(path.join(output, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify(evidence, null, 2));
} finally {
  await browser?.close();
  child.stdin.end();
  child.kill();
  lines.close();
  for (const entry of pending.values()) clearTimeout(entry.timer);
}
