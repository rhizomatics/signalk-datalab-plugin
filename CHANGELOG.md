> [!TIP]
> For the Marimo notebooks, see their [Release Notes](https://github.com/marimo-team/marimo/releases)

# v0.5.3 - Sept 2026

## ✨ Enhancements

- Added CORS headers for all local calls

# v0.5.2 - Sept 2026

## ✨ Enhancements

- Speed up data load with compression and caching of web assets (JS,CSS etc)

# v0.5.1 - Sept 2026

## ✨ Enhancements

- More improvemenets for faster page data load

# v0.5.0 - Sept 2026

## ✨ Enhancements

- New home page gallery, with a choice of the notebook experiments
- New documentary notebook to explain how to add your own notebooks to it (quite technical at present).
- Renamed the experiment notebooks to make clearer what they do

# v0.4.0 - Sept 2026

## ✨ Enhancements

## New Notebooks

- New SQL based experiment notebook using [DuckDb](https://duckdb.org)
- New **Live Stream** experiment notebook, to see charts update realtime with wind data (or whatever else you want)
  - Streams over the browser's WebSocket, with `signalk-cli` for subscriptions and parsing
  - Holds each value on the chart until the next reading, since SignalK only sends values when they change

## All Notebooks

- Each notebook opens with its purpose, a reminder to run cells, links to the other notebooks, and a **Limitations** section

## signalk-cli Notebook

- Use the new Python API introduced in 3.0.0 of `signalk_cli`
  - Removes the need for direct interaction with SignalK
  - Adds ability to return dataframe in-memory for zero-copy sharing with notebooks
- Installs `signalk-cli` straight from PyPI in the browser
- New position spread chart: standard deviation of latitude and longitude, in metres, per 15 minutes
- Feather export no longer needs `pyarrow`, saving about 10 MB of download

## Data Source Explorer Notebook

- Ibis loads when the notebook opens, replacing the **Load Ibis backend** switch

## 📚 Documentation

- README warning that compiled libraries (polars, pyarrow, DuckDB and others) trail their desktop releases in the browser
- Notebook AI assistant notes (`notebooks/CLAUDE.md`) on the browser's library versions and known bugs

## 📝 Other changes

### Development

- `npm run preview` forwards WebSocket connections, needed by the Live Stream notebook
- `npm run lab` uses `signalk-cli` 3.0 from PyPI, and `signalk-cli` is exempt from the `uv` release cooldown

## 🐛 Bug fixes

- Fix for nullable float64 values, for example querying tide heights
- Fix for tables with UTC timestamps failing to display in the browser, due to time zone info not being available
- Workaround for a crash in the browser's polars (1.33) when string columns from Arrow are passed on, for example to DuckDB. Fixed in polars 1.38, which Pyodide hasn't picked up yet

# v0.3.0 - Sept 2026

## ✨ Enhancements

## New Notebooks

- Fixes and improvements to main SignalK example notebook
- History provider now defaults to the first one that isn't Kip, in both the notebook and ibis-signalk
- New notebooks illustrating `signalk-cli` and `signalk-ibis` usage
  - New Data Source Explorer notebook (linked from Data Lab): choose namespaces and a duration, and each namespace appears in marimo's data browser as its own table, queryable with Ibis.
    - Loads the bundled `ibis-signalk` wheel on demand in the browser
  - New `signalk-cli` Data Access notebook: fetch history with signalk-cli, using path patterns, and download it as Feather or CSV
- The WASM build now includes every notebook in `notebooks/`, sharing one set of assets

## ibis-signalk

- Sends the chosen provider, fills in a missing time range (defaults to the last hour), and drops `httpx`: it uses `urllib` locally and the browser's own requests in WASM
- Overall aggregates, counts and column stats are computed locally from fetched rows, so marimo's data browser works on SignalK tables (without histograms). Histograms and joins need the optional DuckDB extra, included in the developer setup
- New `npm run lab` command to work on the main and ibis-signalk `dev.py` notebooks from one marimo server
- Overhaul of the experimental Ibis Framework `dev.py` notebook that integrates SignalK into the Marimo Data Browser

## AI Agents

- Updates for agent use
  - README notes on connecting an agent to the SignalK-hosted notebook with marimo's External agents (Labs) feature
  - New script for Claude to make checks after edits
  - Guidance for Claude on differences in working with notebooks in WASM (local browser) environment
  - New `npm run agent` command to open the notebook with marimo's MCP server, pre-registered for Claude Code in `.mcp.json`, and README steps for getting started

## 📝 Other changes

### Dependencies

- Updated Marimo to latest version, [0.25.0](https://github.com/marimo-team/marimo/releases/tag/0.25.0)

## Development Use

- `build:wasm` now clears old build assets first, so stale files are no longer shipped in the package
- For local development, new `npm run preview` command to build and serve the WASM notebook locally, proxying API calls to a SignalK server set by `SIGNALK_URL` environment variable
