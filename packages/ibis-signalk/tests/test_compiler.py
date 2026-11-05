"""Ibis expression -> HistoryRequest, with no server involved."""

from __future__ import annotations

from datetime import datetime, timezone

import ibis
import pytest

from ibis_signalk import HistoryRequest, pick_provider
from ibis_signalk.compiler import SignalKCompiler

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 7, 2, tzinfo=timezone.utc)

nav = ibis.table(
    {
        "timestamp": "timestamp('UTC')",
        "navigation__speedOverGround": "float64",
        "navigation__headingTrue": "float64",
    },
    name="navigation",
)


def compile_(expr) -> HistoryRequest:
    return SignalKCompiler().compile(expr.as_table().op())


def test_column_names_map_back_to_paths():
    req = compile_(nav.select("timestamp", hdg="navigation__headingTrue"))
    assert req.paths == ["navigation.headingTrue"]
    assert req.column_names == ["hdg"]


def test_renamed_timestamp_is_kept():
    req = compile_(nav.select(time="timestamp", sog="navigation__speedOverGround"))
    assert req.timestamp_name == "time"


def test_timestamp_only_selection_still_requests_paths():
    # The History API needs at least one path to return timestamps
    req = compile_(nav.select("timestamp"))
    assert req.paths == ["navigation.speedOverGround", "navigation.headingTrue"]


@pytest.mark.parametrize(
    ("unit", "resolution"),
    [("s", "1s"), ("m", "1m"), ("h", "1h"), ("D", "1d")],
)
def test_truncate_unit_sets_resolution(unit, resolution):
    expr = nav.group_by(t=nav.timestamp.truncate(unit)).aggregate(
        v=nav.navigation__speedOverGround.min()
    )
    req = compile_(expr)
    assert req.resolution == resolution
    assert req.paths == ["navigation.speedOverGround:min"]
    assert req.timestamp_name == "t"


def test_strict_and_inclusive_range_filters():
    req = compile_(nav.filter(nav.timestamp > T0, nav.timestamp < T1))
    assert (req.from_, req.to) == (T0, T1)


@pytest.mark.parametrize(
    "expr",
    [
        # filters on values can't go to the server
        nav.filter(nav.navigation__speedOverGround > 1),
        # nor can computed columns
        nav.select(knots=nav.navigation__speedOverGround * 1.944),
        # nor reductions the API has no method for, in a time bucket
        nav.group_by(t=nav.timestamp.truncate("m")).aggregate(
            v=nav.navigation__speedOverGround.std()
        ),
    ],
    ids=["value-filter", "computed-column", "unsupported-bucket-method"],
)
def test_unsupported_expressions_raise_for_local_fallback(expr):
    with pytest.raises(NotImplementedError):
        compile_(expr)


def test_fetch_request_covers_every_filtered_use_of_a_table():
    early = nav.filter(nav.timestamp >= T0, nav.timestamp <= T0.replace(hour=6))
    late = nav.filter(nav.timestamp >= T1, nav.timestamp <= T1.replace(hour=6))
    root = early.union(late).op()

    req = SignalKCompiler().fetch_request(root, nav.op())
    assert req.from_ == T0
    assert req.to == T1.replace(hour=6)


def test_fetch_request_is_unbounded_if_table_is_also_used_unfiltered():
    filtered = nav.filter(nav.timestamp >= T1)
    root = filtered.union(nav).op()

    req = SignalKCompiler().fetch_request(root, nav.op())
    assert req.from_ is None and req.to is None


def test_to_params_omits_defaults():
    req = HistoryRequest(paths=["a.b", "c.d:max"], duration="PT1H")
    assert req.to_params() == {"paths": "a.b,c.d:max", "duration": "PT1H"}

    req = HistoryRequest(paths=["a.b"], from_=T0, to=T1, context="vessels.other", provider="p")
    assert req.to_params() == {
        "paths": "a.b",
        "from": T0.isoformat(),
        "to": T1.isoformat(),
        "context": "vessels.other",
        "provider": "p",
    }


@pytest.mark.parametrize(
    ("providers", "expected"),
    [
        (["kip", "signalk-parquet"], "signalk-parquet"),
        (["Kip-history"], "Kip-history"),
        ([], None),
    ],
)
def test_pick_provider_prefers_anything_but_kip(providers, expected):
    assert pick_provider(providers) == expected
