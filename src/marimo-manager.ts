import { spawn, ChildProcess, execSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export interface MarimoConfig {
  port: number;
  notebookPath: string;
  signalkUrl: string;
  provider: string;
  token?: string;
  mode: 'edit' | 'run';
}

export class MarimoManager {
  private process: ChildProcess | null = null;

  /** Resolve the marimo executable, preferring a venv if present. */
  static findMarimo(): string {
    // Check for marimo in common locations
    for (const candidate of ['marimo', 'python3 -m marimo', 'python -m marimo']) {
      try {
        const bin = candidate.split(' ')[0];
        execSync(`${bin} --version`, { stdio: 'ignore' });
        return candidate;
      } catch {
        // try next
      }
    }
    throw new Error(
      'marimo not found. Install it with: pip install marimo polars httpx\n' +
      'See https://marimo.io for details.',
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

  async start(config: MarimoConfig, log: (msg: string) => void): Promise<void> {
    const marimo = MarimoManager.findMarimo();
    const [bin, ...binArgs] = marimo.split(' ');

    const args = [
      ...binArgs,
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
      // suppress marimo's update-check network call
      MARIMO_SKIP_UPDATE_CHECK: '1',
    };

    log(`Starting marimo ${config.mode}: ${bin} ${args.join(' ')}`);

    this.process = spawn(bin, args, { env, stdio: ['ignore', 'pipe', 'pipe'] });

    this.process.stdout?.on('data', (d: Buffer) => {
      for (const line of d.toString().trimEnd().split('\n')) {
        if (line.trim()) log(line);
      }
    });
    this.process.stderr?.on('data', (d: Buffer) => {
      for (const line of d.toString().trimEnd().split('\n')) {
        if (line.trim()) log(line);
      }
    });

    this.process.on('exit', (code) => {
      log(`Marimo exited with code ${code}`);
      this.process = null;
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
