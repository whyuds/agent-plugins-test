// Protocol-level test host, not a substitute for Codex/Cursor/VS Code acceptance.
import { AppBridge, PostMessageTransport } from '@modelcontextprotocol/ext-apps/app-bridge';
window.mountProbe = async ({ html, initial, theme = 'light' }) => {
  const iframe = document.getElementById('app');
  const bridge = new AppBridge(null,
    { name: 'update-probe-test-harness', version: '1.0.0' },
    { serverTools: {} }, { hostContext: { theme, displayMode: 'inline' } });
  bridge.oncalltool = (params) => window.realMcpCall(params);
  bridge.oninitialized = async () => {
    await bridge.sendToolInput({ arguments: { nonce: 'ui-smoke' } });
    await bridge.sendToolResult(initial);
  };
  bridge.onsizechange = ({ height }) => { iframe.style.height = `${height}px`; };
  await bridge.connect(new PostMessageTransport(iframe.contentWindow, iframe.contentWindow));
  window.testBridge = bridge;
  // Equivalent no-network CSP to our resource metadata, applied by this test host.
  iframe.srcdoc = html.replace('<head>', `<head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">`);
};
