# SignalK Data Lab

[![npm version](https://img.shields.io/npm/v/@rhizomatics/signalk-datalab-plugin.svg)](https://www.npmjs.com/package/@rhizomatics/signalk-datalab-plugin)
[![npm downloads](https://img.shields.io/npm/dm/@rhizomatics/signalk-datalab-plugin.svg)](https://www.npmjs.com/package/@rhizomatics/signalk-datalab-plugin)
[![code style: oxfmt](https://img.shields.io/badge/code_style-oxfmt-blue.svg)](https://github.com)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/rhizomatics/signalk-einklabel-plugin/blob/main/LICENSE)
[![boat tech directory](https://boat-tech-directory.rhizomatics.org.uk/images/badge.svg)](https://boat-tech-directory.rhizomatics.org.uk)

## BETA - Use with care

Data notebooks, using [Marimo](https://marimo.io) and Python for DAG aware notebooks. Notebooks run [entirely in the browser](https://docs.marimo.io/guides/wasm/), using WebAssembly (WASM) to keep the server load minimal and best suited to Raspberry Pi, NanoPi etc servers.

It comes with several _experiments_, working notebooks that use different ways to pull selected paths out of the SignalK History API and demonstration of how the data can be tabluated, charted or otherwise analyzed.

> [!NOTE]
> Whilst this all runs in the browser, the Marimo environment will also run server-side, so this may be an option in future with this plugin, or packaged as a separate plugin. The main up-side of running server-side is not being constrained by using `pyodide` to run Python in the browser, which means latest versions of `polars`,`duckdb` etc are available and fewer gotchas.

## Running from SignalK

- Install from the SignalK **App Store**
- Launch the _Data Lab_ from the **Webapps** link on SignalK main menu

You'll need a _History Provider_ running to capture the SignalK data, such as **signalk-parquet**, **signalk-to-influxdb2** or **signalk-questdb**. If you have **Kip** set up as a plotter, it can also act as a history provider. Without one of these, there's nothing to be queried for data, only raw data files.

> [!TIP]
> If you're not familiar with Data Notebooks, try the [Marimo Tutorials](https://www.youtube.com/@marimo-team) on YouTube, or the [gallery](https://marimo.io/gallery) of demonstration notebooks. If you're familiar with Jupyter, you'll feel at home, although Marimo Notebooks are nicer!

> [!WARNING]
> Libraries with compiled code (polars, DuckDB, pyarrow, numpy, pandas and others) run in the browser only as special WebAssembly builds, which usually trail the desktop releases, sometimes by many months. In September 2026, polars in the browser is 1.33 while desktop is 1.44, and pyarrow is 22 against 25. So the browser can lack newer features, and occasionally has bugs that are long fixed on desktop. Code that works in a desktop notebook may fail in Data Lab, and the reverse. This will ease as more projects publish WebAssembly builds of their own. Pure Python libraries aren't affected.

## Simulating Data

SignalK has several _simulator_ plugins that will generate navigation, environment and similar data. Its also easy to source real live weather data using plugins.

### Ibis (experimental)

The **SignalK Paths in Data Explorer with Ibis** notebook, linked from the top of Data Lab, connects [Ibis](https://ibis-project.org) to the History API when it opens. You can then query SignalK data with Ibis expressions and browse it in marimo's data browser. It takes a few seconds to load the first time.

> [!WARNING]
> Histograms aren't shown in the data browser for SignalK tables by default. Column stats (counts, missing values, min/max, averages) work, but the charts that need histograms are left out. To turn them on, install `duckdb` from marimo's package manager panel; it's a sizeable download. Overall figures cover the last hour unless you filter on `timestamp`.

### Analyze and Export with signalk-cli

The **Analyze and Export with signalk-cli** notebook, linked from the top of Data Lab, fetches history into a polars DataFrame with the [signalk-cli](https://signalk-cli.rhizomatics.org.uk) Python API, and charts how much the boat's position moved in each 15 minutes. You can also download the data as Feather or CSV, in the same format as the `signalk-cli` command line tool. Paths can be glob or regex patterns, e.g. `navigation.*`.

> [!NOTE]
> It installs `signalk-cli` when it opens, which takes a few seconds the first time.

### SQL with DuckDB

The **SQL with DuckDB** notebook fetches history into a `signalk_history` table and queries it with SQL cells running [DuckDB](https://duckdb.org) in the browser. Worked examples cover time bucketing, `PIVOT`, window functions for distance run, and `ASOF JOIN` to line up sensors that report at different rates. It can also query an uploaded CSV or Parquet file.

> [!NOTE]
> DuckDB and the packages marimo loads alongside it are about 28 MB, so the first visit takes a while. The other notebooks don't load DuckDB.

### Live Stream With signalk-cli

The **Live Stream With signalk-cli** notebook subscribes to the SignalK delta stream and shows data as it arrives: a chart per path, redrawn every few seconds, and a table of the latest values. It uses the browser's own WebSocket, since signalk-cli's streaming client waits for each message in a way that would block the rest of the notebook in the browser. signalk-cli still builds the subscription and reads the messages. Only data received while the page is open is shown.

Each notebook's opening cell lists the limitations of its approach.

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

Every marimo notebook in `notebooks/` is included in the WASM build: `signalk.py` (Analyze with Polars Dataframes) becomes the main Data Lab page (`datalab.html`), and each other notebook becomes `<name>.html` alongside it, sharing the same assets. `index.html` is a gallery with a card per notebook, generated by `scripts/build-gallery.js` from each notebook's opening markdown cell (its `# heading` and first paragraph), so a new notebook appears there automatically. Link between them with relative links, e.g. `[SignalK Paths in Data Explorer with Ibis](data_source_explorer.html)`.

The signalk-cli notebooks install `signalk-cli>=3.0.0` in the browser with a plain `micropip.install`; its metadata leaves out `zeroconf` (mDNS discovery) under Pyodide. signalk-cli is exempt from the `exclude-newer` release cooldown, in both `uv.toml` and `packages/ibis-signalk/pyproject.toml` (which `npm run lab` runs under), so new releases of it can be used straight away.

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
