import * as path from 'path';
import * as fs from 'fs';
import express, { IRouter } from 'express';
import type { Plugin, PluginRouter, ServerAPI } from '@signalk/server-api';

const PLUGIN_ID = 'signalk-datalab-plugin';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const PACKAGE_NAME: string = require('../package.json').name;

// The server also passes its Express app, which ServerAPI doesn't type
type App = ServerAPI & Pick<IRouter, 'use'>;

module.exports = function (app: App): Plugin {
  const publicDir = path.join(__dirname, '..', 'public');

  // Serve the WASM bundle at the scoped webapp URL SignalK uses for this package
  app.use(`/${PACKAGE_NAME}`, express.static(publicDir));

  const plugin: Plugin = {
    id: PLUGIN_ID,
    name: 'SignalK Data Lab',
    description: 'Interactive data analysis notebooks for SignalK, using Marimo running as WebAssembly in the browser — no Python required on the server.',

    registerWithRouter(router: PluginRouter) {
      // Serve all WASM bundle assets (JS chunks, fonts, icons, …)
      router.use('/', express.static(publicDir));

      // /ui is the canonical entry point linked from the SignalK admin panel
      router.get('/ui', (_req, res) => {
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
    },

    schema: { type: 'object', properties: {} },

    start(): void {
      app.setPluginStatus(`Data Lab Notebooks ready — open /plugins/${PLUGIN_ID}/ui`);
    },

    stop(): void {
      app.setPluginStatus('Stopped');
    },
  };

  return plugin;
};
