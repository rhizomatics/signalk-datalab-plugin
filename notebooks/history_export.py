import marimo

__generated_with = "0.25.0"
app = marimo.App(width="full", app_title="signalk-cli Based Data Access")

with app.setup(hide_code=True):
    import marimo as mo


@app.cell(hide_code=True)
async def _(mo):
    import importlib as _importlib
    import io
    import os as _os
    import sys as _sys

    if "pyodide" in _sys.modules:
        import js as _js
        import micropip as _micropip

        # signalk-cli's metadata requires zeroconf (mDNS discovery), which has
        # no browser build and isn't needed here, so install its runtime
        # dependencies directly and skip its own. pyarrow is large (40+ MB),
        # which is why this lives in its own notebook.
        with mo.status.spinner(title="Installing signalk-cli and pyarrow…"):
            await _micropip.install(["click>=8.3.3", "niquests>=2.36.0", "pyarrow"])
            await _micropip.install("signalk-cli", deps=False)
        signalk_url = str(_js.location.origin)
    else:
        signalk_url = _os.environ.get("SIGNALK_URL", "http://localhost:3000")

    # importlib so marimo doesn't try to auto-install signalk-cli from PyPI,
    # which fails in the browser on the zeroconf requirement
    history = _importlib.import_module("signalk_cli.history")
    niquests = _importlib.import_module("niquests")
    pa = _importlib.import_module("pyarrow")
    base_url = f"{signalk_url}{history.HISTORY_BASE}"
    return base_url, history, io, niquests, pa, signalk_url


@app.cell(hide_code=True)
def _(base_url, mo, niquests, signalk_url):
    try:
        _provider_options = list(niquests.get(f"{base_url}/_providers", timeout=10).json())
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
    paths_input = mo.ui.text(
        value="navigation.*",
        label="Paths",
        full_width=True,
    )
    fetch_btn = mo.ui.run_button(label="Fetch")
    mo.vstack([
        mo.md(f"""
        # signalk-cli Data Access
        **History API Server** `{signalk_url}` · [Data Lab](index.html) · [Data Source Explorer](data_source_explorer.html)

        Fetch SignalK history with [signalk-cli](https://signalk-cli.rhizomatics.org.uk)
        and download it as Feather or CSV. Paths are comma-separated, and can be
        glob or regex patterns, e.g. `navigation.*` or `environment.wind.*`.
        """),
        mo.hstack([provider_input, duration_input], justify="start", gap="1.5rem"),
        paths_input,
        fetch_btn,
    ])
    return duration_input, fetch_btn, paths_input, provider_input


@app.cell(hide_code=True)
def _(
    base_url,
    duration_input,
    fetch_btn,
    history,
    mo,
    niquests,
    paths_input,
    provider_input,
):
    mo.stop(not fetch_btn.value, mo.callout(mo.md("Press **Fetch** to load."), kind="info"))

    _time_params = {"duration": duration_input.value}
    _patterns = [p.strip() for p in paths_input.value.split(",") if p.strip()]
    try:
        resolved_paths = history.expand_paths(
            _patterns, base_url, _time_params, provider_input.value
        )
        mo.stop(not resolved_paths, mo.callout(mo.md("No paths matched."), kind="warn"))
        _resp = niquests.get(
            f"{base_url}/values",
            params={
                **_time_params,
                "paths": ",".join(resolved_paths),
                "provider": provider_input.value,
            },
            timeout=60,
        )
        _resp.raise_for_status()
    except niquests.RequestException as _e:
        mo.stop(True, mo.callout(mo.md(f"**Fetch failed**: {history.api_error(_e)}"), kind="danger"))
    result = _resp.json()
    return (result,)


@app.cell(hide_code=True)
def _(history, io, mo, pa, result):
    _timestamps, _paths, _values, _unique = history.extract_rows(result)
    history_table = pa.table({"timestamp": _timestamps, "path": _paths, "value": _values})

    # Use signalk-cli's own writers, so the files match its CLI output
    _feather_file = "/tmp/signalk-history.feather"
    history.write_feather(result, _feather_file)
    with open(_feather_file, "rb") as _f:
        _feather_bytes = _f.read()
    _csv = io.StringIO()
    history.write_csv(result, _csv, no_header=False)

    mo.vstack([
        mo.md(f"**{history_table.num_rows:,}** rows from {len(_unique)} path(s)"),
        mo.hstack([
            mo.download(_feather_bytes, filename="signalk-history.feather", label="Download Feather"),
            mo.download(_csv.getvalue().encode(), filename="signalk-history.csv", label="Download CSV"),
        ], justify="start"),
        mo.ui.table(history_table),
    ])
    return (history_table,)


if __name__ == "__main__":
    app.run()
