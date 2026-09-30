from __future__ import annotations

import ibis
import ibis.expr.datatypes as dt

from ._http import get_json
from .datatypes import path_to_column_name, path_to_ibis_type


def pick_provider(provider_ids: list[str]) -> str | None:
    """Default history provider: the first that isn't Kip.

    SignalK often marks Kip as the default provider, but it often holds little
    history. Falls back to Kip if it's the only one.
    """
    preferred = [p for p in provider_ids if not p.lower().startswith("kip")]
    return (preferred or provider_ids or [None])[0]


class SignalKCatalog:
    def __init__(self, base_url: str, provider: str | None = None) -> None:
        self._base = base_url.rstrip("/")
        self.provider = provider
        self._paths_cache: dict[str, list[str]] = {}

    def paths(self, duration: str = "PT24H") -> list[str]:
        if duration not in self._paths_cache:
            params = {"duration": duration}
            if self.provider:
                params["provider"] = self.provider
            self._paths_cache[duration] = get_json(
                f"{self._base}/signalk/v2/api/history/paths", params
            )
        return self._paths_cache[duration]

    def namespaces(self, duration: str = "PT24H") -> list[str]:
        return sorted({p.split(".")[0] for p in self.paths(duration)})

    def schema_for(self, namespace: str, duration: str = "PT24H") -> ibis.Schema:
        fields: dict[str, dt.DataType] = {"timestamp": dt.Timestamp(timezone="UTC")}
        for path in self.paths(duration):
            if path.split(".")[0] == namespace:
                fields[path_to_column_name(path)] = path_to_ibis_type(path)
        return ibis.schema(fields)

    def providers(self) -> dict[str, dict]:
        return get_json(f"{self._base}/signalk/v2/api/history/_providers")
