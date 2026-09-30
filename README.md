# SignalK Data Lab

[![npm version](https://img.shields.io/npm/v/@rhizomatics/signalk-datalab-plugin.svg)](https://www.npmjs.com/package/@rhizomatics/signalk-datalab-plugin)
[![npm downloads](https://img.shields.io/npm/dm/@rhizomatics/signalk-datalab-plugin.svg)](https://www.npmjs.com/package/@rhizomatics/signalk-datalab-plugin)
[![code style: oxfmt](https://img.shields.io/badge/code_style-oxfmt-blue.svg)](https://github.com)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/rhizomatics/signalk-einklabel-plugin/blob/main/LICENSE)
[![boat tech directory](https://boat-tech-directory.rhizomatics.org.uk/images/badge.svg)](https://boat-tech-directory.rhizomatics.org.uk)

## ALPHA - Use with care

Data notebooks, using [Marimo](https://marimo.io) and Python for DAG aware notebooks. Notebooks run entirely in the browser, using WebAssembly (WASM) to keep the server load minimal and best suited to Raspberry Pi, NanoPi etc servers.

Intention is to have these wired up by default to SignalK History API.

Packaged with example working notebooks that pull selected paths out of
the SignalK History API

## Running from SignalK

- Install from the SignalK **App Store**
- Launch the _Data Lab_ from the **Webapps** link on SignalK main menu

You'll need a _History Provider_ running to capture the SignalK data, such as **signalk-parquet**, **signalk-to-influxdb2** or **signalk-questdb**. If you have **Kip** set up as a plotter, it can also act as a history provider. Without one of these, there's nothing to be queried for data, only raw data files.

> [!TIP]
> If you're not familiar with Data Notebooks, try the [Marimo Tutorials](https://www.youtube.com/@marimo-team) on YouTube, or the [gallery](https://marimo.io/gallery) of demonstration notebooks. If you're familiar with Jupyter, you'll feel at home, although Marimo Notebooks are nicer!

### Ibis (experimental)

The **Data Source Explorer** notebook, linked from the top of Data Lab, connects [Ibis](https://ibis-project.org) to the History API when you turn on **Load Ibis backend**. You can then query SignalK data with Ibis expressions and browse it in marimo's data browser. It takes a few seconds to load the first time.

> [!WARNING]
> Histograms aren't shown in the data browser for SignalK tables by default. Column stats (counts, missing values, min/max, averages) work, but the charts that need histograms are left out. To turn them on, install `duckdb` from marimo's package manager panel; it's a sizeable download. Overall figures cover the last hour unless you filter on `timestamp`.

### signalk-cli Data Access

The **signalk-cli Data Access** notebook, linked from the top of Data Lab, fetches history with [signalk-cli](https://signalk-cli.rhizomatics.org.uk) and lets you download it as Feather or CSV, in the same format as the `signalk-cli` command line tool. Paths can be glob or regex patterns, e.g. `navigation.*`.

> [!NOTE]
> It installs `signalk-cli` and `pyarrow` when it opens, a download of about 10 MB, which takes a while the first time.

### Using an AI agent (advanced)

Marimo's **External agents** feature (a Labs feature, turned on in marimo's settings) can connect Claude Code, Codex, Gemini or OpenCode to the notebook in the browser. It needs a terminal command to start a bridge, so it's aimed at technical users for now:

```bash
npx stdio-to-ws "npx @zed-industries/claude-code-acp" --port 3017
```

The notebook connects to the bridge on the same host name it was loaded from (`ws://<host>:3017`). If you open Data Lab from another machine, e.g. `http://my-boat.local:3000`, the bridge has to run on the SignalK server, with Node and a logged-in Claude Code there. You may see file system errors when the agent tries to read or write files, as the browser notebook has no files on disk for it to work with.

For a fuller setup, where the agent edits the notebook file and can see its live outputs, see [Working with an AI agent](#working-with-an-ai-agent) under Development.

## Development

Development environment requirements.

### Linux Packages

- node
- librsvg2-bin

#### Also recommended

- [signalk-cli](https://signalk-cli.rhizomatics.org.uk) Python CLI for exploring and extracting streaming and history daya

### Local Execution

To run the notebook outside of SignalK / webbrowser context, use

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
marimo run notebooks/signalk.py
```

To work on both the main notebook and the [ibis-signalk](packages/ibis-signalk) `dev.py` notebook from one marimo server, use

```bash
SIGNALK_URL=http://my-boat.local:3000 npm run lab
```

marimo's home page lists both notebooks, and the environment has the packages each one needs.

#### Ibis and DuckDB

The `ibis-signalk` backend runs what it can on the SignalK server and computes simple overall figures (counts, sums, min/max, averages) locally with pyarrow. Queries beyond that, notably the histograms marimo's data browser draws and any joins, need a local query engine, which comes from the optional DuckDB extra (`ibis-signalk[duckdb]`).

- `npm run lab` and `packages/ibis-signalk`'s `uv run` include DuckDB (via the `dev` dependency group), so histograms work there.
- The browser notebook installs `ibis-signalk` without DuckDB, to keep loading fast, so histograms aren't shown for users running from SignalK unless they install `duckdb` from marimo's package manager. The backend checks for DuckDB on each query, so that takes effect without reloading.
- Without DuckDB, those queries raise `NotImplementedError` naming the extra. marimo catches these and just leaves the chart out.

See [packages/ibis-signalk/README.md](packages/ibis-signalk/README.md) for how queries are split between the server and local evaluation.

Every marimo notebook in `notebooks/` is included in the WASM build: `signalk.py` becomes the Data Lab entry page (`index.html`), and each other notebook becomes `<name>.html` alongside it, sharing the same assets. Link between them with relative links, e.g. `[Data Source Explorer](data_source_explorer.html)`.

`history_export.py` installs `signalk-cli` in the browser with `micropip.install("signalk-cli", deps=False)`, plus `click` and `niquests>=2.36.0` (the first with browser support). Its package metadata requires `zeroconf` for mDNS discovery, which has no browser build and isn't needed there; that requirement is intentionally left in place for desktop users. `npm run lab` includes `signalk-cli[feather]`.

To preview the WASM build in a browser, as SignalK would serve it, use

```bash
SIGNALK_URL=http://my-boat.local:3000 npm run preview
```

This builds `public/` and serves it on http://localhost:8080 (override with `PORT`), proxying `/signalk/*` API calls to `SIGNALK_URL` (default `http://localhost:3000`). Use `npm run preview:serve` to skip the rebuild.

### Working with an AI agent

> [!NOTE]
> This setup is for developers working from a clone of this repo. For connecting an agent to the notebook launched from the SignalK **Webapps** panel, see [Using an AI agent (advanced)](#using-an-ai-agent-advanced).

The notebooks are plain Python files, so any coding agent can edit them. The repo is set up for [Claude Code](https://claude.com/claude-code), which can also see the live notebook's outputs and errors.

1. Start the notebook with its agent connection enabled, pointing at your SignalK server:

   ```bash
   SIGNALK_URL=http://my-boat.local:3000 npm run agent
   ```

   This opens the notebook for editing on http://localhost:2718, reloads it whenever the file changes on disk, and serves a marimo MCP server at http://localhost:2718/mcp/server.

2. In another terminal in the repo, start Claude Code with `claude`. The MCP server is registered in [.mcp.json](.mcp.json), so the first time you'll be asked to approve the `marimo` server. Run `/mcp` to check it's connected.

3. Ask for changes in plain language, e.g. _"add a chart of wind speed against boat speed"_. Claude edits `notebooks/signalk.py`, the browser tab updates, and Claude can read back cell outputs and errors from the running notebook.

Project settings in [.claude/](.claude/) run `marimo check` after every notebook edit and feed any problems back to Claude. [notebooks/CLAUDE.md](notebooks/CLAUDE.md) covers marimo's rules and what works in the browser (WASM) build.

`npm run agent` turns off marimo's access token so the MCP URL stays the same between runs. It only listens on localhost, but don't run it on a shared machine.

### Release

```bash
git tag -f latest
npm publish --tag latest --access public
```

## Also Check

- [signalk-cli](https://pypi.org/project/signalk-cli/) - A Python based CLI for extracting data and exploring paths on the SignalK APIs, with output to CSV or Apache Arrow dataframe (Feather)
