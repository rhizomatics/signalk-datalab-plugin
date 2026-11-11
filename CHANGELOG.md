> [!TIP]
> For the Marimo notebooks, see their [Release Notes](https://github.com/marimo-team/marimo/releases)

# v0.7.1 - Nov 2026

## 🐛 Bug fixes

- **SQL with DuckDB** crashed in Safari as soon as it ran ("Pyodide has suffered a fatal error ... basic_string", then "RPC request timed out"). The quarter-hour `PIVOT` now has its own cell: when it followed another statement in the same SQL cell, DuckDB threw an error while marimo read the SQL, which Chrome recovers from but Safari doesn't
- **SignalK Paths in Data Explorer with Ibis** and **Performance Polars** failed to install `ibis-signalk` in v0.7.0, as the plugin package was missing the wheel it serves them (`/wheels/index.json` not found)

## 📚 Documentation

- Corrected what HTTPS gives the notebooks: over plain `http` they work the same, but a running cell can't be interrupted. HTTP isn't what makes a first visit slow; downloading Python and the packages is

# v0.7.0 - Nov 2026

## ✨ Enhancements

- Every notebook opens with its code hidden, so the introduction and the **Fetch** controls are easy to find; open any cell to see or edit its code
- New **Performance Polars** notebook: a polar diagram of boat speed against true wind angle and speed from your own sailing, the best VMG angles upwind and downwind, and a `.pol` download for OpenCPN and other routing software, with demo data to try it out
- **SignalK Paths in Data Explorer with Ibis** shows the History API request each Ibis expression compiles to, with the server-side summary charted, and a heatmap of which instruments reported when

## 🐛 Bug fixes

- **SignalK Paths in Data Explorer with Ibis** failed to open in v0.6.0 ("Can't find a pure Python 3 wheel for 'pyarrow>=26.0.0'"): `ibis-signalk` 0.1.4 asks for no newer pyarrow and altair than the browser's Python (Pyodide) provides, and again requires `pyarrow-hotfix`, which ibis imports even though it does nothing on current pyarrow ("No module named 'pyarrow_hotfix'")
- **SignalK Paths in Data Explorer with Ibis** failed on a namespace with a text path, such as `navigation.datetime` from NMEA RMC sentences ("Could not convert ... to double"). Text paths such as times, states and modes are now text columns, objects such as `navigation.attitude` are JSON, and an unexpected text value in a numeric path becomes empty instead of failing the whole table
- **Analyze and Export with signalk-cli** and **SQL with DuckDB** showed every value as text when a text path such as `navigation.datetime` was fetched; numbers are numbers again, with the text in a new `text_value` column
- Positions from history providers that store them as two paths, `navigation.position.latitude` and `navigation.position.longitude`, now load in the signalk-cli, DuckDB and **Geospatial Passage** notebooks, instead of showing no position data
- **SignalK Paths in Data Explorer with Ibis**: "Last 7 days" now works with servers that only accept time durations

## 📚 Documentation

- Documentation re-organized, with improved AI agent instructions and screenshots
- SKsim recommended in the README for test data

# v0.6.0 - Nov 2026

## Marimo

Release v0.25.2 of Marimo adds geospatial support

> Geospatial dataframes (GeoPandas, Arrow, and DuckDB geometry) can now be downloaded as GeoJSON or GeoParquet, alongside the existing CSV, JSON, and Parquet options. Also works with mo.ui.table and mo.ui.dataframe.

## ✨ Enhancements

- New **Geospatial Passage** notebook: splits `navigation.position` history into legs and stops (with anchor swing circles), maps them over OpenStreetMap with OpenSeaMap seamarks, and downloads them as GeoJSON or GeoParquet using marimo 0.25.2's geospatial export, or as GPX for chart plotters

# v0.5.5 - Nov 2026

## 🐛 Bug fixes

- `ibis-signalk`: queries run locally in DuckDB (such as joins) kept their time filters, instead of falling back to the last hour
- `ibis-signalk`: the `[duckdb]` extra now installs `pytz`, which DuckDB needs to return timestamps

## 🔧 Maintenance

- Test suite for `ibis-signalk`, run offline against a stand-in History API, and by pre-commit (`prek`) whenever the package changes
- Pre-commit uses the installed (mise) node, rather than downloading its own, which failed when nodejs.org listed a pre-release as the latest

# v0.5.4 - Nov 2026

## ✨ Enhancements

- On SignalK server 2.31 or later, read-only users can open Data Lab from the plugin's own address (`/plugins/signalk-datalab-plugin/ui`), which sends the headers notebooks need to start quickly. Opening Data Lab from the **Webapps** menu now moves there automatically when it can.

## 📚 Documentation

- Documented the effect of `http` versus `https` on notebook start-up

## 🔧 Maintenance

- CI now also tests on armv7 (e.g. Cerbo GX), so the App Store shows it as supported
- `express` dependency capped below the next major version (`>=4 <6`)
- App Store screenshot resized to 1280x800

# v0.5.3 - Sept 2026

## ✨ Enhancements

- Added CORS headers for all local calls

# v0.5.2 - Sept 2026

## ✨ Enhancements

- Speed up data load with compression and caching of web assets (JS,CSS etc)

# v0.5.1 - Sept 2026

## ✨ Enhancements

- More improvements for faster page data load

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
