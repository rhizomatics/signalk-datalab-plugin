from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from typing import Any, Mapping

import ibis
import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
import ibis.expr.types as ir
import pyarrow as pa
from ibis import Schema
from ibis.backends import BaseBackend

from .catalog import SignalKCatalog, pick_provider
from .compiler import HistoryRequest, SignalKCompiler
from .local import evaluate_metrics
from .transport import SignalKTransport


def _has_duckdb() -> bool:
    return importlib.util.find_spec("duckdb") is not None


class Backend(BaseBackend):
    """Read-only Ibis backend over the SignalK History API.

    Expressions the History API can answer directly (column selection, time
    range filters, time-bucketed aggregates) compile to a single request
    (`SignalKCompiler`), so filtering and aggregation happen server-side.
    Overall aggregates (`t.col.mean()`, `t.count()`, marimo's column stats)
    are computed from the fetched rows with pyarrow. Anything else, such as
    joins or the histograms marimo's data browser draws, needs the optional
    DuckDB extra (`ibis-signalk[duckdb]`), which runs the expression locally
    over the fetched rows; without it these raise NotImplementedError.
    """

    name = "signalk"
    dialect = None
    supports_temporary_tables = False
    supports_python_udfs = False

    def do_connect(
        self,
        base_url: str,
        provider: str | None = None,
        default_duration: str = "PT1H",
    ) -> None:
        """Connect to a SignalK server.

        `provider` picks the history provider; by default the first one that
        isn't Kip (see `pick_provider`). `default_duration` (ISO 8601) is the
        look-back used when a query has no start time, and the window over
        which tables and columns are discovered.
        """
        self.default_duration = default_duration
        self.catalog = SignalKCatalog(base_url)
        self.provider = provider or pick_provider(list(self.catalog.providers()))
        self.catalog.provider = self.provider
        self._transport = SignalKTransport(base_url)
        self._compiler = SignalKCompiler()

    def disconnect(self) -> None:
        pass

    @property
    def version(self) -> str:
        return "0.1.0"

    def list_tables(
        self, *, like: str | None = None, database: str | None = None
    ) -> list[str]:
        # Discover paths over the same window unfiltered queries cover
        names = self.catalog.namespaces(self.default_duration)
        return self._filter_with_like(names, like) if like else names

    def table(self, name: str, /, *, database: str | None = None) -> ir.Table:
        schema = self.catalog.schema_for(name, self.default_duration)
        return ops.DatabaseTable(name, schema, self).to_expr()

    def get_schema(self, table_name: str, /, *, database: str | None = None) -> Schema:
        return self.catalog.schema_for(table_name, self.default_duration)

    def compile(
        self,
        expr: ir.Expr,
        /,
        *,
        limit: int | None = None,
        params: Mapping[ir.Expr, Any] | None = None,
        **kwargs: Any,
    ) -> HistoryRequest:
        node = expr.as_table().op()
        return self._complete(self._compiler.compile(node))

    def _complete(self, req: HistoryRequest) -> HistoryRequest:
        req.provider = req.provider or self.provider
        # The History API needs a complete time range: from+to, or a duration
        if req.duration is None:
            if req.from_ is not None and req.to is None:
                req.to = datetime.now(timezone.utc)
            elif req.from_ is None:
                req.duration = self.default_duration
        return req

    def to_pyarrow(
        self,
        expr: ir.Expr,
        /,
        *,
        params: Mapping[ir.Expr, Any] | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> pa.Table:
        table = self._fetch(expr, limit=limit, params=params, **kwargs)
        return expr.__pyarrow_result__(table)

    def execute(
        self,
        expr: ir.Expr,
        /,
        *,
        params: Mapping[ir.Expr, Any] | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ):
        table = self._fetch(expr, params=params, limit=limit, **kwargs)
        return expr.__pandas_result__(table.to_pandas())

    def _fetch(self, expr: ir.Expr, **kwargs: Any) -> pa.Table:
        """Run `expr`, shaped as its table schema."""
        try:
            req = self.compile(expr, **kwargs)
            table = self._transport.fetch(req)
            if req.local_metrics:
                table = evaluate_metrics(table, req.local_metrics, req.timestamp_name)
        except NotImplementedError as e:
            if not _has_duckdb():
                raise NotImplementedError(
                    f"{e}; install ibis-signalk[duckdb] to run this query locally"
                ) from e
            return self._fetch_local(expr)
        if req.sort_keys:
            table = table.sort_by(
                [(name, "ascending" if asc else "descending") for name, asc in req.sort_keys]
            )
        if req.offset or req.limit is not None:
            table = table.slice(req.offset, req.limit)
        return table.select(list(expr.as_table().schema().names))

    def _fetch_local(self, expr: ir.Expr) -> pa.Table:
        """Fetch the rows `expr` needs, then run it locally in DuckDB.

        Only used when the optional DuckDB extra is installed.
        """
        root = expr.as_table().op()
        replacements = {}
        for source in root.find(ops.DatabaseTable):
            req = self._complete(self._compiler.fetch_request(root, source))
            rows = self._transport.fetch(req)
            # DuckDB would need its json extension, so keep JSON as plain strings
            schema = ibis.schema(
                {k: dt.string if v.is_json() else v for k, v in source.schema.items()}
            )
            replacements[source] = ibis.memtable(rows, schema=schema).op()
        local = root.replace(replacements).to_expr()
        return self._local.to_pyarrow(local)

    @property
    def _local(self):
        if getattr(self, "_local_con", None) is None:
            self._local_con = ibis.duckdb.connect()
        return self._local_con

    def _register_in_memory_table(self, op: ops.InMemoryTable) -> None:
        raise NotImplementedError("signalk backend is read-only")

    def _make_memtable_finalizer(self, name: str):
        return None

    def create_table(
        self,
        name: str,
        /,
        obj=None,
        *,
        schema: Schema | None = None,
        database: str | None = None,
        temp: bool = False,
        overwrite: bool = False,
    ) -> ir.Table:
        raise NotImplementedError("signalk backend is read-only")

    def create_view(
        self,
        name: str,
        /,
        obj: ir.Table,
        *,
        database: str | None = None,
        overwrite: bool = False,
    ) -> ir.Table:
        raise NotImplementedError("signalk backend is read-only")

    def drop_view(
        self, name: str, /, *, database: str | None = None, force: bool = False
    ) -> None:
        raise NotImplementedError("signalk backend is read-only")

    def drop_table(
        self, name: str, /, *, database: str | None = None, force: bool = False
    ) -> None:
        raise NotImplementedError("signalk backend is read-only")
