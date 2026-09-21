// Build-time only. Installed plugins serve this bundled HTML with Python; no npm at runtime.
import { build } from 'esbuild';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const plugin = path.join(root, 'plugins/update-probe');
const release = JSON.parse(await readFile(path.join(plugin, 'release.json'), 'utf8'));
const bundled = await build({
  absWorkingDir: root, entryPoints: ['ui/app.js'], bundle: true, write: false,
  format: 'esm', target: 'es2022', minify: true, legalComments: 'inline', metafile: true,
  define: { __PROBE_RELEASE__: JSON.stringify(release) },
});
const javascript = bundled.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const template = await readFile(path.join(root, 'ui/app.html'), 'utf8');
const html = template.replace('__UI_VERSION__', release.version).replace('__UI_MARKER__', release.ui_marker)
  .replace('<script>__APP_BUNDLE__</script>', () => `<script type="module">${javascript}</script>`);
// Include licenses for every package contributing bundled code, not only the top-level SDK.
const notices = new Map();
for (const input of Object.keys(bundled.metafile.inputs).sort()) {
  if (!input.startsWith('node_modules/')) continue;
  let directory = path.dirname(path.join(root, input));
  while (directory.startsWith(path.join(root, 'node_modules'))) {
    let pkg;
    try { pkg = JSON.parse(await readFile(path.join(directory, 'package.json'), 'utf8')); } catch {}
    if (pkg?.name) {
      if (!notices.has(pkg.name)) {
        let license;
        for (const name of ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'license', 'license.md', 'LICENSE-MIT']) {
          try { license = await readFile(path.join(directory, name), 'utf8'); break; } catch {}
        }
        if (!license) throw new Error(`Missing license for bundled dependency ${pkg.name}`);
        notices.set(pkg.name, `${pkg.name} ${pkg.version}\n${license.replace(/\r\n/g, '\n').replace(/[ \t]+$/gm, '').trim()}\n`);
      }
      break;
    }
    directory = path.dirname(directory);
  }
}
const outputs = new Map([
  ['app.html', html],
  ['THIRD-PARTY-NOTICES.txt', 'Bundled MCP Apps UI dependencies\n\n' + [...notices.values()].join('\n-----\n\n')],
]);
const check = process.argv.includes('--check');
for (const [name, content] of outputs) {
  const target = path.join(plugin, 'web', name);
  if (check) {
    if (await readFile(target, 'utf8') !== content) throw new Error(`UI build drift: ${name}`);
  } else {
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content, 'utf8');
  }
}
console.log(`${check ? 'Verified' : 'Built'} self-contained MCP App: ${Buffer.byteLength(html)} bytes, ${notices.size} dependency licenses`);
