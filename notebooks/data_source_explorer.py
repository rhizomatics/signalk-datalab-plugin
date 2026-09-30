import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full", app_title="SignalK Paths in Data Explorer with Ibis")

with app.setup(hide_code=True):
    import marimo as mo
    import json
    import os

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
            "Last 7 days": "P7D",
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


if __name__ == "__main__":
    app.run()
