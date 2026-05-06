import { spawn, ChildProcess, spawnSync, execSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as http from 'http';

export interface MarimoConfig {
  port: number;
  notebookPath: string;
  signalkUrl: string;
  provider: string;
  token?: string;
  mode: 'edit' | 'run';
  venvDir: string;
}

const DEPS = ['marimo[recommended]', 'niquests'];

export class MarimoManager {
  private process: ChildProcess | null = null;

  private static venvBin(venvDir: string, name: string): string {
    return process.platform === 'win32'
      ? path.join(venvDir, 'Scripts', `${name}.exe`)
      : path.join(venvDir, 'bin', name);
  }

  /**
   * Ensure the plugin's Python venv exists with required deps installed.
   *
   * Strategy: always use uv for the heavy install (much faster than pip on
   * slow hardware). If uv isn't in the system PATH, we pip-install it into
   * the venv first — it's a small self-contained binary and pip only touches
   * it once.
   *
   * Re-runs install only when the dep list changes (tracked via sentinel file).
   * Returns a Promise — does NOT block the event loop.
   */
  static async ensureDeps(venvDir: string, log: (msg: string) => void): Promise<void> {
    const pythonBin = MarimoManager.venvBin(venvDir, 'python');
    const pipBin    = MarimoManager.venvBin(venvDir, 'pip');
    const uvBin     = MarimoManager.venvBin(venvDir, 'uv');
    const depsKey   = DEPS.join('\n');
    const sentinel  = path.join(venvDir, '.signalk-deps');

    const alreadyInstalled =
      fs.existsSync(pythonBin) &&
      fs.existsSync(sentinel) &&
      fs.readFileSync(sentinel, 'utf-8') === depsKey;

    if (alreadyInstalled) return;

    const hasSystemUv = !spawnSync('uv', ['--version'], { stdio: 'ignore' }).error;

    // Create venv if it doesn't exist yet
    if (!fs.existsSync(pythonBin)) {
      if (hasSystemUv) {
        log('Creating venv (uv)…');
        await runCmd('uv', ['venv', venvDir], log);
      } else {
        log('Creating venv (python3)…');
        await runCmd('python3', ['-m', 'venv', venvDir], log);
      }
    }

    // Resolve which uv to use: system → venv → bootstrap via pip
    let uv: string;
    if (hasSystemUv) {
      uv = 'uv';
    } else if (fs.existsSync(uvBin)) {
      uv = uvBin;
    } else {
      log('Bootstrapping uv for fast installs (one-time)…');
      await runCmd(pipBin, ['install', '--quiet', 'uv'], log);
      uv = uvBin;
    }

    log(`Installing ${DEPS.join(', ')} …`);
    await runCmd(uv, ['pip', 'install', '--python', pythonBin, ...DEPS], log);

    fs.writeFileSync(sentinel, depsKey);
    log('Python dependencies ready.');
  }

  /** Return the marimo executable, preferring the managed venv. */
  static findMarimo(venvDir: string): string {
    const marimoBin = MarimoManager.venvBin(venvDir, 'marimo');
    if (fs.existsSync(marimoBin)) return marimoBin;

    for (const candidate of ['marimo', 'python3 -m marimo', 'python -m marimo']) {
      try {
        execSync(`${candidate.split(' ')[0]} --version`, { stdio: 'ignore' });
        return candidate;
      } catch {
        // try next
      }
    }
    throw new Error(
      'marimo not found. Run the plugin once to auto-install, or: pip install "marimo[recommended]" niquests',
    );
  }

  /** Ensure the user's notebook file exists, seeding from the bundled template. */
  static ensureNotebook(notebookPath: string, templateDir: string): void {
    if (fs.existsSync(notebookPath)) return;

    const dir = path.dirname(notebookPath);
    fs.mkdirSync(dir, { recursive: true });

    const template = path.join(templateDir, 'signalk.py');
    if (!fs.existsSync(template)) {
      throw new Error(`Notebook template not found at ${template} — reinstall the plugin.`);
    }
    fs.copyFileSync(template, notebookPath);
  }

  /**
   * Spawn marimo and wait until its HTTP server is accepting connections.
   *
   * Rejects immediately if the process exits before becoming ready (includes
   * the last lines of its output so the caller can surface a useful error).
   * After becoming ready, calls onUnexpectedExit if the process later dies.
   */
  async start(
    config: MarimoConfig,
    log: (msg: string) => void,
    onUnexpectedExit?: (code: number | null) => void,
  ): Promise<void> {
    const marimoBin = MarimoManager.findMarimo(config.venvDir);

    const args = [
      config.mode,
      config.notebookPath,
      '--host', '0.0.0.0',
      '--port', String(config.port),
      '--no-token',
    ];

    const env: NodeJS.ProcessEnv = {
      ...process.env,
      SIGNALK_URL: config.signalkUrl,
      SIGNALK_PROVIDER: config.provider,
      ...(config.token ? { SIGNALK_TOKEN: config.token } : {}),
      MARIMO_SKIP_UPDATE_CHECK: '1',
    };

    log(`Starting marimo ${config.mode}: ${marimoBin} ${args.join(' ')}`);

    return new Promise((resolve, reject) => {
      const proc = spawn(marimoBin, args, { env, stdio: ['ignore', 'pipe', 'pipe'] });

      const tail: string[] = [];
      const collectAndLog = (d: Buffer) => {
        for (const line of d.toString().trimEnd().split('\n')) {
          if (!line.trim()) continue;
          log(line);
          tail.push(line);
          if (tail.length > 30) tail.shift();
        }
      };
      proc.stdout?.on('data', collectAndLog);
      proc.stderr?.on('data', collectAndLog);

      let ready = false;

      proc.on('exit', (code) => {
        this.process = null;
        if (!ready) {
          const context = tail.slice(-8).join('\n');
          reject(new Error(`Marimo exited (code ${code}) before becoming ready.\n${context}`));
        } else {
          onUnexpectedExit?.(code);
        }
      });

      proc.on('error', (err) => {
        if (!ready) reject(err);
      });

      const deadline = Date.now() + 60_000;
      const poll = () => {
        if (proc.killed || !proc.pid) return;

        const req = http.get(`http://127.0.0.1:${config.port}/`, (res) => {
          res.resume();
          ready = true;
          this.process = proc;
          resolve();
        });
        req.setTimeout(1000, () => req.destroy());
        req.on('error', () => {
          if (proc.killed || !proc.pid) return;
          if (Date.now() >= deadline) {
            const context = tail.slice(-8).join('\n');
            reject(new Error(`Marimo did not start on port ${config.port} within 60s.\n${context}`));
          } else {
            setTimeout(poll, 1000);
          }
        });
      };

      setTimeout(poll, 500);
    });
  }

  stop(): void {
    this.process?.kill('SIGTERM');
    this.process = null;
  }

  get running(): boolean {
    return this.process !== null;
  }
}

function runCmd(bin: string, args: string[], log: (msg: string) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, { stdio: ['ignore', 'pipe', 'pipe'] });

    child.stdout?.on('data', (d: Buffer) => {
      for (const line of d.toString().trimEnd().split('\n')) {
        if (line.trim()) log(line);
      }
    });
    child.stderr?.on('data', (d: Buffer) => {
      for (const line of d.toString().trimEnd().split('\n')) {
        if (line.trim()) log(line);
      }
    });

    child.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${path.basename(bin)} exited with code ${code}`));
    });
    child.on('error', reject);
  });
}
