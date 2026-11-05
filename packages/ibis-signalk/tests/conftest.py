"""A fake SignalK History API, so the backend can be tested without a server.

`get_json` is the backend's only way out to the network (catalog and
transport both import it), so replacing it there is enough. The fake records
each request, which lets tests check what was pushed down to the server as
well as what came back.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest

import ibis_signalk.catalog
import ibis_signalk.transport
from ibis_signalk import Backend

BASE_URL = "http://boat.local:3000"
START = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)

PATHS = [
    "navigation.speedOverGround",
    "navigation.courseOverGroundTrue",
    "navigation.position",
    "environment.wind.speedApparent",
]

# One row a minute for 5 minutes; the last speed is missing, as when a sensor
# drops out
ROWS = {
    "navigation.speedOverGround": [2.0, 2.5, 3.0, 3.5, None],
    "navigation.courseOverGroundTrue": [1.0, 1.1, 1.2, 1.3, 1.4],
    "navigation.position": [{"latitude": 55.9 + i / 1000, "longitude": -4.9} for i in range(5)],
    "environment.wind.speedApparent": [5.0, 6.0, 7.0, 8.0, 9.0],
}
TIMESTAMPS = [START + timedelta(minutes=i) for i in range(5)]


class FakeHistoryServer:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.providers = {"kip": {"isDefault": True}, "signalk-parquet": {"isDefault": False}}

    def get_json(self, url: str, params: dict[str, str] | None = None, timeout: float = 0):
        params = dict(params or {})
        endpoint = urlparse(url).path.rsplit("/", 1)[-1]
        self.requests.append((endpoint, params))
        if endpoint == "_providers":
            return self.providers
        if endpoint == "paths":
            return PATHS
        if endpoint == "values":
            return self._values(params)
        raise AssertionError(f"unexpected request to {url}")

    def _values(self, params: dict[str, str]) -> dict:
        # Echo each requested path:method back as a column; the method is
        # ignored, as the tests check the request rather than server maths
        specs = params["paths"].split(",")
        paths = [s.split(":")[0] for s in specs]
        start = datetime.fromisoformat(params["from"]) if "from" in params else None
        end = datetime.fromisoformat(params["to"]) if "to" in params else None
        data = []
        for i, ts in enumerate(TIMESTAMPS):
            if (start and ts < start) or (end and ts > end):
                continue
            stamp = ts.isoformat().replace("+00:00", "Z")
            data.append([stamp] + [ROWS[p][i] for p in paths])
        return {
            "context": "vessels.self",
            "values": [
                {"path": p, "method": s.split(":")[1] if ":" in s else "average"}
                for p, s in zip(paths, specs)
            ],
            "data": data,
        }

    def values_requests(self) -> list[dict[str, str]]:
        return [params for endpoint, params in self.requests if endpoint == "values"]


@pytest.fixture
def server(monkeypatch) -> FakeHistoryServer:
    fake = FakeHistoryServer()
    monkeypatch.setattr(ibis_signalk.catalog, "get_json", fake.get_json)
    monkeypatch.setattr(ibis_signalk.transport, "get_json", fake.get_json)
    return fake


@pytest.fixture
def con(server) -> Backend:
    backend = Backend()
    backend.do_connect(BASE_URL)
    return backend
