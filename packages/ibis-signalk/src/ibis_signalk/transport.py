from __future__ import annotations

import json
from datetime import datetime

import pyarrow as pa

from ._http import get_json
from .compiler import HistoryRequest
from .datatypes import path_to_column_name, path_to_ibis_type


class SignalKTransport:
    """Fetches data from the SignalK History API `/values` endpoint.

    Response shape (verified against a live server):
        {
          "context": "vessels.urn:...",
          "range": {"from": "...", "to": "..."},
          "values": [{"path": "navigation.speedOverGround", "method": "average"}, ...],
          "data": [["2026-07-01T19:49:49Z", 0.0154, ...], ...]
        }
    `values` gives the authoritative path/method per data column — more
    reliable than re-parsing the `path:method` strings we sent. Column types
    are still derived from `req.paths`, since most paths are plain floats but
    a few (e.g. `navigation.position`) come back as JSON objects/arrays and
    need to be serialized to match the `dt.json()` (arrow string) schema
    declared for them in `datatypes.py`, rather than coerced to float64.
    """

    def __init__(self, base_url: str) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/signalk/v2/api/history/values"

    def fetch(self, req: HistoryRequest) -> pa.Table:
        return self._to_arrow(get_json(self._endpoint, req.to_params()), req)

    def _to_arrow(self, payload: dict, req: HistoryRequest) -> pa.Table:
        columns = req.column_names or [
            path_to_column_name(v["path"]) for v in payload["values"]
        ]
        paths = req.paths or [v["path"] for v in payload["values"]]
        ibis_types = [path_to_ibis_type(p.split(":")[0]) for p in paths]
        arrow_types = [t.to_pyarrow() for t in ibis_types]
        timestamp_name = req.timestamp_name
        data: list[list] = payload["data"]

        if not data:
            fields = [pa.field(timestamp_name, pa.timestamp("us", tz="UTC"))]
            fields += [pa.field(name, t) for name, t in zip(columns, arrow_types)]
            return pa.schema(fields).empty_table()

        # rows -> columns in one transpose pass, straight into pa.array()
        transposed = list(zip(*data))

        ts_col = pa.array(
            [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in transposed[0]],
            type=pa.timestamp("us", tz="UTC"),
        )

        arrays = [ts_col]
        for i, (ibis_type, arrow_type) in enumerate(zip(ibis_types, arrow_types)):
            arrays.append(pa.array(_cells(transposed[i + 1], ibis_type), type=arrow_type))

        return pa.table(dict(zip([timestamp_name] + columns, arrays)))


def _cells(raw, ibis_type) -> list:
    """One column's values, made to fit the type declared for its path.

    Types come from path names, so a path can return something other than its
    declared type, e.g. text from a path the rules in datatypes.py don't know.
    A numeric column keeps numbers, with booleans (switches) as 1.0 and 0.0,
    and makes anything else null rather than failing the whole table.
    """
    if ibis_type.is_json():
        return [None if v is None else json.dumps(v) for v in raw]
    if ibis_type.is_string():
        return [None if v is None else v if isinstance(v, str) else json.dumps(v) for v in raw]
    return [float(v) if isinstance(v, (int, float)) else None for v in raw]
