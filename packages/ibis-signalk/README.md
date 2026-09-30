# SignalK Data Lab

An experimental data notebook environment for SignalK, using [Marimo](https://marimo.io) notebooks for exploration and analysis of SignalK History API data.

While Marimo could run on the SignalK server, or on cloud, this implementation chooses to use them in WASM mode (using `pyoxide`), where they run _entirely_ within the web browser, so that the only strain on the boat's SignalK server is supplying the static resources when the web app is loading, and running the History API queries.

It's also possible to wire these notebooks up directly to your actual back-end Parquet, QuestDB, InfluxDB etc however this implementation chooses to use the general SignalK [History API](https://demo.signalk.org/documentation/Developing/REST_APIs/History_API.html).

## An Alternative at the Command Line

A less experimental command line alternative is available, [signalk-cli](https://signalk-cli.rhizomatics.org.uk) - this lets you analyze, explore and extract both streaming deltas and History API data and export to console, JSON or Apache Arrow dataframes.

## SignalK Data Access

There are three notebooks provided with two different approaches. There are links within each notebook to switch between them within the app.

### Default Data Lab Notebook

The simplest, and easiest to make work, approach uses `polara` dataframe in Python to pull in the History API data and turn it into dataframes. Once in a dataframe ( how data notebooks usually like their data ), there are then unlimited ways to analyze and manipulate that data using `polars`, Marimo UI widgets, or third party libraries (within the limitations of what can be imported within a `pyxoide` environment).

### Data Source Explorer Notebook

This notebook is able to bring SignalK data into the visual data browser environment of Marimo, in the same way that a traditional database could be browsed in the app. To do that, it uses a very alpha package included inside this plugin called [`ibis-signalk`](#ibis-signalk), which has a minimal set of database wrapping around the SignalK APIs.

### Third Option - signalk-cli as a Library

The `signalk-cli` package can also be used as a library, and has some useful features like metrics handling and path wildcarding that make more practical use of SignalK data, and has direct dataframe output.

## ibis-signalk

An [Ibis Framework](https://ibis-project.org) backend for the [SignalK](https://signalk.org/) History API. Lets Marimo's Data Sources panel (and plain Ibis code) browse, query and extract SignalK history data with aggregation and resolution pushed down to the server — no local storage, no DuckDB import step.

See `../../planning/data_connectivity.md` in the parent repo for the design notes.

## Local dev

Iterate against a real SignalK server (no browser/WASM round-trip needed):

```sh
cd packages/ibis-signalk
SIGNALK_URL=http://<boat-host>:<port> uv run marimo edit notebooks/dev.py
```

`SIGNALK_URL` defaults to `http://localhost:3000`, the same as the main Data Lab notebook. The history provider defaults to the first one that isn't Kip; pass `provider=` to `do_connect()` to choose another.

## How queries run

Column selection, timestamp range filters and time-bucketed aggregates (`by=t.timestamp.truncate("h")` with mean/min/max/first/last) compile to a single History API request, so the server does the work.

Overall aggregates, such as `t.col.mean()`, `t.count()`, and the column stats marimo's data browser shows, fetch the rows for the query's time range and are computed with pyarrow. Sorting and `limit()` are applied to the fetched rows too. Without a timestamp filter, the range is the last hour (`do_connect(..., default_duration=...)`).

Anything else, such as joins or the histograms marimo's data browser draws, raises `NotImplementedError` unless the optional DuckDB extra is installed:

```sh
uv sync --extra duckdb   # in packages/ibis-signalk
```

With DuckDB installed, those queries fetch the table's rows for the time range and run locally in DuckDB. marimo's data browser works either way; without DuckDB it just leaves out the histograms. The `dev` dependency group includes DuckDB, so `uv run` and `npm run lab` have it.
