import marimo

__generated_with = "0.9.0"
app = marimo.App(width="full", app_title="SignalK Data Notebooks")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import polars as pl
    import duckdb
    import os
    from datetime import date, timedelta

    import niquests as http_client
    return mo, pl, duckdb, os, date, timedelta, http_client


@app.cell(hide_code=True)
def _(mo, os):
    _url = os.environ.get("SIGNALK_URL", "http://localhost:3000")
    mo.md(
        f"""
        # SignalK Data Notebooks
        **Server** `{_url}`

        Select a provider and paths, set a date range, then press **Fetch data**.
        """
    )
    return


# ── Provider dropdown — populated from the history API ───────────────────────
@app.cell(hide_code=True)
def _(http_client, mo, os):
    _url = os.environ.get("SIGNALK_URL", "http://localhost:3000")
    _token = os.environ.get("SIGNALK_TOKEN", "")
    _headers = {"Authorization": f"Bearer {_token}"} if _token else {}

    try:
        _r = http_client.get(
            f"{_url}/signalk/v2/api/history/_providers",
            headers=_headers,
            timeout=10,
        )
        _r.raise_for_status()
        _provider_options = _r.json()
    except Exception:
        _provider_options = []

    _default = os.environ.get("SIGNALK_PROVIDER", "")
    provider_input = mo.ui.dropdown(
        options=_provider_options,
        value=_default if _default in _provider_options else (_provider_options[0] if _provider_options else None),
        label="Provider",
    )
    return provider_input,


# ── Path multiselect — re-fetched when provider changes ──────────────────────
@app.cell(hide_code=True)
def _(http_client, mo, os, provider_input):
    _url = os.environ.get("SIGNALK_URL", "http://localhost:3000")
    _token = os.environ.get("SIGNALK_TOKEN", "")
    _headers = {"Authorization": f"Bearer {_token}"} if _token else {}

    _available_paths = []
    if provider_input.value:
        try:
            _r = http_client.get(
                f"{_url}/signalk/v2/api/history/_providers/{provider_input.value}/paths",
                headers=_headers,
                timeout=10,
            )
            _r.raise_for_status()
            _available_paths = sorted(_r.json())
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
            label="Paths (one per line)",
            rows=5,
        )
    return paths_input,


# ── Date range + fetch button — independent of provider/paths ─────────────────
@app.cell(hide_code=True)
def _(mo, date, timedelta):
    _today = date.today()
    _yesterday = _today - timedelta(days=1)
    from_date = mo.ui.date(value=_yesterday, label="From")
    to_date = mo.ui.date(value=_today, label="To")
    fetch_btn = mo.ui.run_button(label="Fetch data")
    return from_date, to_date, fetch_btn


# ── Layout — displays all controls together ───────────────────────────────────
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


# ── Data fetch ────────────────────────────────────────────────────────────────
@app.cell
def _(
    duckdb,
    fetch_btn,
    from_date,
    http_client,
    mo,
    os,
    paths_input,
    pl,
    provider_input,
    to_date,
):
    _empty_schema = {"timestamp": pl.Utf8, "path": pl.Utf8, "value": pl.Float64, "source": pl.Utf8, "context": pl.Utf8}
    signalk_data = pl.DataFrame(_empty_schema)
    tables = {}

    mo.stop(
        not fetch_btn.value,
        mo.callout(mo.md("Press **Fetch data** above to load."), kind="info"),
    )

    _url = os.environ.get("SIGNALK_URL", "http://localhost:3000")
    _token = os.environ.get("SIGNALK_TOKEN", "")
    _headers = {"Authorization": f"Bearer {_token}"} if _token else {}

    _paths = (
        paths_input.value
        if isinstance(paths_input.value, list)
        else [p.strip() for p in paths_input.value.splitlines() if p.strip()]
    )
    _provider = provider_input.value or ""

    _params = [("path", p) for p in _paths]
    _params += [
        ("from", f"{from_date.value.isoformat()}T00:00:00Z"),
        ("to", f"{to_date.value.isoformat()}T23:59:59Z"),
    ]
    if _provider:
        _params.append(("provider", _provider))

    _raw = {}
    try:
        _r = http_client.get(
            f"{_url}/signalk/v1/history/values",
            params=_params,
            headers=_headers,
            timeout=60,
        )
        _r.raise_for_status()
        _raw = _r.json()
    except Exception as _e:
        mo.stop(True, mo.callout(mo.md(f"**Fetch failed**: {_e}"), kind="danger"))

    _context = _raw.get("context", "")
    _path_meta = _raw.get("values", [])
    _data_rows = _raw.get("data", [])

    _long_rows: list[dict] = []

    for _i, _meta in enumerate(_path_meta):
        _path = _meta.get("path", f"path_{_i}")
        _tname = _path.replace(".", "_")
        _source = ", ".join(str(s) for s in _meta.get("sources", []))

        _path_rows = [
            {
                "timestamp": _row[0],
                "value": float(_row[_i + 1]) if _row[_i + 1] is not None else None,
                "source": _source,
                "context": _context,
            }
            for _row in _data_rows
            if len(_row) > _i + 1
        ]
        _long_rows.extend(
            {"timestamp": r["timestamp"], "path": _path, "value": r["value"],
             "source": r["source"], "context": r["context"]}
            for r in _path_rows
        )

        _df = (
            pl.DataFrame(_path_rows)
            .with_columns([
                pl.col("timestamp").str.to_datetime(strict=False, time_unit="us"),
                pl.col("value").cast(pl.Float64, strict=False),
            ])
            if _path_rows
            else pl.DataFrame({"timestamp": [], "value": [], "source": [], "context": []})
        )

        tables[_tname] = _df
        duckdb.register(_tname, _df)

    if _long_rows:
        signalk_data = (
            pl.DataFrame(_long_rows)
            .with_columns([
                pl.col("timestamp").str.to_datetime(strict=False, time_unit="us"),
                pl.col("value").cast(pl.Float64, strict=False),
            ])
        )
    duckdb.register("signalk_data", signalk_data)

    mo.vstack([
        mo.md(
            f"Loaded **{len(tables)}** table(s): "
            + ", ".join(f"`{t}`" for t in tables)
            + f"  ·  **{len(_long_rows):,}** total rows"
        ),
        mo.md(
            "**Available tables** (query with `mo.sql` below):\n"
            + "\n".join(f"- `{t}` — {tables[t].height:,} rows" for t in tables)
        ),
    ])
    return signalk_data, tables


@app.cell
def _(mo, signalk_data):
    mo.md(f"""
    ---
    ## SQL Explorer

    The tables are available in `mo.sql()` cells. You have:

    - **`signalk_data`** — combined long-form table ({signalk_data.height:,} rows): `timestamp`, `path`, `value`, `source`, `context`
    - **individual path tables** — e.g. `navigation_speedOverGround`: `timestamp`, `value`, `source`, `context`

    Tip: double-click a cell header to sort, or drag to resize columns.
    """)
    return


@app.cell
def _(mo):
    _q1 = mo.sql("""
    -- Recent speed over ground
    SELECT
        timestamp,
        value  AS speed_ms,
        ROUND(value * 1.94384, 2) AS speed_kt
    FROM navigation_speedOverGround
    ORDER BY timestamp DESC
    LIMIT 200
    """)
    return (_q1,)


@app.cell
def _(mo):
    _q2 = mo.sql("""
    -- Summary statistics per path
    SELECT
        path,
        COUNT(*)                    AS n,
        ROUND(AVG(value), 4)        AS avg,
        ROUND(MIN(value), 4)        AS min,
        ROUND(MAX(value), 4)        AS max,
        MIN(timestamp)              AS first_ts,
        MAX(timestamp)              AS last_ts
    FROM signalk_data
    GROUP BY path
    ORDER BY path
    """)
    return (_q2,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ## Add your own queries

    Add new SQL cells with `mo.sql(\"...\")` or Python cells for custom analysis.
    All standard DuckDB SQL is supported — window functions, `unnest`, `read_parquet()`, etc.

    ```python
    # Example: per-minute average speed
    result = mo.sql(\"\"\"
    SELECT
        time_bucket(INTERVAL '1 minute', timestamp) AS minute,
        AVG(value) AS avg_speed_ms
    FROM navigation_speedOverGround
    GROUP BY 1
    ORDER BY 1
    \"\"\")
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
