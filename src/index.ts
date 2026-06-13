import * as path from 'path';
import * as fs from 'fs';
import express from 'express';

const PLUGIN_ID = 'signalk-datalab-plugin';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const PACKAGE_NAME: string = require('../package.json').name;

module.exports = function (app: any) {
  const plugin: any = {
    id: PLUGIN_ID,
    name: 'SignalK Data Lab',
    description: 'Interactive data analysis notebooks for SignalK, using Marimo runnuing as WebAssembly in the browser — no Python required on the server.',
  };

  const publicDir = path.join(__dirname, '..', 'public');

  // Serve the WASM bundle at the scoped webapp URL SignalK uses for this package
  app.use(`/${PACKAGE_NAME}`, express.static(publicDir));

  plugin.registerWithRouter = function (router: any) {
    // Serve all WASM bundle assets (JS chunks, fonts, icons, …)
    router.use('/', express.static(publicDir));

    // /ui is the canonical entry point linked from the SignalK admin panel
    router.get('/ui', (_req: any, res: any) => {
      const htmlPath = path.join(publicDir, 'index.html');
      if (fs.existsSync(htmlPath)) {
        res.sendFile(htmlPath);
      } else {
        res.status(503).send(
          '<!doctype html><html><body>' +
          '<h2>Notebook not built</h2>' +
          '<p>Run <code>npm run build:wasm</code> in the plugin directory.</p>' +
          '</body></html>',
        );
      }
    });
  };

  plugin.schema = { type: 'object', properties: {} };

  plugin.start = function (_options: any): void {
    app.setPluginStatus(`Data Lab Notebooks ready — open /plugins/${PLUGIN_ID}/ui`);
  };

  plugin.stop = function (): void {
    app.setPluginStatus('Stopped');
  };

  return plugin;
};
