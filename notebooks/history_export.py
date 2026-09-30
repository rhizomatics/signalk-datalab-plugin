import marimo

__generated_with = "0.25.0"
app = marimo.App(width="full", app_title="signalk-cli Based Data Access")

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
    # signalk-cli Data Access

    Fetch SignalK history into a [polars](https://pola.rs) DataFrame with the
    [signalk-cli](https://signalk-cli.rhizomatics.org.uk) Python API, then analyse
    it in the notebook, for example charting how much the boat's position moved.
    You can also download the data as Feather or CSV, matching the CLI's output.

    Cells run automatically as you change the inputs. If any look stale or empty,
    press **Run** (▶) at the bottom right of the page.

    **Limitations**

    - In the browser, signalk-cli's requests go through niquests and
    urllib3-future, forks of requests and urllib3 maintained mainly by one
    developer, whose WebAssembly support is what makes this work.
    - The whole time range is fetched into browser memory, so long ranges with
    many paths are slow.
    - Polars in the browser is a WebAssembly build from a one-person project
    ([xlwings/polars-pyodide](https://github.com/xlwings/polars-pyodide)), not the
    polars team, and trails the desktop release (1.33 against 1.44 in September
    2026), so newer features and some bug fixes are missing. Other compiled
    libraries, such as pyarrow, numpy and pandas, lag behind in the same way. This notebook works
    around one such bug, with string columns.
    - signalk-cli's streaming client doesn't suit the browser; see
    [Live Stream](live_stream.html) for live data.

    Other experiments to try:

    - [Data Lab](index.html) for picking paths and dates and getting
    a DataFrame back
    - [Data Source Explorer](data_source_explorer.html) for
    browsing history in marimo's data browser or querying it with Ibis
    - [SQL with DuckDB](sql_duckdb.html) for querying history with SQL
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
    history_output = _importlib.import_module("signalk_cli.history.output")
    return history_output, signalk_cli, signalk_url


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
    fetch_btn = mo.ui.run_button(label="Fetch")
    mo.vstack([
        mo.md(f"""
        **History API Server** `{signalk_url}`

        Paths are comma-separated, and can be glob or regex patterns, e.g.
        `navigation.*` or `environment.wind.*`. Include `navigation.position`
        for the chart below.
        """),
        mo.hstack([provider_input, duration_input], justify="start", gap="1.5rem"),
        paths_input,
        fetch_btn,
    ])
    return duration_input, fetch_btn, paths_input, provider_input


@app.cell(hide_code=True)
def _(
    duration_input,
    fetch_btn,
    paths_input,
    provider_input,
    signalk_cli,
    signalk_url,
):
    mo.stop(not fetch_btn.value, mo.callout(mo.md("Press **Fetch** to load."), kind="info"))

    _patterns = [p.strip() for p in paths_input.value.split(",") if p.strip()]
    try:
        with signalk_cli.HistoryClient(signalk_url, provider=provider_input.value) as _client:
            history_result = _client.values(
                _patterns, signalk_cli.TimeRange(duration=duration_input.value)
            )
    except ValueError:
        mo.stop(True, mo.callout(mo.md("No paths matched."), kind="warn"))
    except signalk_cli.SignalKError as _e:
        mo.stop(True, mo.callout(mo.md(f"**Fetch failed**: {_e}"), kind="danger"))

    # Wide shape: min_value/avg_value/max_value per number path, and
    # longitude/latitude columns for navigation.position
    # Rebuild the string columns in polars: Pyodide's polars 1.33 can't pass
    # on strings it imported from Arrow (to_arrow() panics), which breaks
    # DuckDB and anything else that reads the frame as Arrow. Fixed in polars
    # 1.38 (pola-rs/polars#26328); remove once Pyodide ships 1.38 or later
    history_df = pl.DataFrame(history_result.to_arrow()).with_columns(pl.col(pl.String) + "")

    mo.vstack([
        mo.md(f"**{history_df.height:,}** rows from {len(history_result.paths)} path(s)"),
        mo.ui.table(history_df),
    ])
    return history_df, history_result


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Position spread

    How much the boat moved in each 15 minutes: the standard deviation of latitude
    and longitude within each window, in metres. Near zero when moored, a few
    metres at anchor, and large when under way.
    """)
    return


@app.cell
def _(history_df):
    _has_position = {"latitude", "longitude"} <= set(history_df.columns)
    _positions = (
        history_df.filter(pl.col("path") == "navigation.position").drop_nulls(["latitude", "longitude"])
        if _has_position
        else history_df.clear()
    )
    mo.stop(
        _positions.is_empty(),
        mo.callout(mo.md("No `navigation.position` data in this fetch."), kind="info"),
    )

    # Degrees to metres: a degree of latitude is ~111 km everywhere, a degree
    # of longitude shrinks with the cosine of the latitude
    _M_PER_DEGREE = 111_320
    position_spread = (
        _positions.sort("timestamp")
        .group_by_dynamic("timestamp", every="15m")
        .agg(
            (pl.col("latitude").std() * _M_PER_DEGREE).alias("latitude"),
            (
                pl.col("longitude").std()
                * _M_PER_DEGREE
                * pl.col("latitude").mean().radians().cos()
            ).alias("longitude"),
        )
    )

    alt.Chart(
        position_spread.unpivot(
            index="timestamp", variable_name="axis", value_name="metres"
        )
    ).mark_line(point=True).encode(
        x=alt.X("timestamp:T", title="Time"),
        y=alt.Y("metres:Q", title="Standard deviation (m)"),
        color=alt.Color("axis:N", title=None),
        tooltip=["timestamp:T", "axis:N", alt.Tooltip("metres:Q", format=".1f")],
    ).properties(width="container", height=300)
    return (position_spread,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Export

    Download the fetched data. Both files have the same columns as the table
    above, as `signalk_cli.history query` writes them.
    """)
    return


@app.cell(hide_code=True)
def _(history_df, history_output, history_result):
    import io as _io

    _csv = _io.StringIO()
    _write_csv = history_output.write_csv_wide if history_result.wide else history_output.write_csv
    _write_csv(history_result.payload, _csv, no_header=False)

    # polars writes Arrow IPC (Feather v2) itself, so pyarrow isn't needed
    _feather = _io.BytesIO()
    history_df.write_ipc(_feather, compat_level=pl.CompatLevel.oldest())

    mo.hstack([
        mo.download(_feather.getvalue(), filename="signalk-history.feather", label="Download Feather"),
        mo.download(_csv.getvalue().encode(), filename="signalk-history.csv", label="Download CSV"),
    ], justify="start")
    return


if __name__ == "__main__":
    app.run()
