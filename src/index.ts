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
  let configuredPort = DEFAULT_PORT;

  // Tracks what the plugin is doing so /ui can show a useful message
  type Phase = 'idle' | 'installing' | 'starting' | 'running' | 'error';
  let phase: Phase = 'idle';
  let phaseDetail = '';

  function setPhase(p: Phase, detail = '') {
    phase = p;
    phaseDetail = detail;
  }

  // registerWithRouter: GET /ui redirects to Marimo using request hostname
  // so remote access (over boat LAN) resolves correctly.
  plugin.registerWithRouter = function (router: any) {
    router.get('/ui', (req: any, res: any) => {
      if (marimo?.running) {
        res.redirect(`http://${req.hostname}:${configuredPort}/`);
        return;
      }

      const adminUrl = `/admin/#/serverConfiguration/plugins/${PLUGIN_ID}`;

      if (phase === 'installing' || phase === 'starting') {
        const label = phase === 'installing'
          ? 'Installing Python dependencies…'
          : 'Starting Marimo…';
        res.status(503).send(
          `<!doctype html><html><head>` +
          `<meta http-equiv="refresh" content="5">` +
          `<title>Marimo starting</title></head><body>` +
          `<h2>${label}</h2>` +
          `<p>This page refreshes automatically every 5 seconds.</p>` +
          `<p>See <a href="${adminUrl}">plugin status</a> for details.</p>` +
          `</body></html>`,
        );
      } else if (phase === 'error') {
        res.status(503).send(
          `<!doctype html><html><head><title>Marimo error</title></head><body>` +
          `<h2>Marimo failed to start</h2>` +
          `<pre style="background:#fee;padding:1em">${escHtml(phaseDetail)}</pre>` +
          `<p>See <a href="${adminUrl}">plugin status</a> for details.</p>` +
          `</body></html>`,
        );
      } else {
        res.status(503).send(
          `<!doctype html><html><head><title>Marimo not running</title></head><body>` +
          `<h2>Marimo is not running</h2>` +
          `<p>Enable the plugin in the <a href="${adminUrl}">SignalK admin panel</a>.</p>` +
          `</body></html>`,
        );
      }
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

    const notebookPath =
      options.notebookPath?.trim() ||
      path.join(app.getDataDirPath(), 'notebooks', 'signalk.py');

    const templateDir = path.join(__dirname, 'notebooks');
    try {
      MarimoManager.ensureNotebook(notebookPath, templateDir);
    } catch (err) {
      setPhase('error', String(err));
      app.setPluginError(`Notebook setup failed: ${err}`);
      return;
    }

    const serverPort: number = app.getPort?.() ?? 3000;
    const signalkUrl = options.signalkUrl?.trim() || `http://localhost:${serverPort}`;
    const venvDir = path.join(app.getDataDirPath(), '.venv');

    setPhase('installing');
    app.setPluginStatus('Installing Python dependencies…');
    try {
      await MarimoManager.ensureDeps(venvDir, log);
    } catch (err) {
      setPhase('error', String(err));
      app.setPluginError(`Dependency setup failed: ${err}`);
      return;
    }

    marimo = new MarimoManager();

    setPhase('starting');
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
          if (marimo) {
            setPhase('error', `Marimo exited unexpectedly (code ${code})`);
            app.setPluginError(`Marimo exited unexpectedly (code ${code})`);
          }
        },
      );
    } catch (err) {
      setPhase('error', String(err));
      app.setPluginError(String(err));
      return;
    }

    setPhase('running');
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
    setPhase('idle');
    app.setPluginStatus('Stopped');
  };

  return plugin;
};

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
