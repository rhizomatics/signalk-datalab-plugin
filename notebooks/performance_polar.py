import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="Performance Polars")

with app.setup(hide_code=True):
    import marimo as mo
    import altair as alt
    import numpy as np
    import importlib
    import json
    import math
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

    MS_TO_KNOTS = 1.943844
    # True wind speed bands (knots), as on a published polar
    TWS_BANDS = [6, 8, 10, 12, 14, 16, 20, 25]
    # Boat speed, true wind angle and true wind speed, each with a fallback
    BOAT_SPEED_PATHS = ["navigation.speedThroughWater", "navigation.speedOverGround"]
    WIND_ANGLE_PATHS = ["environment.wind.angleTrueWater", "environment.wind.angleTrueGround"]
    WIND_SPEED_PATHS = ["environment.wind.speedTrue", "environment.wind.speedOverGround"]


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Performance Polars

    Build a [polar diagram](https://www.boatpolars.com/learn/what-is-a-polar-diagram) from your own sailing: how fast the boat goes at
    each true wind angle and wind speed, taken from SignalK history with
    [Ibis](https://ibis-project.org), with the server summarising each minute.
    See the best angles to sail upwind and downwind, and download the polar
    for OpenCPN and other routing software.

    No sailing history with wind yet? Choose **Demo data** for a made-up
    season on a 36 ft cruiser.

    Cells run automatically as you change the inputs. If any look stale or empty,
    press **Run** (▶) at the bottom right of the page.

    **Limitations**

    - Needs true wind: `environment.wind.angleTrueWater` (or `angleTrueGround`)
    and `environment.wind.speedTrue` (or `speedOverGround`), as calculated by
    the derived-data plugin from apparent wind and boat speed.
    - Boat speed is speed through water if there's a log, otherwise speed over
    ground, which tide skews.
    - Motoring isn't excluded: time under engine shows as fast sailing, so use
    durations that are mostly sailing, or this will flatter the boat.
    - About 21 MB (Ibis, pyarrow, pandas) downloads the first time.

    Find the other notebooks in the [gallery](index.html).
    """)
    return


@app.cell(hide_code=True)
async def _():
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

    source_input = mo.ui.radio(
        options=["SignalK history", "Demo data"],
        value="SignalK history" if _provider_options else "Demo data",
        label="Source",
        inline=True,
    )
    provider_input = mo.ui.dropdown(
        options=_provider_options,
        value=(_preferred or _provider_options or [None])[0],
        label="Provider",
    )
    duration_input = mo.ui.dropdown(
        # The History API only takes time durations (PT...), not days
        options={
            "Last 24 hours": "PT24H",
            "Last 7 days": "PT168H",
            "Last 30 days": "PT720H",
            "Last 90 days": "PT2160H",
        },
        value="Last 30 days",
        label="Duration",
    )
    fetch_btn = mo.ui.run_button(label="Build polar")
    return duration_input, fetch_btn, provider_input, signalk_url, source_input


@app.cell(hide_code=True)
def _(duration_input, fetch_btn, provider_input, signalk_url, source_input):
    if source_input.value == "Demo data":
        _controls = mo.md(
            "A made-up season on a 36 ft cruiser: a few thousand minutes of "
            "sailing in 4 to 26 knots of wind, with the scatter real data has."
        )
    else:
        _controls = mo.vstack([
            mo.md(f"**History API Server** `{signalk_url}`"),
            mo.hstack([provider_input, duration_input], justify="start", gap="1.5rem"),
            fetch_btn,
        ])
    mo.vstack([source_input, _controls])
    return


@app.cell(hide_code=True)
async def _(source_input):
    import sys as _sys

    ibis_signalk = None
    if source_input.value == "SignalK history":
        if "pyodide" in _sys.modules:
            # In the browser, install the wheel the plugin serves alongside
            # this notebook
            import micropip as _micropip

            _wheels = f"{mo.notebook_location()}/wheels"
            _resp = await pyfetch(f"{_wheels}/index.json")
            _wheel = json.loads(await _resp.string())["ibis-signalk"]
            with mo.status.spinner(title="Installing Ibis…"):
                await _micropip.install(f"{_wheels}/{_wheel}")
        try:
            # importlib so marimo doesn't try to auto-install it from PyPI
            ibis_signalk = importlib.import_module("ibis_signalk")
        except ImportError:
            mo.stop(
                True,
                mo.callout(
                    mo.md("`ibis-signalk` isn't installed here. Run locally with `npm run lab`."),
                    kind="warn",
                ),
            )
    return (ibis_signalk,)


@app.cell(hide_code=True)
def _(
    duration_input,
    fetch_btn,
    ibis_signalk,
    provider_input,
    signalk_url,
    source_input,
):
    if source_input.value == "Demo data":
        samples = demo_samples()
        sample_note = "demo data"
    else:
        mo.stop(
            not fetch_btn.value,
            mo.callout(mo.md("Press **Build polar** to load."), kind="info"),
        )
        _con = ibis_signalk.Backend()
        _con.do_connect(
            signalk_url, provider=provider_input.value, default_duration=duration_input.value
        )
        try:
            with mo.status.spinner(title="Fetching a summary of each minute…"):
                samples, _used = fetch_samples(_con)
        except LookupError as _e:
            mo.stop(True, mo.callout(mo.md(str(_e)), kind="warn"))
        except Exception as _e:
            mo.stop(True, mo.callout(mo.md(f"**Fetch failed**: {_e}"), kind="danger"))
        sample_note = ", ".join(f"`{p}`" for p in _used)
    mo.stop(
        len(samples["bsp"]) < 30,
        mo.callout(
            mo.md(
                f"Only {len(samples['bsp'])} minutes under sail with true wind in "
                "this duration; try a longer one."
            ),
            kind="warn",
        ),
    )
    mo.md(f"**{len(samples['bsp']):,}** minutes under sail, from {sample_note}")
    return (samples,)


@app.cell(hide_code=True)
def _():
    quantile_input = mo.ui.slider(
        0.5, 0.99, step=0.01, value=0.9, label="Boat speed percentile", show_value=True
    )
    min_samples_input = mo.ui.slider(
        1, 30, step=1, value=5, label="Fewest minutes per point", show_value=True
    )
    mo.vstack([
        mo.md(r"""
        ## Polar diagram

        Each line is a true wind speed band. A point is the boat speed reached
        at that true wind angle in that wind, as a high percentile of the
        minutes sailed there, which shows what the boat does when sailed well
        rather than on average. Port and starboard are combined.
        """),
        mo.hstack([quantile_input, min_samples_input], justify="start", gap="2rem"),
    ])
    return min_samples_input, quantile_input


@app.cell(hide_code=True)
def _(min_samples_input, quantile_input, samples):
    polar = build_polar(
        samples, quantile=quantile_input.value, min_samples=min_samples_input.value
    )
    mo.stop(not polar, mo.callout(mo.md("Not enough minutes in any band yet."), kind="info"))
    mo.hstack(
        [polar_chart(polar), best_angles_table(polar)],
        justify="start",
        gap="2rem",
        align="start",
    )
    return (polar,)


@app.cell(hide_code=True)
def _(polar):
    mo.vstack([
        mo.md(
            "## Download\n\nThe polar as a tab-separated table, true wind angle "
            "down and true wind speed across, in knots: the layout OpenCPN's "
            "weather routing and other routing software read. Gaps are where "
            "there weren't enough minutes."
        ),
        mo.download(
            data=to_pol(polar).encode("utf-8"),
            filename="performance.pol",
            mimetype="text/tab-separated-values",
            label="Download polar (.pol)",
        ),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ---
    ## How it works

    The functions below do the work. Their code is hidden to keep the page
    short; open any cell to read or change it.
    """)
    return


@app.function(hide_code=True)
def fetch_samples(con) -> tuple:
    """Per-minute boat speed, true wind angle and speed, as knots and degrees.

    Two Ibis queries, `navigation` and `environment`, each grouped by minute so
    the server summarises the history. Speeds are averaged, but the angle is
    the first in each minute: averaging angles either side of dead downwind
    (+179 and -179 degrees) would give 0, head to wind. The two are joined on
    the minute in pandas, as the History API can't join.
    """
    def pick(table, candidates):
        columns = set(table.columns)
        return next((p for p in candidates if p.replace(".", "__") in columns), None)

    tables = set(con.list_tables())
    if not {"navigation", "environment"} <= tables:
        raise LookupError("No `navigation` and `environment` history in this duration.")
    nav, env = con.table("navigation"), con.table("environment")
    bsp_path = pick(nav, BOAT_SPEED_PATHS)
    twa_path = pick(env, WIND_ANGLE_PATHS)
    tws_path = pick(env, WIND_SPEED_PATHS)
    missing = [
        name
        for name, path in (("boat speed", bsp_path), ("true wind angle", twa_path), ("true wind speed", tws_path))
        if path is None
    ]
    if missing:
        raise LookupError(
            "No " + " or ".join(missing) + " in this duration. True wind comes from the "
            "derived-data plugin, calculated from apparent wind and boat speed."
        )

    def col(table, path):
        return table[path.replace(".", "__")]

    boat = con.execute(
        nav.group_by(minute=nav.timestamp.truncate("m")).aggregate(bsp=col(nav, bsp_path).mean())
    )
    wind = con.execute(
        env.group_by(minute=env.timestamp.truncate("m")).aggregate(
            twa=col(env, twa_path).first(), tws=col(env, tws_path).mean()
        )
    )
    joined = boat.merge(wind, on="minute").dropna()
    samples = {
        "bsp": joined["bsp"].to_numpy(dtype=float) * MS_TO_KNOTS,
        "twa": np.degrees(np.abs(joined["twa"].to_numpy(dtype=float))),
        "tws": joined["tws"].to_numpy(dtype=float) * MS_TO_KNOTS,
    }
    return under_sail(samples), [bsp_path, twa_path, tws_path]


@app.function(hide_code=True)
def under_sail(samples: dict) -> dict:
    """Drop minutes stopped, or with too little wind to sail."""
    keep = (samples["bsp"] > 0.5) & (samples["tws"] >= 3) & (samples["twa"] <= 180)
    return {k: v[keep] for k, v in samples.items()}


@app.function(hide_code=True)
def demo_samples() -> dict:
    """A made-up season on a ~36 ft cruiser, with real data's scatter.

    Target speed rises with wind towards a hull speed of ~7.5 knots, is
    nothing inside ~32 degrees, peaks on a beam reach and falls off running.
    Each minute gets random wind, a random angle, and noise for waves, helming
    and gusts. Seeded, so the same every time.
    """
    rng = np.random.default_rng(7)
    n = 6000
    tws = rng.gamma(4.0, 3.0, n).clip(4, 26)
    twa = rng.uniform(25, 180, n)
    hull = 7.5
    power = 1 - np.exp(-tws / 8.5)
    upwind = np.clip((twa - 32) / 28, 0, 1) ** 0.6
    shape = upwind * (1 - 0.18 * np.clip((twa - 115) / 65, 0, 1))
    bsp = np.minimum(hull * 1.03, 1.12 * hull * power * shape) + rng.normal(0, 0.35, n)
    return under_sail({"bsp": bsp, "twa": twa, "tws": tws})


@app.function(hide_code=True)
def build_polar(samples: dict, quantile: float = 0.9, min_samples: int = 5, angle_step: int = 10) -> list:
    """Points of the polar: band, angle and boat speed, from the samples.

    Each minute goes to the nearest wind band (halfway to its neighbours) and
    the nearest angle step; a point is the `quantile` of boat speed among at
    least `min_samples` minutes. VMG (velocity made good) is the speed
    straight upwind or downwind at that angle.
    """
    edges = [0] + [(a + b) / 2 for a, b in zip(TWS_BANDS, TWS_BANDS[1:])] + [TWS_BANDS[-1] + 3]
    band_index = np.digitize(samples["tws"], edges) - 1
    angle_bin = np.round(samples["twa"] / angle_step) * angle_step
    points = []
    for i, band in enumerate(TWS_BANDS):
        in_band = band_index == i
        for angle in range(30, 181, angle_step):
            speeds = samples["bsp"][in_band & (angle_bin == angle)]
            if len(speeds) < min_samples:
                continue
            bsp = float(np.quantile(speeds, quantile))
            points.append({
                "tws": band,
                "twa": angle,
                "bsp": round(bsp, 2),
                "vmg": round(bsp * math.cos(math.radians(angle)), 2),
                "minutes": int(len(speeds)),
            })
    return points


@app.function(hide_code=True)
def polar_chart(polar: list):
    """The classic half-circle polar plot, in altair.

    Altair has no polar coordinates, so each point is placed at
    (speed x sin angle, speed x cos angle), with rings and spokes drawn the
    same way. Wind blows from the top.
    """
    top = max(p["bsp"] for p in polar)
    radius = 2 * math.ceil(top / 2 + 0.25)
    for p in polar:
        a = math.radians(p["twa"])
        p["x"], p["y"] = p["bsp"] * math.sin(a), p["bsp"] * math.cos(a)

    sweep = range(0, 181, 5)
    rings = [
        {"ring": r, "i": i, "x": r * math.sin(math.radians(d)), "y": r * math.cos(math.radians(d))}
        for r in range(2, radius + 1, 2)
        for i, d in enumerate(sweep)
    ]
    spokes = [
        {"spoke": d, "i": i, "x": s * math.sin(math.radians(d)), "y": s * math.cos(math.radians(d))}
        for d in range(0, 181, 30)
        for i, s in enumerate((0, radius))
    ]
    labels = [
        {"text": f"{d}°", "x": (radius + 0.6) * math.sin(math.radians(d)), "y": (radius + 0.6) * math.cos(math.radians(d))}
        for d in range(0, 181, 30)
    ] + [{"text": f"{r} kn", "x": 0.25, "y": r} for r in range(2, radius + 1, 2)]

    size = 520
    x = alt.X("x:Q", scale=alt.Scale(domain=[0, radius + 1]), axis=None)
    y = alt.Y("y:Q", scale=alt.Scale(domain=[-radius - 1, radius + 1]), axis=None)
    grid = alt.Chart(alt.Data(values=rings)).mark_line(color="#ccc", strokeWidth=0.8).encode(
        x=x, y=y, detail="ring:N", order="i:Q"
    ) + alt.Chart(alt.Data(values=spokes)).mark_line(color="#ddd", strokeWidth=0.8).encode(
        x=x, y=y, detail="spoke:N", order="i:Q"
    )
    text = alt.Chart(alt.Data(values=labels)).mark_text(color="#888", fontSize=10, align="left").encode(
        x=x, y=y, text="text:N"
    )
    lines = alt.Chart(alt.Data(values=polar)).mark_line(point=True, interpolate="monotone").encode(
        x=x,
        y=y,
        order="twa:Q",
        color=alt.Color(
            "tws:O", title="True wind (kn)", scale=alt.Scale(scheme="viridis")
        ),
        tooltip=[
            alt.Tooltip("tws:O", title="true wind kn"),
            alt.Tooltip("twa:Q", title="true wind angle °"),
            alt.Tooltip("bsp:Q", title="boat speed kn"),
            alt.Tooltip("vmg:Q", title="VMG kn"),
            alt.Tooltip("minutes:Q"),
        ],
    )
    return (grid + text + lines).properties(width=size / 2, height=size)


@app.function(hide_code=True)
def best_angles_table(polar: list):
    """Per wind band: the angle and speed with the best VMG up and downwind."""
    rows = []
    for band in TWS_BANDS:
        points = [p for p in polar if p["tws"] == band]
        if not points:
            continue
        up = max((p for p in points if p["twa"] < 90), key=lambda p: p["vmg"], default=None)
        down = min((p for p in points if p["twa"] > 90), key=lambda p: p["vmg"], default=None)
        fastest = max(points, key=lambda p: p["bsp"])
        rows.append({
            "true wind kn": band,
            "upwind angle °": up["twa"] if up else None,
            "upwind VMG kn": up["vmg"] if up else None,
            "downwind angle °": down["twa"] if down else None,
            "downwind VMG kn": -down["vmg"] if down else None,
            "fastest at °": fastest["twa"],
            "top speed kn": fastest["bsp"],
        })
    return mo.vstack([
        mo.md(
            "**Best angles.** VMG is the speed made straight upwind or downwind: "
            "sailing a little lower or higher than the upwind angle, or the "
            "downwind one, costs ground towards a mark dead to windward or leeward."
        ),
        mo.ui.table(rows, selection=None, show_download=False),
    ])


@app.function(hide_code=True)
def to_pol(polar: list) -> str:
    """Tab-separated polar: 'TWA\\TWS' header of wind speeds, a row per angle."""
    bands = [b for b in TWS_BANDS if any(p["tws"] == b for p in polar)]
    angles = sorted({p["twa"] for p in polar})
    speed = {(p["twa"], p["tws"]): p["bsp"] for p in polar}
    lines = ["TWA\\TWS\t" + "\t".join(str(b) for b in bands)]
    for angle in angles:
        cells = [f"{speed[(angle, b)]:.2f}" if (angle, b) in speed else "" for b in bands]
        lines.append(f"{angle}\t" + "\t".join(cells))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    app.run()
