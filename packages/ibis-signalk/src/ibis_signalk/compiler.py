from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import ibis.expr.operations as ops
from ibis.common.graph import Graph

from .datatypes import column_name_to_path


@dataclass
class HistoryRequest:
    """Direct mapping to History V2 `/values` query parameters."""

    paths: list[str] = field(default_factory=list)  # path[:method[:param]]
    from_: datetime | None = None
    to: datetime | None = None
    duration: str | None = None  # ISO 8601 duration, e.g. PT1H
    resolution: str | None = None  # seconds, or "1s"/"1m"/"1h"/"1d"
    context: str = "vessels.self"
    provider: str | None = None
    # Output column names, in the same order as `paths` — the ibis-expected
    # aliases, which may differ from the raw path (e.g. `by=[...]` group
    # aliases, or `.select(alias=col)` renames).
    column_names: list[str] = field(default_factory=list)
    timestamp_name: str = "timestamp"
    # Ungrouped aggregates (alias -> metric expression): the History API only
    # returns time series, so these are evaluated from the fetched rows
    # (see `local.py`)
    local_metrics: dict[str, ops.Node] = field(default_factory=dict)
    # Applied to the fetched result: (column, ascending) sort keys, then a slice
    sort_keys: list[tuple[str, bool]] = field(default_factory=list)
    limit: int | None = None
    offset: int = 0

    def to_params(self) -> dict[str, str]:
        p: dict[str, str] = {"paths": ",".join(self.paths)}
        if self.from_ is not None:
            p["from"] = self.from_.isoformat()
        if self.to is not None:
            p["to"] = self.to.isoformat()
        if self.duration:
            p["duration"] = self.duration
        if self.resolution:
            p["resolution"] = self.resolution
        if self.context != "vessels.self":
            p["context"] = self.context
        if self.provider:
            p["provider"] = self.provider
        return p


# Ibis reduction op class name -> SignalK History API method string
_AGG_METHOD: dict[str, str] = {
    "Mean": "average",
    "Min": "min",
    "Max": "max",
    "First": "first",
    "Last": "last",
}

# ops.TimestampTruncate unit name -> SignalK `resolution` string
_TRUNCATE_RESOLUTION: dict[str, str] = {
    "SECOND": "1s",
    "MINUTE": "1m",
    "HOUR": "1h",
    "DAY": "1d",
}


class SignalKCompiler:
    """Walks an Ibis op tree and produces a `HistoryRequest`.

    Only understands the operations the History API can push down server-side:
    plain column projection, timestamp range filters, and aggregation
    (optionally grouped by a truncated timestamp -> `resolution`). Anything
    else raises NotImplementedError, and the backend then runs the query
    locally over the fetched rows (see `Backend._fetch_local`).
    """

    def compile(self, node: ops.Node) -> HistoryRequest:
        req = HistoryRequest()
        self._visit(node, req)
        if not req.paths:
            # Only the timestamp was selected, but the History API needs at
            # least one path, so fetch the source table's paths for their
            # timestamps (e.g. `t.select("timestamp")`)
            for name in _source_table(node).schema.names:
                if name != "timestamp" and name not in req.column_names:
                    req.paths.append(column_name_to_path(name))
                    req.column_names.append(name)
        return req

    def _visit(self, op: ops.Node, req: HistoryRequest) -> None:
        if isinstance(op, (ops.UnboundTable, ops.DatabaseTable)):
            return
        if isinstance(op, ops.Project):
            self._visit(op.parent, req)
            self._apply_projection(op, req)
        elif isinstance(op, ops.Filter):
            self._visit(op.parent, req)
            self._apply_filters(op, req)
        elif isinstance(op, ops.Aggregate):
            self._visit(op.parent, req)
            self._apply_aggregate(op, req)
        elif isinstance(op, ops.Sort):
            # Sorted locally after fetching, as the API always returns time order
            self._visit(op.parent, req)
            for key in op.keys:
                if not isinstance(key.arg, ops.Field):
                    raise NotImplementedError("signalk backend can only sort by a column")
                name = req.timestamp_name if key.arg.name == "timestamp" else key.arg.name
                req.sort_keys.append((name, key.ascending))
        elif isinstance(op, ops.Limit):
            self._visit(op.parent, req)
            req.limit = _literal_int(op.n)
            req.offset = _literal_int(op.offset) or 0
        else:
            raise NotImplementedError(
                f"signalk backend cannot push down {type(op).__name__!r}"
            )

    def _apply_projection(self, op: ops.Project, req: HistoryRequest) -> None:
        paths = []
        names = []
        for alias, value in op.values.items():
            if not isinstance(value, ops.Field):
                raise NotImplementedError(
                    f"signalk backend can only push down plain column selections, "
                    f"got {type(value).__name__!r} for {alias!r}"
                )
            if value.name == "timestamp":
                req.timestamp_name = alias
                continue
            paths.append(column_name_to_path(value.name))
            names.append(alias)
        if paths:
            req.paths = paths
            req.column_names = names

    def _apply_filters(self, op: ops.Filter, req: HistoryRequest) -> None:
        for pred in op.predicates:
            if not (isinstance(pred.left, ops.Field) and pred.left.name == "timestamp"):
                raise NotImplementedError(
                    "signalk backend can only push down filters on the timestamp column"
                )
            value = _literal_value(pred.right)
            if isinstance(pred, (ops.Greater, ops.GreaterEqual)):
                req.from_ = value
            elif isinstance(pred, (ops.Less, ops.LessEqual)):
                req.to = value
            else:
                raise NotImplementedError(
                    f"signalk backend cannot push down filter {type(pred).__name__!r}"
                )

    def _apply_aggregate(self, op: ops.Aggregate, req: HistoryRequest) -> None:
        if not op.groups:
            self._apply_local_aggregate(op, req)
            return

        paths = []
        names = []
        for alias, metric in op.metrics.items():
            method = _AGG_METHOD.get(type(metric).__name__)
            arg = getattr(metric, "arg", None)
            if method is None or not isinstance(arg, ops.Field) or arg.name == "timestamp":
                raise NotImplementedError(
                    f"signalk backend can't push down {type(metric).__name__!r} in a time bucket"
                )
            paths.append(f"{column_name_to_path(arg.name)}:{method}")
            names.append(alias)
        req.paths = paths
        req.column_names = names

        for alias, group in op.groups.items():
            if isinstance(group, ops.TimestampTruncate):
                req.resolution = _TRUNCATE_RESOLUTION.get(group.unit.name, "1m")
                req.timestamp_name = alias

    def _apply_local_aggregate(self, op: ops.Aggregate, req: HistoryRequest) -> None:
        """Fetch the raw columns an ungrouped aggregate uses, to evaluate locally."""
        names: list[str] = []
        fetch_all = False
        for alias, metric in op.metrics.items():
            req.local_metrics[alias] = metric
            # Rows span all paths, so counting rows or reducing the timestamp
            # needs every path
            fetch_all |= bool(metric.find(ops.CountStar))
            for fld in metric.find(ops.Field):
                if fld.name == "timestamp":
                    fetch_all = True
                elif fld.name not in names:
                    names.append(fld.name)
        if fetch_all:
            names += [n for n in _source_table(op).schema.names if n not in names and n != "timestamp"]
        req.paths = [column_name_to_path(n) for n in names]
        req.column_names = names

    def fetch_request(self, root: ops.Node, source: ops.Node) -> HistoryRequest:
        """Request for all of `source`'s rows that `root` could need.

        Used when `root` can't be pushed down: the time range is widened to
        cover every timestamp filter applied directly to `source`, and left
        open (for the backend's default) if `source` is also used unfiltered.
        """
        froms: list = []
        tos: list = []
        unbounded_from = unbounded_to = False
        for node, children in Graph.from_bfs(root).items():
            if source not in children:
                continue
            if not isinstance(node, ops.Filter):
                unbounded_from = unbounded_to = True
                continue
            lower = upper = None
            for pred in node.predicates:
                if isinstance(pred.left, ops.Field) and pred.left.name == "timestamp":
                    try:
                        value = _literal_value(pred.right)
                    except NotImplementedError:
                        continue
                    if isinstance(pred, (ops.Greater, ops.GreaterEqual)):
                        lower = value
                    elif isinstance(pred, (ops.Less, ops.LessEqual)):
                        upper = value
            froms.append(lower)
            tos.append(upper)
            unbounded_from |= lower is None
            unbounded_to |= upper is None

        names = [n for n in source.schema.names if n != "timestamp"]
        return HistoryRequest(
            paths=[column_name_to_path(n) for n in names],
            column_names=names,
            from_=None if unbounded_from or not froms else min(froms),
            to=None if unbounded_to or not tos else max(tos),
        )


def _literal_int(value) -> int | None:
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, ops.Literal):
        return int(value.value)
    raise NotImplementedError("signalk backend can only limit by a literal number")


def _source_table(node: ops.Node) -> ops.Node:
    while not isinstance(node, (ops.UnboundTable, ops.DatabaseTable)):
        node = node.parent
    return node


def _literal_value(op: ops.Node) -> datetime | str:
    if isinstance(op, ops.Literal):
        return op.value
    if isinstance(op, ops.Cast):
        return _literal_value(op.arg)
    raise NotImplementedError(
        f"signalk backend can only push down literal filter values, got {type(op).__name__!r}"
    )
