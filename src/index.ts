import * as path from 'path';
import * as http from 'http';
import httpProxy from 'http-proxy';
import { MarimoManager } from './marimo-manager';

interface PluginConfig {
  port: number;
  provider: string;
  signalkUrl: string;
  notebookPath: string;
  mode: 'edit' | 'run';
}

const PLUGIN_ID = 'signalk-data-notebooks';
const DEFAULT_PORT = 2718; // Euler's number — Marimo's default

module.exports = function (app: any) {
  const plugin: any = {
    id: PLUGIN_ID,
    name: 'Data Notebooks for Signalk',
    description: 'Data analyis notebooks for querying and visualizing the SignalK History API',
  };

  let marimo: MarimoManager | null = null;
  let proxyServer: http.Server | null = null;
  let proxyInstance: httpProxy | null = null;

  // registerWithRouter: GET /ui redirects to Marimo using request hostname
  // so remote access (over boat LAN) resolves correctly.
  let configuredPort = DEFAULT_PORT;

  plugin.registerWithRouter = function (router: any) {
    router.get('/ui', (req: any, res: any) => {
      if (!marimo?.running) {
        res.status(503).send(
          `<h2>Marimo is not running</h2>` +
          `<p>Check the plugin status in the ` +
          `<a href="/admin/#/serverConfiguration/plugins/${PLUGIN_ID}">SignalK admin panel</a> ` +
          `for the error message.</p>`,
        );
        return;
      }
      res.redirect(`http://${req.hostname}:${configuredPort}/`);
    });
  };

  plugin.schema = {
    type: 'object',
    required: ['port'],
    properties: {
      port: {
        type: 'number',
        title: 'Web port',
        description: 'Port Marimo listens on (also accessible via /plugins/signalk-data-notebooks/ui)',
        default: DEFAULT_PORT,
      },
      provider: {
        type: 'string',
        title: 'Default History API provider',
        description: 'e.g. signalk-parquet. Leave empty to use the server default.',
        default: '',
      },
      signalkUrl: {
        type: 'string',
        title: 'SignalK server URL',
        description:
          'URL the notebook uses to call the History API. Defaults to http://localhost:<server-port>.',
        default: '',
      },
      notebookPath: {
        type: 'string',
        title: 'Notebook path',
        description:
          'Path to the .py notebook file. Leave empty to use the default in the SignalK data directory.',
        default: '',
      },
      mode: {
        type: 'string',
        title: 'Marimo mode',
        description: '"edit" lets users modify notebook code; "run" is read-only interaction.',
        enum: ['edit', 'run'],
        default: 'edit',
      },
    },
  };

  plugin.start = async function (options: PluginConfig): Promise<void> {
    const log = (msg: string) => app.debug(msg);
    configuredPort = options.port ?? DEFAULT_PORT;

    // Resolve notebook path — use user's path or create one in the data directory
    const notebookPath =
      options.notebookPath?.trim() ||
      path.join(app.getDataDirPath(), 'notebooks', 'signalk.py');

    // Seed from bundled template if the file doesn't exist yet
    const templateDir = path.join(__dirname, 'notebooks');
    try {
      MarimoManager.ensureNotebook(notebookPath, templateDir);
    } catch (err) {
      app.setPluginError(`Notebook setup failed: ${err}`);
      return;
    }

    // Resolve the SignalK server URL for the notebook's History API calls
    const serverPort: number = app.getPort?.() ?? 3000;
    const signalkUrl =
      options.signalkUrl?.trim() || `http://localhost:${serverPort}`;

    const venvDir = path.join(app.getDataDirPath(), '.venv');

    app.setPluginStatus('Installing Python dependencies…');
    try {
      await MarimoManager.ensureDeps(venvDir, log);
    } catch (err) {
      app.setPluginError(`Dependency setup failed: ${err}`);
      return;
    }

    marimo = new MarimoManager();

    app.setPluginStatus('Starting Marimo…');
    try {
      await marimo.start(
        {
          port: configuredPort,
          notebookPath,
          signalkUrl,
          provider: options.provider ?? '',
          mode: options.mode ?? 'edit',
          venvDir,
        },
        log,
        (code) => {
          if (marimo) app.setPluginError(`Marimo exited unexpectedly (code ${code})`);
        },
      );
    } catch (err) {
      app.setPluginError(String(err));
      return;
    }

    app.setPluginStatus(
      `Marimo on :${configuredPort} · /plugins/${PLUGIN_ID}/ui · ${notebookPath}`,
    );
  };

  plugin.stop = function (): void {
    proxyInstance?.close();
    proxyServer?.close();
    proxyInstance = null;
    proxyServer = null;
    marimo?.stop();
    marimo = null;
    app.setPluginStatus('Stopped');
  };

  return plugin;
};
