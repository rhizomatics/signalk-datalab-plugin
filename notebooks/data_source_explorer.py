import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full", app_title="SignalK Paths in Data Explorer with Ibis")

with app.setup(hide_code=True):
    import marimo as mo
    import altair as alt
    import json
    import os
    from datetime import timedelta

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

        # Local stand-in for pyodide's pyfetch. Browser-only options such as
        # credentials="include" are accepted and ignored.
        async def pyfetch(url, **kwargs):
            def _do_request():
                with urllib.request.urlopen(url) as resp:
                    return resp.read(), resp.status

            data, status = await asyncio.get_event_loop().run_in_executor(None, _do_request)
            return _Response(data, status)

        class _Location:
            origin = os.environ.get("SIGNALK_URL", "http://localhost:3000")

        class _Js:
            location = _Location()

        js = _Js()



@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # SignalK Paths in Data Explorer with Ibis

    Browse SignalK history with marimo's data browser, or query it with
    [Ibis](https://ibis-project.org) expressions, with filtering and aggregation
    done on the server. Ibis loads when the notebook opens, which takes a few
    seconds the first time.

    Cells run automatically as you change the inputs. If any look stale or empty,
    press **Run** (▶) at the bottom right of the page.

    **Limitations**

    - `ibis-signalk` is an experimental Ibis backend written for this plugin, not
    part of Ibis itself.
    - About 21 MB (Ibis, pyarrow, pandas) downloads the first time.
    - Whatever the History API can't filter or aggregate is computed in the
    browser. Histograms and joins need DuckDB, which isn't loaded here; install
    `duckdb` from the package manager panel if you need them.
    - pyarrow and pandas in the browser are WebAssembly builds that trail the
    desktop releases (pyarrow 22 against 25 in September 2026).

    Find the other notebooks in the [gallery](index.html).
    """)
    return


@app.cell(hide_code=True)
async def _(js, json, mo, pyfetch):
    signalk_url = str(js.location.origin)
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
            # The History API only takes time durations (PT...), not days
            "Last 7 days": "PT168H",
        },
        value="Last hour",
        label="Duration",
    )
    mo.vstack([
        mo.md(f"""
        **History API Server** `{signalk_url}`

        Choose the namespaces to browse once Ibis is loaded. Each appears in
        the data browser under its own name, covering the chosen duration
        unless you filter on `timestamp`. Column stats work, but histograms
        need `duckdb`, which you can install from the package manager panel.
        """),
        mo.hstack(
            [provider_input, duration_input],
            justify="start",
            gap="1.5rem",
            align="center",
        ),
    ])
    return duration_input, provider_input, signalk_url


@app.cell(hide_code=True)
async def _(json, mo, pyfetch):
    import importlib as _importlib
    import sys as _sys

    if "pyodide" in _sys.modules:
        # In the browser, install the wheel the plugin serves alongside this notebook
        import micropip as _micropip

        _wheels = f"{mo.notebook_location()}/wheels"
        _resp = await pyfetch(f"{_wheels}/index.json")
        _wheel = json.loads(await _resp.string())["ibis-signalk"]
        with mo.status.spinner(title="Installing Ibis…"):
            await _micropip.install(f"{_wheels}/{_wheel}")

    try:
        # importlib so marimo doesn't try to auto-install it from PyPI
        ibis_signalk = _importlib.import_module("ibis_signalk")
    except ImportError:
        ibis_signalk = None
    mo.stop(
        ibis_signalk is None,
        mo.callout(
            mo.md("`ibis-signalk` isn't installed here. Run locally with `npm run lab`."),
            kind="warn",
        ),
    )
    return (ibis_signalk,)


@app.cell(hide_code=True)
def _(duration_input, ibis_signalk, mo, provider_input, signalk_url):
    ibis_con = ibis_signalk.Backend()
    ibis_con.do_connect(
        signalk_url,
        provider=provider_input.value,
        default_duration=duration_input.value,
    )
    _namespaces = ibis_con.list_tables()
    namespace_input = mo.ui.multiselect(
        options=_namespaces,
        value=["navigation"] if "navigation" in _namespaces else _namespaces[:1],
        label="Namespaces",
    )
    mo.vstack([
        mo.md(f"Connected with provider `{ibis_con.provider}`."),
        namespace_input,
    ])
    return ibis_con, namespace_input


@app.cell(hide_code=True)
def _(ibis_con, mo, namespace_input):
    # One Ibis table per chosen namespace, each a named variable so it shows
    # up in marimo's data browser. Unchosen namespaces are None.
    tables = {_ns: ibis_con.table(_ns) for _ns in namespace_input.value}
    communication = tables.get("communication")
    design = tables.get("design")
    electrical = tables.get("electrical")
    environment = tables.get("environment")
    navigation = tables.get("navigation")
    notifications = tables.get("notifications")
    performance = tables.get("performance")
    propulsion = tables.get("propulsion")
    sails = tables.get("sails")
    sensors = tables.get("sensors")
    steering = tables.get("steering")
    tanks = tables.get("tanks")

    mo.stop(not tables, mo.callout(mo.md("Choose one or more namespaces."), kind="info"))
    mo.vstack([
        mo.ui.tabs({_ns: mo.ui.table(_t) for _ns, _t in tables.items()}),
        mo.md("""
        Query them with Ibis, e.g.

        ```python
        from datetime import datetime, timedelta, timezone

        recent = navigation.filter(
            navigation.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        ibis_con.execute(recent)
        ```
        """),
    ])
    return (
        communication,
        design,
        electrical,
        environment,
        navigation,
        notifications,
        performance,
        propulsion,
        sails,
        sensors,
        steering,
        tables,
        tanks,
    )


@app.cell(hide_code=True)
def _(ibis_con, mo):
    # Number paths only: those are what the server can average, min or max
    numeric_paths = {}
    for _ns in ibis_con.list_tables():
        for _name, _dtype in ibis_con.table(_ns).schema().items():
            if _dtype.is_floating():
                numeric_paths[_name.replace("__", ".")] = (_ns, _name)
    _default = next(
        (p for p in ("navigation.speedOverGround", "environment.wind.speedApparent") if p in numeric_paths),
        next(iter(sorted(numeric_paths)), None),
    )
    request_path_input = mo.ui.dropdown(
        options=sorted(numeric_paths), value=_default, label="Path", searchable=True
    )
    request_bucket_input = mo.ui.dropdown(
        options={"Second": "s", "Minute": "m", "Hour": "h", "Day": "D"},
        value="Minute",
        label="Bucket",
    )
    request_stat_input = mo.ui.dropdown(
        options={"Average": "mean", "Minimum": "min", "Maximum": "max", "First": "first", "Last": "last"},
        value="Average",
        label="Statistic",
    )
    mo.vstack([
        mo.md(r"""
        ---
        ## From Ibis expression to History API request

        An Ibis expression isn't run in the browser: `ibis-signalk` compiles it
        into a History API request, and the SignalK server does the work. Time
        filters become the request's time range, and grouping by a truncated
        `timestamp` becomes its `resolution`, with the statistic as each path's
        aggregation method. Only the summary comes back over the network.
        """),
        mo.hstack(
            [request_path_input, request_bucket_input, request_stat_input],
            justify="start",
            gap="1.5rem",
        ),
    ])
    return numeric_paths, request_bucket_input, request_path_input, request_stat_input


@app.cell(hide_code=True)
def _(
    ibis_con,
    mo,
    numeric_paths,
    request_bucket_input,
    request_path_input,
    request_stat_input,
):
    mo.stop(
        request_path_input.value is None,
        mo.callout(mo.md("No number paths reported in this duration."), kind="info"),
    )
    _ns, _col = numeric_paths[request_path_input.value]
    _t = ibis_con.table(_ns)
    _unit, _stat = request_bucket_input.value, request_stat_input.value
    _expr = _t.group_by(bucket=_t.timestamp.truncate(_unit)).aggregate(
        value=getattr(_t[_col], _stat)()
    )
    _params = ibis_con.compile(_expr).to_params()
    _code = (
        f'{_ns}.group_by(bucket={_ns}.timestamp.truncate("{_unit}")).aggregate(\n'
        f"    value={_ns}.{_col}.{_stat}()\n)"
    )
    _request = "GET /signalk/v2/api/history/values\n" + "\n".join(
        f"    {k}={v}" for k, v in _params.items()
    )
    try:
        with mo.status.spinner(title="Asking the server…"):
            _df = ibis_con.execute(_expr)
    except Exception as _e:
        mo.stop(True, mo.callout(mo.md(f"**Request failed**: {_e}"), kind="danger"))

    _bucket_name = request_bucket_input.selected_key.lower()
    _stat_name = request_stat_input.selected_key.lower()
    _chart = (
        alt.Chart(_df.dropna())
        .mark_line(point=len(_df) <= 60)
        .encode(
            x=alt.X("bucket:T", title=None),
            y=alt.Y("value:Q", title=f"{_stat_name} of {request_path_input.value}"),
            tooltip=[alt.Tooltip("bucket:T", format="%d %b %H:%M:%S"), alt.Tooltip("value:Q", format=".4~f")],
        )
        .properties(height=220, width="container")
    )
    mo.vstack([
        mo.hstack(
            [
                mo.vstack([mo.md("**This Ibis expression**"), mo.md(f"```python\n{_code}\n```")]),
                mo.vstack([mo.md("**becomes this request**"), mo.md(f"```\n{_request}\n```")]),
            ],
            widths="equal",
            gap="1.5rem",
        ),
        mo.md(
            f"The server sent back **{len(_df):,}** rows, one per {_bucket_name}, having "
            f"worked out each {_stat_name} itself. Values are in SignalK's SI units "
            "(m/s, radians, Kelvin)."
        ),
        _chart,
    ])
    return


@app.cell(hide_code=True)
def _(duration_input, ibis_con, mo, namespace_input):
    mo.stop(not namespace_input.value)
    # Minute buckets for short durations, hours for longer ones, so the
    # heatmap stays a readable width
    _unit, _step = (
        ("m", timedelta(minutes=1))
        if duration_input.value in ("PT1H", "PT6H")
        else ("h", timedelta(hours=1))
    )
    _rows = []
    with mo.status.spinner(title="Checking which paths reported…"):
        for _ns in namespace_input.value:
            _t = ibis_con.table(_ns)
            _columns = [c for c in _t.columns if c != "timestamp"]
            if not _columns:
                continue
            # One request per namespace: the first value of every path in
            # every bucket, picked by the server
            _df = ibis_con.execute(
                _t.group_by(bucket=_t.timestamp.truncate(_unit)).aggregate(
                    **{c: _t[c].first() for c in _columns}
                )
            )
            for _record in _df.to_dict("records"):
                for _column in _columns:
                    _value = _record[_column]
                    if _value is not None and _value == _value:  # not None or NaN
                        _start = _record["bucket"]
                        _rows.append({
                            "path": _column.replace("__", "."),
                            "start": _start.isoformat(),
                            "end": (_start + _step).isoformat(),
                        })
    mo.stop(not _rows, mo.callout(mo.md("Nothing reported in this duration."), kind="info"))

    _paths = sorted({r["path"] for r in _rows})
    _latest = max(r["start"] for r in _rows)
    _quiet = sorted(
        p for p in _paths if max(r["start"] for r in _rows if r["path"] == p) < _latest
    )
    _heatmap = (
        alt.Chart(alt.Data(values=_rows))
        .mark_rect(color="#1f77b4")
        .encode(
            x=alt.X("start:T", title=None),
            x2="end:T",
            y=alt.Y("path:N", title=None, sort=_paths),
            tooltip=["path:N", alt.Tooltip("start:T", format="%d %b %H:%M", title="from")],
        )
        .properties(height=max(80, 16 * len(_paths)), width="container")
    )
    mo.vstack([
        mo.md(
            "---\n## Which instruments reported, and when\n\n"
            f"Each bar is a {'minute' if _unit == 'm' else 'hour'} in which a path "
            "reported at least once, across the namespaces chosen above, so gaps "
            "show when a sensor or its connection dropped out. Each namespace is a "
            "single request, with the server picking one value per path per bucket."
        ),
        _heatmap,
        mo.callout(
            mo.md(
                "Quiet in the latest " + ("minute" if _unit == "m" else "hour") + ": "
                + ", ".join(f"`{p}`" for p in _quiet)
            ),
            kind="warn",
        )
        if _quiet
        else mo.md("Every path reported in the latest bucket."),
    ])
    return


if __name__ == "__main__":
    app.run()
