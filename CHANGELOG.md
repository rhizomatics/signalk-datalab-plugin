# What's Changed

> [!TIP]
> For the Marimo notebooks, see their [Release Notes](https://github.com/marimo-team/marimo/releases)

[0.3.0] - Sept 2026
## Dependencies
- Updated Marimo to latest version, [0.25.0](https://github.com/marimo-team/marimo/releases/tag/0.25.0)
## Notebook
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
## Development Use
- `build:wasm` now clears old build assets first, so stale files are no longer shipped in the package
- For local development, new `npm run preview` command to build and serve the WASM notebook locally, proxying API calls to a SignalK server set by `SIGNALK_URL` environment variable