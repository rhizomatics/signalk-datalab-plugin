import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="Geospatial Passage")

with app.setup(hide_code=True):
    import marimo as mo
    import altair as alt
    import numpy as np
    import polars as pl
    import importlib
    import json
    import os
    from datetime import datetime, timedelta, timezone
    from urllib.parse import urlencode
    from xml.sax.saxutils import escape

    # Displaying UTC timestamps needs the tzdata package, which Pyodide only
    # loads when it sees it imported
    try:
        import tzdata  # noqa: F401
    except ImportError:
        pass

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
    METRES_PER_NM = 1852.0


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Geospatial Passage

    Turn the boat's `navigation.position` history into a passage log: legs under
    way and stops at anchor or alongside, drawn on a chart with OpenSeaMap
    seamarks, and downloadable as GeoJSON or GeoParquet for QGIS, Google Earth,
    Felt or geojson.io, or as GPX for OpenCPN and other plotters.

    No history yet? Choose **Demo passage** for a made-up day on the Firth of
    Clyde. It's picked for you when the server has no history provider.

    Cells run automatically as you change the inputs. If any look stale or empty,
    press **Run** (▶) at the bottom right of the page.

    **Limitations**

    - Loads GeoPandas, Shapely, pyproj, pandas and pyarrow when it opens, about
    20 MB, so the first visit takes a while.
    - The chart tiles come from OpenStreetMap, OpenSeaMap and Esri, so the map
    background needs an internet connection. Without one, the track is still
    drawn, on a blank background, and the downloads still work.
    - Legs and stops are worked out from position alone, by speed between fixes,
    so slow drifting can count as a stop, and a fast swing at anchor as a short
    leg. Adjust the thresholds to suit.

    Find the other notebooks in the [gallery](index.html).
    """)
    return


@app.cell(hide_code=True)
async def _():
    import sys as _sys

    if "pyodide" in _sys.modules:
        import micropip as _micropip
        import pyodide_js as _pyodide_js

        with mo.status.spinner(title="Loading GeoPandas…"):
            await _micropip.install(["shapely", "pyproj", "pandas", "pyarrow"])
            # Pyodide's geopandas also pulls in fiona and GDAL (about 17 MB),
            # which only file reading needs, so install its wheel on its own
            try:
                _wheel = _pyodide_js.lockfile.packages.geopandas.file_name
                await _micropip.install(f"{_pyodide_js.lockfileBaseUrl}{_wheel}", deps=False)
            except Exception:
                await _micropip.install("geopandas")

    # importlib, so marimo doesn't load Pyodide's geopandas, with fiona and
    # GDAL, as soon as it sees the import
    try:
        gpd = importlib.import_module("geopandas")
    except ImportError:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "GeoPandas isn't installed. Running locally, add it with "
                    "`uv run --with geopandas --with pyarrow marimo edit ...`"
                ),
                kind="danger",
            ),
        )
    return (gpd,)


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

    # Without a history provider there's nothing to fetch, so start on the demo
    source_input = mo.ui.radio(
        options=["SignalK history", "Demo passage"],
        value="SignalK history" if _provider_options else "Demo passage",
        label="Source",
        inline=True,
    )
    provider_input = mo.ui.dropdown(
        options=_provider_options,
        value=(_preferred or _provider_options or [None])[0],
        label="Provider",
    )
    duration_input = mo.ui.dropdown(
        options={
            "Last 6 hours": 6,
            "Last 24 hours": 24,
            "Last 3 days": 72,
            "Last 7 days": 168,
            "Last 30 days": 720,
        },
        value="Last 7 days",
        label="Duration",
    )
    resolution_input = mo.ui.dropdown(
        options={"10 seconds": 10, "30 seconds": 30, "1 minute": 60, "5 minutes": 300},
        value="1 minute",
        label="One fix every",
    )
    fetch_btn = mo.ui.run_button(label="Fetch track")
    return (
        duration_input,
        fetch_btn,
        provider_input,
        resolution_input,
        signalk_url,
        source_input,
    )


@app.cell(hide_code=True)
def _(
    duration_input,
    fetch_btn,
    provider_input,
    resolution_input,
    signalk_url,
    source_input,
):
    if source_input.value == "Demo passage":
        _controls = mo.md(
            "A made-up day on the Firth of Clyde, ending a few minutes ago: three "
            "hours at anchor off Millport, a sail to Largs, two hours with the "
            "instruments off, then alongside in Largs marina."
        )
    else:
        _controls = mo.vstack([
            mo.md(f"**History API Server** `{signalk_url}`"),
            mo.hstack(
                [provider_input, duration_input, resolution_input], justify="start", gap="1.5rem"
            ),
            fetch_btn,
        ])
    mo.vstack([source_input, _controls])
    return


@app.cell(hide_code=True)
async def _(
    duration_input,
    fetch_btn,
    provider_input,
    resolution_input,
    signalk_url,
    source_input,
):
    _now = datetime.now(timezone.utc).replace(microsecond=0)
    if source_input.value == "Demo passage":
        _payload = demo_payload(_now.replace(second=0) - timedelta(minutes=5))
    else:
        mo.stop(
            not fetch_btn.value, mo.callout(mo.md("Press **Fetch track** to load."), kind="info")
        )
        _params = {
            "paths": "navigation.position",
            "from": (_now - timedelta(hours=duration_input.value)).isoformat().replace("+00:00", "Z"),
            "to": _now.isoformat().replace("+00:00", "Z"),
            "resolution": str(resolution_input.value),
        }
        if provider_input.value:
            _params["provider"] = provider_input.value
        try:
            with mo.status.spinner(title="Fetching positions…"):
                _resp = await pyfetch(
                    f"{signalk_url}/signalk/v2/api/history/values?{urlencode(_params)}",
                    credentials="include",
                )
                _payload = json.loads(await _resp.string())
        except Exception as _e:
            mo.stop(True, mo.callout(mo.md(f"**Fetch failed**: {_e}"), kind="danger"))

    positions = parse_positions(_payload)
    mo.stop(
        positions.height < 2,
        mo.callout(mo.md("No `navigation.position` history in this time range."), kind="warn"),
    )
    mo.md(
        f"**{positions.height:,}** fixes from "
        f"{positions['timestamp'].min():%d %b %H:%M} to "
        f"{positions['timestamp'].max():%d %b %H:%M} UTC"
    )
    return (positions,)


@app.cell(hide_code=True)
def _():
    stop_below_input = mo.ui.slider(
        0.2, 3.0, step=0.1, value=1.0, label="Stopped below (knots)", show_value=True
    )
    min_stop_input = mo.ui.slider(
        5, 120, step=5, value=20, label="Shortest stop (minutes)", show_value=True
    )
    mo.vstack([
        mo.md(r"""
        ## Legs and stops

        The track is split wherever the boat's speed between fixes crosses the
        threshold. Stops shorter than the shortest stop are treated as part of
        the leg, such as heaving to or waiting for a bridge.
        """),
        mo.hstack([stop_below_input, min_stop_input], justify="start", gap="2rem"),
    ])
    return min_stop_input, stop_below_input


@app.cell(hide_code=True)
def _(gpd, min_stop_input, positions, stop_below_input):
    track = label_runs(
        add_motion(positions),
        stop_below_kn=stop_below_input.value,
        min_stop_minutes=min_stop_input.value,
    )
    legs_gdf, stops_gdf = build_passage(track)
    points_gdf = track_points(track)

    _under_way_h = legs_gdf["hours"].sum() if len(legs_gdf) else 0
    mo.hstack(
        [
            mo.stat(f"{len(legs_gdf)}", label="Legs"),
            mo.stat(f"{legs_gdf['distance_nm'].sum() if len(legs_gdf) else 0:.1f} nm", label="Distance run"),
            mo.stat(f"{_under_way_h:.1f} h", label="Under way"),
            mo.stat(f"{len(stops_gdf)}", label="Stops"),
            mo.stat(f"{gpd.__version__}", label="GeoPandas"),
        ],
        justify="start",
        gap="1rem",
    )
    return legs_gdf, points_gdf, stops_gdf, track


@app.cell(hide_code=True)
def _(legs_gdf, points_gdf, stops_gdf):
    legs_table = mo.ui.table(legs_gdf, selection="multi", page_size=10, label="Legs")
    stops_table = mo.ui.table(stops_gdf, selection="multi", page_size=10, label="Stops")
    points_table = mo.ui.table(points_gdf, selection=None, page_size=10, label="Track points")
    return legs_table, points_table, stops_table


@app.cell(hide_code=True)
def _(legs_gdf, legs_table, stops_gdf, stops_table):
    _selected_legs = legs_table.value["leg"].tolist() if len(legs_table.value) else []
    _selected_stops = stops_table.value["stop"].tolist() if len(stops_table.value) else []

    # Stops are drawn twice: the swing circle, then the anchoring position on top
    _circles = stops_gdf.set_geometry("swing_circle").drop(columns="geometry").rename_geometry("geometry")
    _collection = {
        "type": "FeatureCollection",
        "features": (
            features(legs_gdf, "leg", _selected_legs, "leg")
            + features(_circles, "stop", _selected_stops, "stop")
            + features(stops_gdf, "stop", _selected_stops, "stop")
        ),
    }
    mo.vstack([
        mo.md("Select legs or stops in the tables below to pick them out on the map."),
        mo.iframe(leaflet_page(_collection), height="560px"),
    ])
    return


@app.cell(hide_code=True)
def _(legs_table, points_table, stops_table):
    mo.vstack([
        mo.md(r"""
        ## Export

        Each table is a GeoPandas GeoDataFrame, so marimo's download button
        (below each table) offers **GeoJSON** and **GeoParquet** as well as CSV,
        JSON and Parquet. Stops have two geometry columns, the anchoring position
        and the swing circle; the download asks which one to use.

        - GeoJSON opens in [geojson.io](https://geojson.io), QGIS, Felt or Google
        Earth, and can be dropped onto most web maps.
        - GeoParquet keeps the column types and is far smaller, for QGIS, DuckDB
        (`spatial` extension) or GeoPandas.
        """),
        mo.ui.tabs({"Legs": legs_table, "Stops": stops_table, "Track points": points_table}),
    ])
    return


@app.cell(hide_code=True)
def _(stops_gdf, track):
    mo.vstack([
        mo.md(
            "Chart plotters and OpenCPN don't read GeoJSON, but do read GPX: a "
            "track for each leg, and a waypoint for each stop."
        ),
        mo.download(
            data=to_gpx(track, stops_gdf),
            filename="passage.gpx",
            mimetype="application/gpx+xml",
            label="Download GPX",
        ),
    ])
    return


@app.cell(hide_code=True)
def _(stop_below_input, track):
    # At most ~3,000 points, so long ranges still chart quickly
    _step = max(1, track.height // 3000)
    _speed = track.gather_every(_step).select("timestamp", "speed_kn", "state", "segment")
    _line = (
        alt.Chart(_speed)
        .mark_circle(size=12)
        .encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("speed_kn:Q", title="Speed over ground (knots)"),
            color=alt.Color(
                "state:N",
                scale=alt.Scale(domain=["under way", "stopped"], range=["#1f77b4", "#ff7f0e"]),
                title=None,
            ),
            tooltip=[
                alt.Tooltip("timestamp:T", format="%d %b %H:%M"),
                alt.Tooltip("speed_kn:Q", format=".1f", title="knots"),
                "segment:N",
            ],
        )
    )
    _threshold = (
        alt.Chart(pl.DataFrame({"y": [stop_below_input.value]}))
        .mark_rule(strokeDash=[4, 4], color="#888")
        .encode(y="y:Q")
    )
    mo.vstack([
        mo.md(
            "## Speed\n\nSpeed between fixes, worked out from position, with the "
            "stopped threshold dashed. Use it to tune the sliders above."
        ),
        (_line + _threshold).properties(height=220, width="container"),
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
def demo_fixes() -> list:
    """A synthetic passage on the Firth of Clyde, as (minute, longitude, latitude).

    One fix a minute: 3 h at anchor in Millport Bay swinging ~25 m, a ~3 nm
    passage at ~4.5 kn out of the bay, round the south-east corner of Great
    Cumbrae and up the Largs Channel, tacking mid-channel and with a 4 min
    slow patch that should stay part of the leg, into Largs Yacht Haven; then
    2 h with no data (instruments off) and 5 h alongside there. With the
    default sliders that is 1 leg and 2 stops, one at anchor and one alongside.
    The route was planned against OpenStreetMap's coastline, and every fix
    stays on the water. Seeded, so the same every time.
    """
    import itertools
    import math
    import random

    rng = random.Random(1)
    m_per_deg_lat = 111_320
    m_per_deg_lon = m_per_deg_lat * math.cos(math.radians(55.76))

    # Millport Bay anchorage, out of the bay, up the Largs Channel, then
    # through the marina entrance to a berth mid-basin
    route = [
        (-4.92200, 55.74940),
        (-4.91770, 55.74699),
        (-4.91770, 55.74605),
        (-4.91435, 55.74403),
        (-4.91267, 55.74430),
        (-4.91099, 55.74497),
        (-4.86238, 55.77232),
        (-4.86214, 55.77273),
        (-4.86046, 55.77273),
        (-4.85850, 55.77330),
    ]
    channel_leg = 5  # the open water stretch, where tacking is safe

    def jitter(lon, lat, metres):
        return (
            lon + rng.gauss(0, metres) / m_per_deg_lon,
            lat + rng.gauss(0, metres) / m_per_deg_lat,
        )

    # Positions along the route, one a minute at ~4.5 kn
    passage = []
    metres_a_minute = 4.5 / 1.943844 * 60
    for index, ((lon0, lat0), (lon1, lat1)) in enumerate(itertools.pairwise(route)):
        dx, dy = (lon1 - lon0) * m_per_deg_lon, (lat1 - lat0) * m_per_deg_lat
        length = math.hypot(dx, dy)
        across = (-dy / length, dx / length)
        steps = max(1, round(length / metres_a_minute))
        for step in range(steps):
            t = step / steps
            side = 0.0
            if index == channel_leg and 0.2 < t < 0.8:
                # Three tacks, up to ~100 m either side, easing in and out
                u = (t - 0.2) / 0.6
                side = 100 * math.sin(6 * math.pi * u) * math.sin(math.pi * u)
            passage.append((
                lon0 + dx * t / m_per_deg_lon + across[0] * side / m_per_deg_lon,
                lat0 + dy * t / m_per_deg_lat + across[1] * side / m_per_deg_lat,
            ))
            if index == channel_leg and step == steps // 2:
                # Slow for a few minutes, e.g. sorting out a fouled sheet
                for _ in range(4):
                    passage.append(passage[-1])
    passage.append(route[-1])

    fixes, minute = [], 0
    anchor_lon, anchor_lat = route[0]
    for i in range(180):
        angle = i / 30
        lon = anchor_lon + 25 * math.cos(angle) / m_per_deg_lon
        lat = anchor_lat + 25 * math.sin(angle) / m_per_deg_lat
        fixes.append((minute, *jitter(lon, lat, 2)))
        minute += 1
    for lon, lat in passage:
        fixes.append((minute, *jitter(lon, lat, 2)))
        minute += 1
    minute += 120
    berth_lon, berth_lat = route[-1]
    for _ in range(300):
        fixes.append((minute, *jitter(berth_lon, berth_lat, 2)))
        minute += 1
    return fixes


@app.function(hide_code=True)
def demo_payload(end: datetime) -> dict:
    """The demo passage as a History API /values response, ending at `end`."""
    fixes = demo_fixes()
    start = end - timedelta(minutes=fixes[-1][0])
    return {
        "context": "vessels.self",
        "values": [{"path": "navigation.position", "method": "average"}],
        "data": [
            [(start + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), [lon, lat]]
            for m, lon, lat in fixes
        ],
    }


@app.function(hide_code=True)
def parse_positions(payload: dict) -> pl.DataFrame:
    """Turn a History API /values response into timestamp, longitude, latitude rows.

    Positions arrive as [longitude, latitude] arrays, or from some providers as
    {"latitude", "longitude"} objects. Null Island (0, 0) and out of range
    values are dropped, as are repeated timestamps.
    """
    columns = payload.get("values", [])
    index = next(
        (i for i, c in enumerate(columns) if c.get("path") == "navigation.position"),
        None,
    )
    rows = []
    if index is not None:
        for row in payload.get("data", []):
            if len(row) <= index + 1:
                continue
            value = row[index + 1]
            if isinstance(value, list) and len(value) >= 2:
                lon, lat = value[0], value[1]
            elif isinstance(value, dict):
                lon, lat = value.get("longitude"), value.get("latitude")
            else:
                continue
            if not all(isinstance(v, (int, float)) for v in (lon, lat)):
                continue
            if abs(lon) > 180 or abs(lat) > 90 or (lon == 0 and lat == 0):
                continue
            rows.append((row[0], float(lon), float(lat)))

    return (
        pl.DataFrame(
            rows,
            schema={"timestamp": pl.String, "longitude": pl.Float64, "latitude": pl.Float64},
            orient="row",
        )
        .with_columns(
            pl.col("timestamp").str.to_datetime(
                format="%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC", time_unit="us", strict=False
            )
        )
        .drop_nulls()
        .sort("timestamp")
        .unique("timestamp", keep="first", maintain_order=True)
    )


@app.function(hide_code=True)
def add_motion(positions: pl.DataFrame) -> pl.DataFrame:
    """Add the distance from the previous fix (step_m), the time since it (gap_s)
    and speed over ground in knots, median-smoothed over 5 fixes to calm GPS
    jitter.
    """
    geod = importlib.import_module("pyproj").Geod(ellps="WGS84")
    lon = positions["longitude"].to_numpy()
    lat = positions["latitude"].to_numpy()
    step = np.zeros(len(lon))
    if len(lon) > 1:
        _, _, step[1:] = geod.inv(lon[:-1], lat[:-1], lon[1:], lat[1:])

    return (
        positions.with_columns(
            step_m=pl.Series(step),
            gap_s=pl.col("timestamp").diff().dt.total_milliseconds() / 1000,
        )
        .with_columns(
            raw_kn=pl.when(pl.col("gap_s") > 0).then(
                pl.col("step_m") / pl.col("gap_s") * MS_TO_KNOTS
            )
        )
        .with_columns(
            speed_kn=pl.col("raw_kn")
            .fill_null(strategy="backward")
            .fill_null(0.0)
            .rolling_median(window_size=5, center=True, min_samples=1)
        )
        .drop("raw_kn")
    )


@app.function(hide_code=True)
def label_runs(
    track: pl.DataFrame,
    stop_below_kn: float,
    min_stop_minutes: float,
    blip_minutes: float = 3.0,
    max_gap_minutes: float = 30.0,
) -> pl.DataFrame:
    """Split the track into alternating runs under way and stopped.

    Moving runs shorter than blip_minutes count as stopped (a swing at anchor),
    then stops shorter than min_stop_minutes count as under way (luffing up, or
    waiting for a bridge). A gap in the data longer than max_gap_minutes always
    starts a new run. Each run gets a label such as "Leg 2" or "Stop 3".
    """
    interval_s = track["gap_s"].median() or 0.0

    def runs(df):
        new_run = (pl.col("moving") != pl.col("moving").shift()) | (
            pl.col("gap_s") > max_gap_minutes * 60
        )
        df = df.with_columns(run=new_run.fill_null(True).cast(pl.Int32).cum_sum())
        span = (pl.col("timestamp").max() - pl.col("timestamp").min()).dt.total_milliseconds()
        return df.with_columns(run_minutes=((span / 1000 + interval_s) / 60).over("run"))

    df = runs(track.with_columns(moving=pl.col("speed_kn") >= stop_below_kn))
    df = runs(df.with_columns(moving=pl.col("moving") & (pl.col("run_minutes") >= blip_minutes)))
    df = runs(
        df.with_columns(moving=pl.col("moving") | (pl.col("run_minutes") < min_stop_minutes))
    )

    numbering = (
        df.group_by("run", maintain_order=True)
        .agg(pl.col("moving").first())
        .with_columns(number=pl.int_range(1, pl.len() + 1).over("moving"))
        .select("run", "number")
    )
    return (
        df.join(numbering, on="run")
        .with_columns(
            state=pl.when(pl.col("moving")).then(pl.lit("under way")).otherwise(pl.lit("stopped")),
            segment=pl.when(pl.col("moving"))
            .then(pl.format("Leg {}", pl.col("number")))
            .otherwise(pl.format("Stop {}", pl.col("number"))),
        )
        .drop("run_minutes")
    )


@app.function(hide_code=True)
def build_passage(track: pl.DataFrame) -> tuple:
    """Build GeoDataFrames of legs (LineStrings) and stops from a labelled track.

    Stops have two geometry columns: the anchoring position (a Point, the
    median fix) and swing_circle (a Polygon), the circle holding 95% of the
    fixes, which shows how far the boat swung on its anchor or mooring.
    Distances are geodesic, on the WGS84 ellipsoid.
    """
    gpd = importlib.import_module("geopandas")
    geometry = importlib.import_module("shapely.geometry")
    geod = importlib.import_module("pyproj").Geod(ellps="WGS84")

    runs = track.group_by("run", maintain_order=True).agg(
        pl.col("moving").first(),
        pl.col("number").first(),
        pl.col("timestamp"),
        pl.col("longitude"),
        pl.col("latitude"),
        pl.col("speed_kn"),
    )

    legs, stops, circles = [], [], []
    last_stop = None
    for run in runs.iter_rows(named=True):
        lon, lat = np.array(run["longitude"]), np.array(run["latitude"])
        start, end = run["timestamp"][0], run["timestamp"][-1]
        hours = (end - start).total_seconds() / 3600
        if run["moving"]:
            if len(lon) < 2:
                continue
            distance_nm = geod.line_length(lon, lat) / METRES_PER_NM
            legs.append({
                "leg": run["number"],
                "from_stop": last_stop,
                "to_stop": None,
                "start": start,
                "end": end,
                "hours": round(hours, 2),
                "distance_nm": round(distance_nm, 2),
                "avg_kn": round(distance_nm / hours, 1) if hours else None,
                "max_kn": round(max(run["speed_kn"]), 1),
                "geometry": geometry.LineString(zip(lon, lat)),
            })
        else:
            centre_lon, centre_lat = float(np.median(lon)), float(np.median(lat))
            _, _, dist = geod.inv(np.full(len(lon), centre_lon), np.full(len(lat), centre_lat), lon, lat)
            radius = max(float(np.quantile(dist, 0.95)), 5.0)
            bearings = np.linspace(0, 360, 65)
            ring_lon, ring_lat, _ = geod.fwd(
                np.full(65, centre_lon), np.full(65, centre_lat), bearings, np.full(65, radius)
            )
            stops.append({
                "stop": run["number"],
                "arrived": start,
                "departed": end,
                "hours": round(hours, 2),
                "swing_radius_m": round(radius),
                "kind": "alongside or in a marina" if radius < 15 else "at anchor or on a mooring",
                "geometry": geometry.Point(centre_lon, centre_lat),
            })
            circles.append(geometry.Polygon(zip(ring_lon, ring_lat)))
            if legs and legs[-1]["to_stop"] is None and legs[-1]["from_stop"] == last_stop:
                legs[-1]["to_stop"] = run["number"]
            last_stop = run["number"]

    leg_columns = ["leg", "from_stop", "to_stop", "start", "end", "hours", "distance_nm", "avg_kn", "max_kn"]
    stop_columns = ["stop", "arrived", "departed", "hours", "swing_radius_m", "kind"]
    legs_gdf = gpd.GeoDataFrame(
        legs or {c: [] for c in leg_columns},
        geometry=gpd.GeoSeries([leg["geometry"] for leg in legs], crs="EPSG:4326"),
        crs="EPSG:4326",
    )
    stops_gdf = gpd.GeoDataFrame(
        stops or {c: [] for c in stop_columns},
        geometry=gpd.GeoSeries([s["geometry"] for s in stops], crs="EPSG:4326"),
        crs="EPSG:4326",
    )
    stops_gdf["swing_circle"] = gpd.GeoSeries(circles, crs="EPSG:4326")
    return legs_gdf, stops_gdf


@app.function(hide_code=True)
def track_points(track: pl.DataFrame):
    """A GeoDataFrame with a Point per fix, for exporting the raw track."""
    gpd = importlib.import_module("geopandas")
    return gpd.GeoDataFrame(
        {
            "timestamp": track["timestamp"].to_list(),
            "speed_kn": track["speed_kn"].round(2).to_numpy(),
            "segment": track["segment"].to_list(),
        },
        geometry=gpd.points_from_xy(track["longitude"].to_numpy(), track["latitude"].to_numpy()),
        crs="EPSG:4326",
    )


@app.function(hide_code=True)
def features(gdf, kind: str, selected: list, key: str) -> list:
    """GeoJSON features for the map, with times as text and a selected flag."""
    columns = [c for c in gdf.columns if c != "swing_circle"]
    frame = gdf[columns].copy()
    for column in frame.columns:
        if str(frame[column].dtype).startswith("datetime"):
            frame[column] = frame[column].dt.strftime("%Y-%m-%d %H:%M UTC")
    collection = json.loads(frame.to_json(drop_id=True, na="null"))
    for feature in collection["features"]:
        feature["properties"]["kind_of_feature"] = kind
        feature["properties"]["selected"] = feature["properties"].get(key) in selected
    return collection["features"]


@app.function(hide_code=True)
def leaflet_page(collection: dict) -> str:
    """A self-contained Leaflet page drawing the passage over chart tiles.

    The page runs under Data Lab's cross-origin isolation (COEP require-corp), so
    every tile layer sets crossOrigin and uses servers that send CORS headers.
    """
    data = json.dumps(collection).replace("</", "<\\/")
    return (
        """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="anonymous">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin="anonymous"></script>
<style>
  html, body, #map { height: 100%; margin: 0; background: #dfe8ee; }
  .leaflet-popup-content table { border-collapse: collapse; font: 12px system-ui, sans-serif; }
  .leaflet-popup-content td { padding: 1px 6px; }
  .leaflet-popup-content td:first-child { color: #666; }
  .legend { background: #fff; padding: 6px 9px; font: 12px system-ui, sans-serif;
            border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.3); line-height: 1.5; }
  .legend i { display: inline-block; width: 14px; height: 4px; vertical-align: middle; margin-right: 6px; }
</style></head>
<body><div id="map"></div>
<script>
const data = """
        + data
        + """;
const map = L.map("map", { preferCanvas: true });
const tile = (url, attribution, maxZoom = 18) =>
  L.tileLayer(url, { attribution, maxZoom, crossOrigin: true });
const chart = tile("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', 19);
const satellite = tile(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  "Imagery &copy; Esri", 19);
const seamarks = tile("https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png",
  'Seamarks &copy; <a href="https://www.openseamap.org">OpenSeaMap</a>');
chart.addTo(map);
seamarks.addTo(map);

const palette = ["#1f77b4", "#2ca02c", "#9467bd", "#17becf", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"];
const anySelected = data.features.some((f) => f.properties.selected);
const popup = (p) => "<table>" + Object.entries(p)
  .filter(([k, v]) => v !== null && k !== "selected" && k !== "kind_of_feature")
  .map(([k, v]) => `<tr><td>${k.replaceAll("_", " ")}</td><td>${v}</td></tr>`).join("") + "</table>";

const style = (f) => {
  const p = f.properties, dim = anySelected && !p.selected;
  if (p.kind_of_feature === "leg") {
    return { color: p.selected ? "#d62728" : palette[(p.leg - 1) % palette.length],
             weight: p.selected ? 5 : 3, opacity: dim ? 0.35 : 0.9 };
  }
  return { color: "#ff7f0e", weight: p.selected ? 3 : 1.5, fillOpacity: dim ? 0.05 : 0.25,
           opacity: dim ? 0.4 : 1 };
};
const passage = L.geoJSON(data, {
  style,
  pointToLayer: (f, latlng) => L.circleMarker(latlng, {
    radius: f.properties.selected ? 7 : 5, color: "#fff", weight: 1.5,
    fillColor: "#ff7f0e", fillOpacity: anySelected && !f.properties.selected ? 0.4 : 1 }),
  onEachFeature: (f, layer) => {
    const p = f.properties;
    const title = p.kind_of_feature === "leg" ? `Leg ${p.leg}` : `Stop ${p.stop}`;
    layer.bindPopup(`<b>${title}</b>` + popup(p));
    layer.bindTooltip(title, { sticky: true });
  },
}).addTo(map);

const focus = anySelected
  ? L.geoJSON({ type: "FeatureCollection", features: data.features.filter((f) => f.properties.selected) })
  : passage;
const bounds = focus.getBounds();
if (bounds.isValid()) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 16 });
else map.setView([0, 0], 2);

L.control.layers({ "Chart": chart, "Satellite": satellite }, { "Seamarks": seamarks, "Passage": passage }).addTo(map);
L.control.scale({ imperial: false }).addTo(map);
const legend = L.control({ position: "bottomleft" });
legend.onAdd = () => {
  const div = L.DomUtil.create("div", "legend");
  div.innerHTML = '<i style="background:#1f77b4"></i>Legs under way<br>' +
    '<i style="background:#ff7f0e;height:10px;width:10px;border-radius:50%"></i>Stops, with swing circle';
  return div;
};
legend.addTo(map);
</script></body></html>"""
    )


@app.function(hide_code=True)
def to_gpx(track: pl.DataFrame, stops_gdf) -> bytes:
    """GPX 1.1 with a track per leg and a waypoint per stop, for chart plotters."""

    def stamp(t):
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="SignalK Data Lab" xmlns="http://www.topografix.com/GPX/1/1">',
    ]
    for stop in stops_gdf.itertuples():
        desc = f"{stop.kind}, {stop.hours} h, swing radius {stop.swing_radius_m} m"
        parts.append(
            f'<wpt lat="{stop.geometry.y:.7f}" lon="{stop.geometry.x:.7f}">'
            f"<time>{stamp(stop.arrived)}</time><name>Stop {stop.stop}</name>"
            f"<desc>{escape(desc)}</desc></wpt>"
        )
    for (name,), leg in track.filter(pl.col("moving")).group_by("segment", maintain_order=True):
        if leg.height < 2:
            continue
        points = "".join(
            f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}"><time>{stamp(t)}</time></trkpt>'
            for t, lon, lat in leg.select("timestamp", "longitude", "latitude").iter_rows()
        )
        parts.append(f"<trk><name>{escape(name)}</name><trkseg>{points}</trkseg></trk>")
    parts.append("</gpx>")
    return "\n".join(parts).encode("utf-8")


if __name__ == "__main__":
    app.run()
