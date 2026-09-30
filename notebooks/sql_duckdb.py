import marimo

__generated_with = "0.25.0"
app = marimo.App(width="full", app_title="SQL with DuckDB", sql_output="native")

with app.setup(hide_code=True):
    import marimo as mo
    import altair as alt
    import polars as pl

    # Displaying UTC timestamps needs the tzdata package, which Pyodide only
    # loads when it sees it imported
    try:
        import tzdata  # noqa: F401
    except ImportError:
        pass


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # SQL with DuckDB

    Query SignalK history with SQL, using [DuckDB](https://duckdb.org) running in
    your browser. The history is fetched into a table called `signalk_history`, and
    the SQL cells below show what DuckDB does well with boat data: lining up sensors
    that report at different rates, bucketing by time, pivoting, and window
    functions. Edit any of them, or add your own SQL cell with the **SQL** button
    under a cell.

    DuckDB and its dependencies are about 28 MB, so the first visit takes a while
    to load. Your browser keeps them for next time.

    Cells run automatically as you change the inputs. If any look stale or empty,
    press **Run** (▶) at the bottom right of the page.

    **Limitations**

    - DuckDB in the browser is Pyodide's build, which trails the desktop release
    (1.5.1 against 1.5.6 in September 2026) and runs on a single thread. DuckDB
    extensions, such as spatial, haven't been tried here and may not load.
    - The fetched history is held in browser memory, so very long ranges are slow.
    - In the browser, signalk-cli's requests go through niquests and
    urllib3-future, forks of requests and urllib3 maintained mainly by one
    developer, whose WebAssembly support is what makes this work.
    - Polars in the browser is a WebAssembly build from a one-person project
    ([xlwings/polars-pyodide](https://github.com/xlwings/polars-pyodide)), not the
    polars team, and trails the desktop release (1.33 against 1.44 in September
    2026), so newer features and some bug fixes are missing. Other compiled
    libraries, such as pyarrow, numpy and pandas, lag behind in the same way.

    Other experiments to try:

    - [Data Lab](index.html) for picking paths and dates and getting
    a DataFrame back
    - [Data Source Explorer](data_source_explorer.html) for browsing
    history in marimo's data browser or querying it with Ibis
    - [signalk-cli Data Access](history_export.html) for fetching with the
    `signalk-cli` Python API, charting position, and downloading Feather or CSV
    - [Live Stream](live_stream.html) for watching data arrive live.
    """)
    return


@app.cell(hide_code=True)
async def _():
    import importlib as _importlib
    import os as _os
    import sys as _sys

    if "pyodide" in _sys.modules:
        import js as _js
        import micropip as _micropip

        # signalk-cli's metadata leaves out zeroconf (mDNS discovery) under
        # Pyodide, so a plain install works
        with mo.status.spinner(title="Installing signalk-cli…"):
            await _micropip.install("signalk-cli>=3.0.0")
        signalk_url = str(_js.location.origin)
    else:
        signalk_url = _os.environ.get("SIGNALK_URL", "http://localhost:3000")

    # importlib so marimo doesn't try to auto-install signalk-cli from PyPI
    signalk_cli = _importlib.import_module("signalk_cli")
    return signalk_cli, signalk_url


@app.cell(hide_code=True)
def _(signalk_cli, signalk_url):
    try:
        with signalk_cli.HistoryClient(signalk_url, timeout=10) as _client:
            _provider_options = list(_client.providers())
    except signalk_cli.SignalKError:
        _provider_options = []

    # SignalK often marks Kip as the default provider, but it often holds little
    # history, so prefer the first provider that isn't Kip
    _preferred = [p for p in _provider_options if not p.lower().startswith("kip")]

    provider_input = mo.ui.dropdown(
        options=_provider_options,
        value=(_preferred or _provider_options or [None])[0],
        label="Provider",
    )
    duration_input = mo.ui.dropdown(
        options={
            "Last hour": "PT1H",
            "Last 6 hours": "PT6H",
            "Last 24 hours": "PT24H",
            "Last 7 days": "P7D",
        },
        value="Last 24 hours",
        label="Duration",
    )
    paths_input = mo.ui.text(
        value="navigation.*",
        label="Paths",
        full_width=True,
    )
    mo.vstack([
        mo.md(f"""
        **History API Server** `{signalk_url}`

        Paths are comma-separated, and can be glob or regex patterns, e.g.
        `navigation.*` or `environment.wind.*`. The examples below use
        `navigation.position` and `navigation.speedOverGround`.
        """),
        mo.hstack([provider_input, duration_input], justify="start", gap="1.5rem"),
        paths_input,
    ])
    return duration_input, paths_input, provider_input


@app.cell(hide_code=True)
def _(duration_input, paths_input, provider_input, signalk_cli, signalk_url):
    _patterns = [p.strip() for p in paths_input.value.split(",") if p.strip()]
    try:
        with mo.status.spinner(title="Fetching history…"):
            with signalk_cli.HistoryClient(signalk_url, provider=provider_input.value) as _client:
                _result = _client.values(
                    _patterns, signalk_cli.TimeRange(duration=duration_input.value)
                )
    except ValueError:
        mo.stop(True, mo.callout(mo.md("No paths matched."), kind="warn"))
    except signalk_cli.SignalKError as _e:
        mo.stop(True, mo.callout(mo.md(f"**Fetch failed**: {_e}"), kind="danger"))

    # Position and number columns only appear when those paths have data, so
    # add any that are missing to keep the example queries working
    # Rebuild the string columns in polars: Pyodide's polars 1.33 can't pass
    # on strings it imported from Arrow (to_arrow() panics), which DuckDB
    # needs to read the frame. Fixed in polars 1.38 (pola-rs/polars#26328);
    # remove once Pyodide ships 1.38 or later
    _df = pl.DataFrame(_result.to_arrow()).with_columns(pl.col(pl.String) + "")
    signalk_history = _df.with_columns(
        pl.lit(None, dtype=pl.Float64).alias(_c)
        for _c in ("latitude", "longitude", "min_value", "avg_value", "max_value")
        if _c not in _df.columns
    )

    mo.md(
        f"Fetched **{signalk_history.height:,}** rows from {len(_result.paths)} path(s) "
        "into `signalk_history`: one row per timestamp and path, with `avg_value` "
        "(and `min_value`, `max_value`) for numbers, and `latitude`, `longitude` "
        "for positions."
    )
    return (signalk_history,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## What's in the data

    A plain `GROUP BY`: how many readings each path has, and the time they cover.
    """)
    return


@app.cell
def _(signalk_history):
    path_summary = mo.sql(
        f"""
        SELECT
            path,
            count(*) AS readings,
            min(timestamp) AS first_reading,
            max(timestamp) AS last_reading
        FROM signalk_history
        GROUP BY path
        ORDER BY readings DESC
        """
    )
    return (path_summary,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## One column per path

    `time_bucket` averages each path over 15 minutes, and `PIVOT` turns the paths
    into columns, giving one row per 15 minutes. Speeds and angles are in SI units,
    metres per second and radians.
    """)
    return


@app.cell
def _(signalk_history):
    quarter_hours = mo.sql(
        f"""
        PIVOT (
            SELECT
                time_bucket(INTERVAL 15 MINUTE, timestamp) AS quarter_hour,
                path,
                avg_value
            FROM signalk_history
            WHERE avg_value IS NOT NULL
        )
        ON path
        USING avg(avg_value)
        ORDER BY quarter_hour
        """
    )
    return (quarter_hours,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Distance run

    Window functions compare each position fix with the one before it (`lag`), to
    work out the distance between them, the speed that implies, and a running
    total (`sum ... OVER`) in nautical miles.
    """)
    return


@app.cell
def _(signalk_history):
    distance_run = mo.sql(
        f"""
        WITH fixes AS (
            SELECT timestamp, latitude, longitude
            FROM signalk_history
            WHERE path = 'navigation.position' AND latitude IS NOT NULL
        ),
        legs AS (
            SELECT
                timestamp,
                latitude,
                longitude,
                111320 * sqrt(
                    pow(latitude - lag(latitude) OVER w, 2)
                    + pow((longitude - lag(longitude) OVER w) * cos(radians(latitude)), 2)
                ) AS metres,
                epoch(timestamp) - epoch(lag(timestamp) OVER w) AS seconds
            FROM fixes
            WINDOW w AS (ORDER BY timestamp)
        )
        SELECT
            timestamp,
            latitude,
            longitude,
            metres,
            metres / nullif(seconds, 0) * 1.94384 AS knots,
            sum(metres) OVER (ORDER BY timestamp) / 1852 AS distance_nm
        FROM legs
        ORDER BY timestamp
        """
    )
    return (distance_run,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Lining up sensors with `ASOF JOIN`

    Instruments report at different rates, so their timestamps rarely match.
    `ASOF JOIN` pairs each position fix with the latest speed over ground reported
    at or before it. The chart shows the track, coloured by speed.
    """)
    return


@app.cell
def _(signalk_history):
    track = mo.sql(
        f"""
        SELECT
            p.timestamp,
            p.latitude,
            p.longitude,
            s.avg_value * 1.94384 AS sog_knots
        FROM (
            SELECT timestamp, latitude, longitude
            FROM signalk_history
            WHERE path = 'navigation.position' AND latitude IS NOT NULL
        ) p
        ASOF LEFT JOIN (
            SELECT timestamp, avg_value
            FROM signalk_history
            WHERE path = 'navigation.speedOverGround'
        ) s
        ON p.timestamp >= s.timestamp
        ORDER BY p.timestamp
        """
    )
    return (track,)


@app.cell
def _(track):
    # SQL results are DuckDB relations (sql_output="native"), so queries can
    # build on each other inside DuckDB; convert to polars for charting
    _track = pl.DataFrame(track)
    mo.stop(_track.is_empty(), mo.callout(mo.md("No `navigation.position` data to plot."), kind="info"))
    alt.Chart(_track).mark_circle(size=12).encode(
        x=alt.X("longitude:Q", scale=alt.Scale(zero=False), title="Longitude"),
        y=alt.Y("latitude:Q", scale=alt.Scale(zero=False), title="Latitude"),
        color=alt.Color("sog_knots:Q", title="SOG (kn)", scale=alt.Scale(scheme="viridis")),
        tooltip=["timestamp:T", alt.Tooltip("sog_knots:Q", format=".1f")],
    ).properties(width="container", height=400)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Querying a file

    DuckDB can query CSV and Parquet files directly, for example a CSV downloaded
    from [signalk-cli Data Access](history_export.html) or exported by the
    `signalk-cli` command line tool.
    """)
    return


@app.cell(hide_code=True)
def _():
    upload = mo.ui.file(filetypes=[".csv", ".parquet"], label="Choose a CSV or Parquet file")
    upload
    return (upload,)


@app.cell
def _(upload):
    mo.stop(not upload.value)
    uploaded_path = f"/tmp/{upload.name()}"
    with open(uploaded_path, "wb") as _f:
        _f.write(upload.contents())
    return (uploaded_path,)


@app.cell
def _(uploaded_path):
    uploaded = mo.sql(
        f"""
        SELECT * FROM '{uploaded_path}' LIMIT 1000
        """
    )
    return (uploaded,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Your turn

    Change this query, or add SQL cells of your own. The result of every query
    above can be queried too, e.g. `SELECT max(distance_nm) FROM distance_run`.
    To work with a result in Python, convert it with `pl.DataFrame(distance_run)`.
    """)
    return


@app.cell
def _(signalk_history):
    _df = mo.sql(
        f"""
        SELECT * FROM signalk_history LIMIT 100
        """
    )
    return


if __name__ == "__main__":
    app.run()
