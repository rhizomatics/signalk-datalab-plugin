import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", app_title="ibis-signalk dev")

with app.setup:
    import marimo as mo
    import os

    # Same setting and default as notebooks/signalk.py
    signalk_url = os.environ.get("SIGNALK_URL", "http://localhost:3000")
    from ibis_signalk import Backend

    con = Backend()
    con.do_connect(signalk_url)
    mo.md(
        f"# ibis-signalk dev notebook\n"
        f"Target server: `{signalk_url}` · History provider: `{con.provider}`"
    )


@app.cell
def _():
    namespaces = con.list_tables()
    namespaces
    return (namespaces,)


@app.cell
def _(namespaces):
    if not namespaces:
        print("No tables found on history API")
    else:
        namespace_picker = mo.ui.dropdown(options=namespaces, value=namespaces[0], label="Namespace")
    namespace_picker
    return (namespace_picker,)


@app.cell
def _(namespace_picker):
    signalk_history = con.table(namespace_picker.value)
    signalk_history.schema()
    return (signalk_history,)


@app.cell
def _():
    duration_hours = mo.ui.slider(10, 600, value=60, step=10, label="Lookback window (hours)")
    resolution = mo.ui.dropdown(options=["s", "m", "h"], value="m", label="Aggregate resolution")
    mo.hstack([duration_hours, resolution])
    return duration_hours, resolution


@app.cell
def _(duration_hours, resolution, signalk_history):
    from datetime import datetime, timedelta, timezone

    _now = datetime.now(timezone.utc)
    _windowed = signalk_history.filter(
        signalk_history.timestamp >= _now - timedelta(seconds=duration_hours.value *3600),
        signalk_history.timestamp <= _now,
    )

    _numeric_cols = [
        name for name, dtype in signalk_history.schema().items() if name != "timestamp" and dtype.is_numeric()
    ]
    _metrics = {col: _windowed[col].mean() for col in _numeric_cols}

    aggregated = _windowed.aggregate(
        **_metrics,
        by=[_windowed.timestamp.truncate(resolution.value).name("timestamp")],
    )
    con.execute(aggregated)
    return


if __name__ == "__main__":
    app.run()
