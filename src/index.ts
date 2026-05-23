import * as path from 'path';
import * as fs from 'fs';
import express from 'express';

const PLUGIN_ID = 'signalk-datalab-plugin';

module.exports = function (app: any) {
  const plugin: any = {
    id: PLUGIN_ID,
    name: 'Data Notebooks for SignalK',
    description: 'Interactive data analysis notebooks for SignalK, using Marimo runnuing as WebAssembly in the browser — no Python required on the server.',
  };

  // Redirect the webapp entry point to the plugin router's /ui
  app.use(`/${PLUGIN_ID}`, (_req: any, res: any) => {
    res.redirect(`/plugins/${PLUGIN_ID}/ui`);
  });

  const publicDir = path.join(__dirname, '..', 'public');

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

  plugin.start = function (): void {
    app.setPluginStatus('Data Notebooks ready — open /plugins/signalk-data-notebooks/ui');
  };

  plugin.stop = function (): void {
    app.setPluginStatus('Stopped');
  };

  return plugin;
};
