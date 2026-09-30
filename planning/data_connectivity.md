# Code-less SignalK Data Integration

Integrate data from the SignalK History API so that it can be browsed, queried and extracted without coding by clicking thru the Marimo Data Sources data discovery (and be accessed in code via similar), including choice of aggregation and duration.

This will probably use ADBC and Ibis Framework for extensible zero-copy data movement, although other options may work. DuckDb is not favoured since that will require movement and
transformation of data from History API to DuckDb native store.

Storage will be in memory, since predicate push down means filtering and summation happens on server-side, and data volumes expected to in the low 10s of MB.

## Test Environment

SignalK History API at http://10.36.10.20/signalk/v2/api/history

## Discovery

**Aggregation is per-path in the `paths` param:**

```
paths=navigation.speedOverGround:sma:5,navigation.speedThroughWater:max
```

So `method` and `parameter` are encoded _into the path string_, not separate params. The compiler needs to encode Ibis aggregation ops into that syntax.

**`resolution` replaces `interval`** — time window length in seconds or `1s`/`1m`/`1h`/`1d`.

---

## Architecture

The data shape means the transport layer is extremely clean:

```python
# data[0] is always timestamp, data[1..n] are path values in paths order
# → pa.RecordBatch directly from the raw arrays, no reshape needed
```

And the path-level aggregation encoding means the compiler needs to handle it at the **column level**, not the table level — which maps nicely to Ibis's per-column reduction ops.

---

## Module Sketches

### `datatypes.py`

```python
from __future__ import annotations
import ibis.expr.datatypes as dt

# SignalK uses SI units throughout — speeds in m/s, angles in radians, etc.
# Map path prefixes to Arrow/Ibis types
_PREFIX_TYPES: dict[str, dt.DataType] = {
    "navigation.speedOverGround":        dt.float64(),
    "navigation.speedThroughWater":      dt.float64(),
    "navigation.courseOverGroundTrue":   dt.float64(),
    "navigation.courseOverGroundMag":    dt.float64(),
    "navigation.headingTrue":            dt.float64(),
    "navigation.headingMagnetic":        dt.float64(),
    "navigation.position":               dt.json(),   # {lat, lon} object
    "environment.wind.speedTrue":        dt.float64(),
    "environment.wind.speedApparent":    dt.float64(),
    "environment.wind.angleTrue":        dt.float64(),
    "environment.wind.angleTrueWater":   dt.float64(),
    "environment.wind.angleApparent":    dt.float64(),
    "environment.depth.belowKeel":       dt.float64(),
    "environment.depth.belowSurface":    dt.float64(),
    "environment.water.temperature":     dt.float64(),
}

def path_to_ibis_type(path: str) -> dt.DataType:
    return _PREFIX_TYPES.get(path, dt.float64())

def path_to_column_name(path: str) -> str:
    """navigation.speedOverGround → navigation__speedOverGround"""
    return path.replace(".", "__")

def column_name_to_path(col: str) -> str:
    return col.replace("__", ".", 1)
```

---

### `compiler.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class HistoryRequest:
    """Direct mapping to History V2 query parameters."""
    paths: list[str]                    # path[:method[:param]]
    from_: datetime | None = None
    to: datetime | None = None
    duration: str | None = None         # ISO 8601 duration e.g. PT1H
    resolution: str | None = None       # e.g. "1m", "30s"
    context: str = "vessels.self"
    provider: str | None = None

    def to_params(self) -> dict[str, str]:
        p: dict[str, str] = {"paths": ",".join(self.paths)}
        if self.from_:      p["from"] = self.from_.isoformat()
        if self.to:         p["to"] = self.to.isoformat()
        if self.duration:   p["duration"] = self.duration
        if self.resolution: p["resolution"] = self.resolution
        if self.context != "vessels.self": p["context"] = self.context
        if self.provider:   p["provider"] = self.provider
        return p


# Ibis aggregation op name → SignalK method string
_AGG_MAP: dict[str, str] = {
    "Mean":    "average",
    "Min":     "min",
    "Max":     "max",
    "First":   "first",
    "Last":    "last",
}

import ibis.expr.operations as ops
import ibis.expr.types as ir

class SignalKCompiler:

    def compile(self, expr: ir.Expr) -> HistoryRequest:
        req = HistoryRequest(paths=[])
        self._visit(expr.op(), req)
        return req

    def _visit(self, op, req: HistoryRequest) -> None:
        match type(op).__name__:

            case "UnboundTable":
                # table name encodes namespace; paths populated from schema
                for name in op.schema.names:
                    if name != "timestamp":
                        req.paths.append(column_name_to_path(name))

            case "Selection":
                self._visit(op.table, req)
                for pred in op.predicates:
                    self._apply_filter(pred, req)
                if op.selections:
                    # column pruning — only request selected paths
                    selected = [
                        column_name_to_path(c.name)
                        for c in op.selections
                        if hasattr(c, "name") and c.name != "timestamp"
                    ]
                    if selected:
                        req.paths = selected

            case "Aggregation":
                self._visit(op.table, req)
                self._apply_aggregation(op, req)

    def _apply_filter(self, pred, req: HistoryRequest) -> None:
        match type(pred).__name__:
            case "Greater" | "GreaterEqual":
                if _is_timestamp_col(pred.left):
                    req.from_ = _literal_value(pred.right)
            case "Less" | "LessEqual":
                if _is_timestamp_col(pred.left):
                    req.to = _literal_value(pred.right)

    def _apply_aggregation(self, op, req: HistoryRequest) -> None:
        # op.metrics: list of reduction ops on columns
        # encode as path:method into paths list
        encoded: list[str] = []
        for metric in op.metrics:
            agg_name = type(metric).__name__
            method = _AGG_MAP.get(agg_name, "average")
            path = column_name_to_path(metric.arg.name)

            # SMA/EMA carry a window parameter
            if agg_name == "Mean" and hasattr(metric, "where"):
                encoded.append(f"{path}:{method}")
            else:
                encoded.append(f"{path}:{method}")

        if encoded:
            req.paths = encoded

        # GroupBy on time → resolution
        for key in op.by:
            if hasattr(key, "resolution"):  # TimestampTruncate
                req.resolution = _truncate_to_resolution(key.unit)


def _is_timestamp_col(op) -> bool:
    return hasattr(op, "name") and op.name == "timestamp"

def _literal_value(op):
    return op.value

def _truncate_to_resolution(unit: str) -> str:
    return {"s": "1s", "m": "1m", "h": "1h", "D": "1d"}.get(unit, "1m")
```

---

### `transport.py`

```python
from __future__ import annotations
import pyarrow as pa
import pyarrow.compute as pc
from datetime import datetime, timezone

try:
    import httpx
    _BACKEND = "httpx"
except ImportError:
    import pyodide.http as _pyodide_http  # type: ignore
    _BACKEND = "pyodide"


class SignalKTransport:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._endpoint = f"{self._base}/signalk/v2/api/history/values"

    def fetch(self, req: HistoryRequest) -> pa.Table:
        raw = self._get(req.to_params())
        return self._to_arrow(raw, req.paths)

    def _get(self, params: dict) -> dict:
        if _BACKEND == "httpx":
            import httpx
            r = httpx.get(self._endpoint, params=params)
            r.raise_for_status()
            return r.json()
        else:
            # Pyodide — sync wrapper around JS fetch
            import pyodide.http
            r = pyodide.http.open_url(
                self._endpoint + "?" +
                "&".join(f"{k}={v}" for k, v in params.items())
            )
            import json
            return json.loads(r.read())

    def _to_arrow(self, response: dict, paths: list[str]) -> pa.Table:
        data: list[list] = response["data"]
        if not data:
            schema = self._make_schema(paths)
            return schema.empty_table()

        # data rows: [timestamp_str, val0, val1, ...]
        # transpose list-of-rows → list-of-columns (one Python pass)
        transposed = list(zip(*data))

        ts_col = pa.array(
            [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in transposed[0]],
            type=pa.timestamp("us", tz="UTC"),
        )

        cols: list[pa.ChunkedArray | pa.Array] = [ts_col]
        names: list[str] = ["timestamp"]

        # base path without :method — strip aggregation suffix for column naming
        for i, path_expr in enumerate(paths):
            base_path = path_expr.split(":")[0]
            col_name = path_to_column_name(base_path)
            arr = pa.array(transposed[i + 1], type=pa.float64())  # nulls preserved
            cols.append(arr)
            names.append(col_name)

        return pa.table(dict(zip(names, cols)))

    def _make_schema(self, paths: list[str]) -> pa.Schema:
        fields = [pa.field("timestamp", pa.timestamp("us", tz="UTC"))]
        for p in paths:
            base = p.split(":")[0]
            fields.append(pa.field(path_to_column_name(base), pa.float64()))
        return pa.schema(fields)
```

---

### `catalog.py`

```python
from __future__ import annotations
import ibis
import ibis.expr.datatypes as dt
import httpx

class SignalKCatalog:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._paths_cache: list[str] | None = None

    def paths(self, duration: str = "P1D") -> list[str]:
        if self._paths_cache is None:
            r = httpx.get(
                f"{self._base}/signalk/v2/api/history/paths",
                params={"duration": duration}
            )
            self._paths_cache = r.json()  # ["navigation.speedOverGround", ...]
        return self._paths_cache

    def namespaces(self, duration: str = "P1D") -> list[str]:
        return sorted({p.split(".")[0] for p in self.paths(duration)})

    def schema_for(self, namespace: str, duration: str = "P1D") -> ibis.Schema:
        fields: dict[str, dt.DataType] = {"timestamp": dt.Timestamp(timezone="UTC")}
        for path in self.paths(duration):
            if path.split(".")[0] == namespace:
                fields[path_to_column_name(path)] = path_to_ibis_type(path)
        return ibis.Schema(fields)

    def providers(self) -> dict[str, dict]:
        r = httpx.get(f"{self._base}/signalk/v2/api/history/_providers")
        return r.json()
```

---

### `backend.py`

```python
from __future__ import annotations
import pyarrow as pa
import ibis.expr.types as ir
from ibis.backends.base import BaseBackend
from ibis import Schema
from .catalog import SignalKCatalog
from .compiler import SignalKCompiler
from .transport import SignalKTransport


class SignalKBackend(BaseBackend):
    name = "signalk"

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self._url = base_url
        self.catalog = SignalKCatalog(base_url)
        self._transport = SignalKTransport(base_url)
        self._compiler = SignalKCompiler()

    def do_connect(self, **kwargs) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def list_tables(self, **kwargs) -> list[str]:
        return self.catalog.namespaces()

    def get_schema(self, table_name: str, **kwargs) -> Schema:
        return self.catalog.schema_for(table_name)

    def table(self, name: str, **kwargs) -> ir.Table:
        schema = self.get_schema(name)
        return self._make_unbound_table(name, schema)  # ibis helper

    def execute(self, expr: ir.Expr, **kwargs) -> pa.Table:
        req = self._compiler.compile(expr)
        return self._transport.fetch(req)

    @property
    def version(self) -> str:
        return "0.1.0"
```

---

## Summary

- **Zero copy**: `zip(*data)` is one transpose pass, then straight into `pa.array()` — no intermediate dicts or dataframes
- **Aggregation pushdown**: `navigation.speedOverGround:sma:5` is built at compile time from Ibis ops, sent server-side, result is already reduced
- **`navigation.position`**: returns `{lat, lon}` objects — flagged as `dt.json()` in datatypes, needs special handling (either explode to two columns at fetch time, or leave as JSON and let user handle)
- **Pyodide swap**: only `transport._get()` needs changing — everything else is pure Python/Arrow

The main thing still to work out is how Ibis's `_make_unbound_table` / backend registration API looks in your specific Ibis version — that plumbing changed between 7.x and 9.x. Worth pinning and checking before building the compiler's op-tree matching against it.
