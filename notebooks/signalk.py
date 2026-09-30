import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full", app_title="SignalK Data Lab")


with app.setup(hide_code=True):
    import marimo as mo
    import polars as pl
    import json
    import os
    from datetime import date, timedelta
    from urllib.parse import urlencode
    import polars as pl
    import json
    import os
    from datetime import date, timedelta
    from urllib.parse import urlencode

    try:
        from pyodide.http import pyfetch
        import js
    except ImportError:
        import asyncio
        import urllib.request

        class _Response:
            def __init__(self, data, status):
                self._data = data
                self.status = status
                self.ok = 200 <= status < 300

            async def string(self):
                return self._data.decode("utf-8")

            async def json(self):
                return json.loads(self._data)

        # Local stand-in for pyodide's pyfetch. Browser-only options such as
        # credentials="include" are accepted and ignored.
        async def pyfetch(url, **kwargs):
            method = kwargs.get("method", "GET")
            headers = kwargs.get("headers", {})
            body = kwargs.get("body")

            def _do_request():
                req = urllib.request.Request(url, data=body, headers=headers, method=method)
                with urllib.request.urlopen(req) as resp:
                    return resp.read(), resp.status

            data, status = await asyncio.get_event_loop().run_in_executor(None, _do_request)
            return _Response(data, status)

        class _Location:
            origin = os.environ.get("SIGNALK_URL", "http://localhost:3000")

        class _Js:
            location = _Location()

        js = _Js()


@app.cell(hide_code=True)
def _(js, mo):
    signalk_url = str(js.location.origin)
    mo.md(
        f"""
        # SignalK Data Lab
        **History API Server** `{signalk_url}`

        Select a provider and paths, set a date range, then press **Fetch data**.
        Other notebooks: [Data Source Explorer](data_source_explorer.html) to browse or query history with Ibis,
        [signalk-cli Data Access](history_export.html) to access via the `signalk-cli` library for analysis in the notebook or export to JSON or Feather dataframe.
        """
    )
    return (signalk_url,)


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

    # SignalK often marks Kip as the default provider, but it often holds little
    # history, so prefer the first provider that isn't Kip
    _preferred = [p for p in _provider_options if not p.lower().startswith("kip")]
    _default_provider = (_preferred or _provider_options or [None])[0]

    provider_input = mo.ui.dropdown(
        options=_provider_options,
        value=_default_provider,
        label="Provider",
    )
    return (provider_input,)


@app.cell(hide_code=True)
async def _(json, mo, provider_input, pyfetch, signalk_url, urlencode):
    _available_paths = []
    if provider_input.value:
        try:
            _qs = urlencode({"provider": provider_input.value, "duration": "PT24H"})
            _resp = await pyfetch(
                f"{signalk_url}/signalk/v2/api/history/paths?{_qs}",
                credentials="include",
            )
            _data = json.loads(await _resp.string())
            _available_paths = sorted(_data) if isinstance(_data, list) else []
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
            full_width=True,
        )
    else:
        paths_input = mo.ui.text_area(
            value="\n".join(_defaults),
            label="Paths (one per line — no data found for last 24 h)",
            rows=5,
        )
    return (paths_input,)


@app.cell(hide_code=True)
def _(date, mo, timedelta):
    _today = date.today()
    _yesterday = _today - timedelta(days=1)
    from_date = mo.ui.date(value=_yesterday, label="From")
    to_date = mo.ui.date(value=_today, label="To")
    fetch_btn = mo.ui.run_button(label="Fetch data")
    return fetch_btn, from_date, to_date


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


@app.cell(hide_code=True)
async def _(
    fetch_btn,
    from_date,
    json,
    mo,
    paths_input,
    pl,
    provider_input,
    pyfetch,
    signalk_url,
    to_date,
    urlencode,
):
    _empty = pl.DataFrame({
        "timestamp": pl.Series([], dtype=pl.Datetime("us", "UTC")),
        "path": pl.Series([], dtype=pl.Utf8),
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

    def _to_float(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            inner = v.get("value")
            return float(inner) if isinstance(inner, (int, float)) else None
        return None

    for _i, _meta in enumerate(_path_meta):
        _path = _meta.get("path", f"path_{_i}")
        _tname = _path.replace(".", "_")
        _method = _meta.get("method", "")

        _path_rows = [
            {
                "timestamp": _row[0],
                "path": _path,
                "value": _to_float(_row[_i + 1]),
                "method": _method,
                "context": _context,
            }
            for _row in _data_rows
            if len(_row) > _i + 1
        ]
        _long_rows.extend(_path_rows)

        tables[_tname] = (
            pl.DataFrame(_path_rows)
            .with_columns([
                pl.col("timestamp").str.to_datetime(
                    format="%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC", strict=False, time_unit="us"
                ),
                pl.col("value").cast(pl.Float64, strict=False),
            ])
            if _path_rows else _empty
        )

    if _long_rows:
        signalk_data = (
            pl.DataFrame(_long_rows)
            .with_columns([
                pl.col("timestamp").str.to_datetime(
                    format="%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC", strict=False, time_unit="us"
                ),
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
    return


@app.cell(hide_code=True)
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
