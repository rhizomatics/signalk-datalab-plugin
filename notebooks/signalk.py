import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full", app_title="SignalK Data Notebooks")

@app.cell(hide_code=True)
def _():
    import marimo as mo
    return mo

@app.cell(hide_code=True)
def _():# -> tuple[type[date], ModuleType, ModuleType, Any, ModuleType...:
    import polars as pl
    import json
    from datetime import date, timedelta
    from pyodide.http import pyfetch
    from urllib.parse import urlencode
    import js
    return date, js, json, pl, pyfetch, timedelta, urlencode


@app.cell(hide_code=True)
def _(js, mo):
    signalk_url = str(js.location.origin)
    mo.md(
        f"""
        # SignalK Data Notebooks
        **Server** `{signalk_url}`

        Select a provider and paths, set a date range, then press **Fetch data**.
        """
    )
    return (signalk_url,)


# ── Provider dropdown ─────────────────────────────────────────────────────────
@app.cell(hide_code=True)
async def _(json, mo, pyfetch, signalk_url):
    try:
        _resp = await pyfetch(
            f"{signalk_url}/signalk/v2/api/history/_providers",
            credentials="include",
        )
        _data = json.loads(await _resp.string())
        _provider_options = list(_data.keys()) if isinstance(_data, dict) else _data
    except Exception:
        _provider_options = []

    provider_input = mo.ui.dropdown(
        options=_provider_options,
        value=_provider_options[0] if _provider_options else None,
        label="Provider",
    )
    return (provider_input,)


# ── Path multiselect — /v2/api/history/paths ──────────────────────────────────
@app.cell(hide_code=True)
async def _(json, mo, pyfetch, provider_input, signalk_url, urlencode):
    _available_paths = []
    if provider_input.value:
        try:
            _qs = urlencode({"provider": provider_input.value, "duration": "P1D"})
            _resp = await pyfetch(
                f"{signalk_url}/signalk/v2/api/history/paths?{_qs}",
                credentials="include",
            )
            _available_paths = sorted(json.loads(await _resp.string()))
        except Exception:
            pass

    _defaults = [
        "navigation.speedOverGround",
        "navigation.courseOverGroundTrue",
        "navigation.position",
    ]

    if _available_paths:
        paths_input = mo.ui.multiselect(
            options=_available_paths,
            value=[p for p in _defaults if p in _available_paths],
            label="Paths",
        )
    else:
        paths_input = mo.ui.text_area(
            value="\n".join(_defaults),
            label="Paths (one per line — no data found for last 24 h)",
            rows=5,
        )
    return (paths_input,)


# ── Date range + fetch button ─────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(date, mo, timedelta):
    _today = date.today()
    _yesterday = _today - timedelta(days=1)
    from_date = mo.ui.date(value=_yesterday, label="From")
    to_date = mo.ui.date(value=_today, label="To")
    fetch_btn = mo.ui.run_button(label="Fetch data")
    return fetch_btn, from_date, to_date


# ── Layout ────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(fetch_btn, from_date, mo, paths_input, provider_input, to_date):
    mo.vstack(
        [
            mo.hstack([provider_input, from_date, to_date], gap="1.5rem", align="end"),
            paths_input,
            fetch_btn,
        ],
        gap="0.75rem",
    )
    return


# ── Data fetch — /v2/api/history/values ───────────────────────────────────────
@app.cell
async def _(
    fetch_btn,
    from_date,
    json,
    mo,
    paths_input,
    pyfetch,
    pl,
    provider_input,
    signalk_url,
    to_date,
    urlencode,
):
    _empty = pl.DataFrame({
        "timestamp": pl.Series([], dtype=pl.Datetime),
        "value": pl.Series([], dtype=pl.Float64),
        "method": pl.Series([], dtype=pl.Utf8),
        "context": pl.Series([], dtype=pl.Utf8),
    })
    signalk_data = _empty
    tables = {}

    mo.stop(
        not fetch_btn.value,
        mo.callout(mo.md("Press **Fetch data** above to load."), kind="info"),
    )

    _paths = (
        paths_input.value
        if isinstance(paths_input.value, list)
        else [p.strip() for p in paths_input.value.splitlines() if p.strip()]
    )

    _params = {
        "paths": ",".join(_paths),
        "from": f"{from_date.value.isoformat()}T00:00:00Z",
        "to": f"{to_date.value.isoformat()}T23:59:59Z",
    }
    if provider_input.value:
        _params["provider"] = provider_input.value

    _raw = {}
    try:
        _url = f"{signalk_url}/signalk/v2/api/history/values?{urlencode(_params)}"
        _resp = await pyfetch(_url, credentials="include")
        _raw = json.loads(await _resp.string())
    except Exception as _e:
        mo.stop(True, mo.callout(mo.md(f"**Fetch failed**: {_e}"), kind="danger"))

    _context = _raw.get("context", "")
    _path_meta = _raw.get("values", [])
    _data_rows = _raw.get("data", [])
    _long_rows: list[dict] = []

    for _i, _meta in enumerate(_path_meta):
        _path = _meta.get("path", f"path_{_i}")
        _tname = _path.replace(".", "_")
        _method = _meta.get("method", "")

        _path_rows = [
            {
                "timestamp": _row[0],
                "value": float(_row[_i + 1]) if _row[_i + 1] is not None else None,
                "method": _method,
                "context": _context,
            }
            for _row in _data_rows
            if len(_row) > _i + 1
        ]
        _long_rows.extend(
            {"timestamp": r["timestamp"], "path": _path, "value": r["value"],
             "method": r["method"], "context": r["context"]}
            for r in _path_rows
        )

        tables[_tname] = (
            pl.DataFrame(_path_rows)
            .with_columns([
                pl.col("timestamp").str.to_datetime(strict=False, time_unit="us"),
                pl.col("value").cast(pl.Float64, strict=False),
            ])
            if _path_rows else _empty
        )

    if _long_rows:
        signalk_data = (
            pl.DataFrame(_long_rows)
            .with_columns([
                pl.col("timestamp").str.to_datetime(strict=False, time_unit="us"),
                pl.col("value").cast(pl.Float64, strict=False),
            ])
        )

    mo.vstack([
        mo.md(
            f"Loaded **{len(tables)}** path(s): "
            + ", ".join(f"`{t}`" for t in tables)
            + f"  ·  **{len(_long_rows):,}** total rows"
        ),
        signalk_data,
    ])
    return signalk_data, tables


@app.cell
def _(mo):
    mo.md("""
    ---
    ## Analysis

    Add cells below. Each named path is also available as its own DataFrame
    in the `tables` dict — e.g. `tables["navigation_speedOverGround"]`.

    ```python
    # Example: speed in knots
    sog = tables["navigation_speedOverGround"]
    sog.with_columns((pl.col("value") * 1.94384).alias("knots"))
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
