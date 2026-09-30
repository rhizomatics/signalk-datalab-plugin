"""Local evaluation of ungrouped aggregates over fetched rows.

The History API only returns time series, so an aggregate without a time
bucket (e.g. `t.col.mean()`, `t.count()`, or marimo's column summaries such
as `col.isnull().sum() + col.isnan().sum()`) is computed here from the
fetched rows with pyarrow. Anything this can't evaluate raises
NotImplementedError, and the backend falls back to DuckDB if installed.
"""

from __future__ import annotations

from typing import Any

import ibis.expr.operations as ops
import pyarrow as pa
import pyarrow.compute as pc

_BINARY = {
    ops.Add: pc.add,
    ops.Subtract: pc.subtract,
    ops.Multiply: pc.multiply,
    ops.Divide: pc.divide,
}
_PREDICATES = {
    ops.IsNull: pc.is_null,
    ops.NotNull: pc.is_valid,
    ops.IsNan: pc.is_nan,
    ops.Not: pc.invert,
}


def evaluate_metrics(table: pa.Table, metrics: dict[str, ops.Node], timestamp_name: str) -> pa.Table:
    """Evaluate each metric expression to a one-row table."""
    columns = {}
    for alias, metric in metrics.items():
        value = _eval(metric, table, timestamp_name)
        if isinstance(value, (pa.Array, pa.ChunkedArray)):
            raise NotImplementedError(f"signalk backend expected a single value for {alias!r}")
        columns[alias] = pa.array([_as_py(value)], type=metric.dtype.to_pyarrow())
    return pa.table(columns)


def _as_py(value: Any) -> Any:
    return value.as_py() if isinstance(value, pa.Scalar) else value


def _eval(op: ops.Node, table: pa.Table, ts_name: str) -> Any:
    if isinstance(op, ops.Field):
        return table[ts_name if op.name == "timestamp" else op.name]
    if isinstance(op, ops.Literal):
        return pa.scalar(op.value)
    if isinstance(op, ops.Cast):
        return pc.cast(_eval(op.arg, table, ts_name), op.to.to_pyarrow())
    if isinstance(op, ops.ExtractEpochSeconds):
        arg = _eval(op.arg, table, ts_name)
        return pc.cast(pc.cast(arg, pa.timestamp("s", tz=arg.type.tz)), pa.int64())
    if isinstance(op, ops.Negate):
        return pc.negate(_eval(op.arg, table, ts_name))
    if type(op) in _BINARY:
        return _BINARY[type(op)](_eval(op.left, table, ts_name), _eval(op.right, table, ts_name))
    if type(op) in _PREDICATES:
        arg = _eval(op.arg, table, ts_name)
        if isinstance(op, ops.IsNan) and not pa.types.is_floating(arg.type):
            # Only floats can be NaN (e.g. position is a JSON string column)
            return pa.array([False] * len(arg), type=pa.bool_())
        return _PREDICATES[type(op)](arg)
    if isinstance(op, ops.CountStar):
        rows = table
        if op.where is not None:
            rows = table.filter(_eval(op.where, table, ts_name))
        return rows.num_rows
    if isinstance(op, ops.Reduction):
        return _reduce(op, table, ts_name)
    raise NotImplementedError(f"signalk backend cannot compute {type(op).__name__!r} locally")


def _reduce(op: ops.Reduction, table: pa.Table, ts_name: str) -> Any:
    values = _eval(op.arg, table, ts_name)
    where = getattr(op, "where", None)
    if where is not None:
        values = pc.filter(values, _eval(where, table, ts_name))
    present = pc.drop_null(values)

    if isinstance(op, ops.Count):
        return len(present)
    if isinstance(op, ops.CountDistinct):
        return pc.count_distinct(present).as_py()
    if isinstance(op, ops.Sum):
        return pc.sum(values)
    if isinstance(op, ops.Mean):
        return pc.mean(values)
    if isinstance(op, ops.Min):
        return pc.min(values)
    if isinstance(op, ops.Max):
        return pc.max(values)
    if isinstance(op, ops.Any):
        return pc.any(values)
    if isinstance(op, ops.All):
        return pc.all(values)
    if isinstance(op, (ops.StandardDev, ops.Variance)):
        ddof = 1 if op.how == "sample" else 0
        fn = pc.stddev if isinstance(op, ops.StandardDev) else pc.variance
        return fn(values, ddof=ddof)
    if isinstance(op, (ops.Median, ops.ApproxMedian)):
        return _quantile(present, 0.5)
    if isinstance(op, (ops.Quantile, ops.ApproxQuantile)):
        return _quantile(present, _as_py(_eval(op.quantile, table, ts_name)))
    # Rows come back in time order, so first/last are by position
    if isinstance(op, ops.First):
        return present[0] if len(present) else None
    if isinstance(op, ops.Last):
        return present[-1] if len(present) else None
    raise NotImplementedError(f"signalk backend cannot compute {type(op).__name__!r} locally")


def _quantile(values: Any, q: float) -> Any:
    if len(values) == 0:
        return None
    return pc.quantile(values, q=q, interpolation="linear")[0]
