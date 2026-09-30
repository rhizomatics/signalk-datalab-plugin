import marimo

__generated_with = "0.25.0"
app = marimo.App(width="full", app_title="Live Stream With signalk-cli")

with app.setup(hide_code=True):
    import marimo as mo
    import altair as alt
    import polars as pl
    import collections
    import json
    import threading

    # Displaying UTC timestamps needs the tzdata package, which Pyodide only
    # loads when it sees it imported
    try:
        import tzdata  # noqa: F401
    except ImportError:
        pass

    class LiveFeed:
        """A SignalK delta subscription that collects rows as they arrive.

        In the browser it uses the browser's WebSocket, which calls back for
        each message and leaves the notebook free to redraw in between.
        Locally it runs signalk-cli's blocking client in a thread. State lives
        on the object rather than in cell variables, because marimo deletes a
        cell's private (_-prefixed) variables when the cell runs again, while
        callbacks and the thread may still need them.
        """

        def __init__(self, stream_api, signalk_cli, host, paths, min_period, in_browser):
            self.stream_api = stream_api
            self.rows = collections.deque(maxlen=200_000)
            self.status = {"state": "connecting", "messages": 0, "error": None}
            self.stopped = threading.Event()
            self.stream = None
            self.ws = None
            self.handlers = {}
            if in_browser:
                self.open_browser(host, paths, min_period)
            else:
                thread = threading.Thread(
                    target=self.run_local,
                    args=(signalk_cli, host, paths, min_period),
                    daemon=True,
                )
                thread.start()

        def add_message(self, text):
            try:
                payload = json.loads(text)
            except ValueError:
                return
            # Skip the server's hello and other messages that aren't deltas
            if not isinstance(payload, dict) or "updates" not in payload:
                return
            self.rows.extend(self.stream_api.DeltaMessage(text, payload).rows())
            self.status["messages"] += 1

        def open_browser(self, host, paths, min_period):
            from js import WebSocket
            from pyodide.ffi import create_proxy

            subscribe = json.dumps(
                self.stream_api.build_subscribe_message(
                    "vessels.self",
                    paths,
                    policy="instant",
                    min_period_ms=None if min_period is None else int(min_period * 1000),
                )
            )
            self.ws = WebSocket.new(f"{self.stream_api.to_ws_url(host)}?subscribe=none")

            def on_open(event):
                self.status["state"] = "live"
                self.ws.send(subscribe)

            def on_close(event):
                self.status["state"] = "closed"
                # 1000 is a normal close; anything else says why it dropped
                if event.code != 1000:
                    reason = f": {event.reason}" if event.reason else ""
                    self.status["error"] = f"connection closed with code {event.code}{reason}"

            def on_error(event):
                self.status["error"] = "WebSocket error"

            self.handlers = {
                "onopen": create_proxy(on_open),
                "onmessage": create_proxy(lambda event: self.add_message(event.data)),
                "onclose": create_proxy(on_close),
                "onerror": create_proxy(on_error),
            }
            for name, handler in self.handlers.items():
                setattr(self.ws, name, handler)

        def run_local(self, signalk_cli, host, paths, min_period):
            try:
                with signalk_cli.StreamClient(host) as client:
                    with client.open(
                        paths, policy="instant", period=None, min_period=min_period, timeout=None
                    ) as stream:
                        self.stream = stream
                        self.status["state"] = "live"
                        for message in stream:
                            if self.stopped.is_set():
                                break
                            self.add_message(message.text)
            except Exception as e:
                if not self.stopped.is_set():
                    self.status["error"] = str(e)
            self.status["state"] = "closed"

        def close(self):
            self.stopped.set()
            if self.ws is not None:
                for name in self.handlers:
                    setattr(self.ws, name, None)
                self.ws.close()
                for handler in self.handlers.values():
                    handler.destroy()
                self.handlers = {}
            if self.stream is not None:
                self.stream.close()
            self.status["state"] = "closed"

    # Feeds opened by earlier runs of the connect cell, closed when it runs
    # again so only one subscription is live at a time
    open_feeds: list = []


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Live Stream With signalk-cli

    Watch your boat's data arrive live from SignalK, as a chart per path and a
    table of the latest values. It subscribes to the SignalK delta stream over a
    WebSocket and redraws every few seconds; use the refresh control to change the
    rate or pause.

    Cells run automatically as you change the inputs. If any look stale or empty,
    press **Run** (▶) at the bottom right of the page.

    **Limitations**

    - Only data that arrives while the page is open is shown, and it's kept in
    browser memory for the chosen window. For anything older, use the history
    notebooks below.
    - The chart redraws on the refresh interval, not on every message. Numbers
    are averaged per second, and positions are split into latitude and longitude.
    - SignalK only sends a value when it changes, so the chart holds each value
    until the next reading (dots mark the readings). A flat line means nothing
    new has arrived, not that the reading was confirmed.
    - It uses the browser's own WebSocket rather than signalk-cli's streaming
    client, which waits for each message in a way that would stop the rest of
    the notebook from running in the browser. signalk-cli still builds the
    subscription and reads the messages.
    - Only your own vessel (`vessels.self`) is subscribed.

    Find the other notebooks in the [gallery](index.html).
    """)
    return


@app.cell(hide_code=True)
async def _():
    import importlib as _importlib
    import os as _os
    import sys as _sys

    in_browser = "pyodide" in _sys.modules
    if in_browser:
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
    stream_api = _importlib.import_module("signalk_cli.stream.api")
    return in_browser, signalk_cli, signalk_url, stream_api


@app.cell(hide_code=True)
def _(signalk_url):
    paths_input = mo.ui.text(
        value="environment.outside.*, environment.wind.*",
        label="Paths",
        full_width=True,
    )
    rate_input = mo.ui.dropdown(
        options={
            # The "instant" policy with a minimum period. Unlike "fixed" or
            # "ideal", signalk-server then starts with the current value of
            # every path, not only the ones that change
            "Every change": None,
            "At most once a second": 1,
            "At most every 5 seconds": 5,
        },
        value="At most once a second",
        label="Updates",
    )
    window_input = mo.ui.dropdown(
        options={"Last 5 minutes": 5, "Last 15 minutes": 15, "Last hour": 60},
        value="Last 5 minutes",
        label="Show",
    )
    refresh = mo.ui.refresh(options=["1s", "2s", "5s", "10s"], default_interval="2s")
    mo.vstack([
        mo.md(f"""
        **SignalK Server** `{signalk_url}`

        Paths are comma-separated. A `*` matches the rest of a path
        (`environment.*`, `navigation.*`) or one whole segment
        (`propulsion.*.revolutions`). Only paths with new data show up.
        """),
        mo.hstack([rate_input, window_input, refresh], justify="start", gap="1.5rem", align="end"),
        paths_input,
    ])
    return paths_input, rate_input, refresh, window_input


@app.cell(hide_code=True)
def _(in_browser, paths_input, rate_input, signalk_cli, signalk_url, stream_api):
    for _feed in open_feeds:
        _feed.close()
    open_feeds.clear()

    live_feed = LiveFeed(
        stream_api,
        signalk_cli,
        signalk_url,
        [p.strip() for p in paths_input.value.split(",") if p.strip()],
        rate_input.value,
        in_browser,
    )
    open_feeds.append(live_feed)
    return (live_feed,)


@app.cell(hide_code=True)
def _(live_feed, refresh, window_input):
    import datetime as _dt

    _ = refresh.value

    # Numbers as they are; objects such as navigation.position split into one
    # series per numeric field (latitude, longitude)
    _records = []
    _latest = {}
    for _row in list(live_feed.rows):
        _latest[_row.path] = (_row.timestamp, _row.value)
        _value = _row.value
        if isinstance(_value, (int, float)) and not isinstance(_value, bool):
            _records.append((_row.timestamp, _row.path, float(_value)))
        elif isinstance(_value, dict):
            for _key, _field in _value.items():
                if isinstance(_field, (int, float)) and not isinstance(_field, bool):
                    _records.append((_row.timestamp, f"{_row.path}.{_key}", float(_field)))

    # The window is measured back from the newest reading, not the browser's
    # clock, so it still works if the boat's clock is off
    _readings = (
        pl.DataFrame(
            _records,
            schema={"timestamp": pl.String, "path": pl.String, "value": pl.Float64},
            orient="row",
        )
        .with_columns(
            pl.col("timestamp").str.to_datetime(
                format="%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC", strict=False, time_unit="us"
            )
        )
        .drop_nulls("timestamp")
        .sort("timestamp")
        .group_by_dynamic("timestamp", every="1s", group_by="path")
        .agg(pl.col("value").mean())
        .sort("timestamp")
    )

    # The window runs up to now, so values that haven't changed are drawn up to
    # the present. If the newest reading is older than the window (e.g. the
    # boat's clock is off), it runs up to the newest reading instead.
    _window = _dt.timedelta(minutes=window_input.value)
    _now = _dt.datetime.now(_dt.UTC)
    _newest = _readings["timestamp"].max()
    _end = _now if _newest is not None and _now - _newest < _window else _newest

    if _readings.is_empty():
        live_data = _readings.with_columns(reading=pl.lit(True))
    else:
        # SignalK only sends a path when its value changes, so hold each value
        # until the next reading: a grid of times per path, filled from the
        # latest reading at or before each time (including ones from before
        # the window started)
        _step = f"{max(1, window_input.value // 12)}s"
        _grid = (
            pl.DataFrame({"timestamp": pl.datetime_range(_end - _window, _end, _step, time_unit="us", eager=True)})
            .join(_readings.select("path").unique(), how="cross")
            .sort("timestamp")
        )
        _held = (
            _grid.join_asof(_readings, on="timestamp", by="path", strategy="backward", check_sortedness=False)
            .drop_nulls("value")
            .with_columns(reading=pl.lit(False))
        )
        live_data = pl.concat([
            _held,
            _readings.filter(pl.col("timestamp") >= _end - _window).with_columns(reading=pl.lit(True)),
        ], how="diagonal").sort("path", "timestamp")

    latest_values = pl.DataFrame(
        [
            {"path": _path, "timestamp": _ts, "value": json.dumps(_value) if isinstance(_value, (dict, list)) else str(_value)}
            for _path, (_ts, _value) in sorted(_latest.items())
        ],
        schema={"timestamp": pl.String, "path": pl.String, "value": pl.String},
    ).select("path", "timestamp", "value")

    _status = (
        f"**{live_feed.status['state'].capitalize()}** · {live_feed.status['messages']:,} messages · "
        f"{len(_latest)} path(s)"
    )
    if live_feed.status["error"]:
        _status += f" · {live_feed.status['error']}"

    if live_data.is_empty():
        _chart = mo.callout(mo.md("Waiting for numeric data…"), kind="info")
    else:
        # Chart the 12 paths with the most readings, which favours ones that
        # are changing over slow-moving values such as forecasts
        _shown = (
            live_data.filter("reading")
            .group_by("path")
            .len()
            .sort(["len", "path"], descending=[True, False])["path"]
            .head(12)
            .to_list()
        )
        _base = alt.Chart(live_data.filter(pl.col("path").is_in(_shown))).encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False)),
            tooltip=["path:N", "timestamp:T", alt.Tooltip("value:Q", format=".4~f")],
        )
        # A line holds each value until the next reading; dots are readings
        _chart = (
            alt.layer(
                _base.mark_line(interpolate="step-after"),
                _base.mark_circle(size=25).transform_filter("datum.reading"),
            )
            .properties(width=700, height=90)
            .facet(row=alt.Row("path:N", title=None, header=alt.Header(labelAngle=0, labelAlign="left")))
            .resolve_scale(y="independent")
        )

    mo.vstack([mo.md(_status), mo.hstack([_chart, mo.ui.table(latest_values, page_size=20)], widths=[3, 2])])
    return latest_values, live_data


if __name__ == "__main__":
    app.run()
