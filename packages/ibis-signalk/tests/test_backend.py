"""End-to-end through the backend, against the fake History API in conftest."""

from __future__ import annotations

import ibis
import pytest

from conftest import START, TIMESTAMPS


def test_connect_skips_kip_as_default_provider(con):
    assert con.provider == "signalk-parquet"


def test_tables_are_path_namespaces(con):
    assert con.list_tables() == ["environment", "navigation"]
    assert con.list_tables(like="nav") == ["navigation"]


def test_schema_maps_paths_to_columns(con):
    schema = con.table("navigation").schema()
    assert dict(schema.items()) == {
        "timestamp": ibis.dtype("timestamp('UTC')"),
        "navigation__speedOverGround": ibis.dtype("float64"),
        "navigation__courseOverGroundTrue": ibis.dtype("float64"),
        "navigation__position": ibis.dtype("json"),
        "navigation__datetime": ibis.dtype("string"),
    }


def test_text_paths_are_returned_as_text(con):
    df = con.table("navigation").select("timestamp", "navigation__datetime").execute()
    assert df["navigation__datetime"][0] == "2026-07-01T12:00:00.000Z"


def test_whole_namespace_loads_with_text_values(con):
    df = con.table("navigation").execute()
    assert len(df) == 5


def test_unexpected_text_in_a_numeric_path_becomes_null(con):
    t = con.table("environment")
    assert t.schema()["environment__forecast__description"] == ibis.dtype("float64")
    df = t.select("timestamp", "environment__forecast__description").execute()
    assert df["environment__forecast__description"].tolist()[2] == 3.5
    assert df["environment__forecast__description"].isna().sum() == 4


def test_select_fetches_only_the_selected_path(con, server):
    t = con.table("navigation")
    result = t.select("timestamp", sog="navigation__speedOverGround").to_pyarrow()

    [params] = server.values_requests()
    assert params["paths"] == "navigation.speedOverGround"
    assert params["provider"] == "signalk-parquet"
    # No start time, so the connection's default look-back
    assert params["duration"] == "PT1H"
    assert result.column_names == ["timestamp", "sog"]
    assert result["sog"].to_pylist() == [2.0, 2.5, 3.0, 3.5, None]


def test_timestamp_filters_become_the_request_range(con, server):
    t = con.table("navigation")
    expr = t.filter(t.timestamp >= TIMESTAMPS[1], t.timestamp <= TIMESTAMPS[3]).select(
        "timestamp", "navigation__speedOverGround"
    )
    result = expr.to_pyarrow()

    [params] = server.values_requests()
    assert params["from"] == TIMESTAMPS[1].isoformat()
    assert params["to"] == TIMESTAMPS[3].isoformat()
    assert "duration" not in params
    assert result.num_rows == 3


def test_open_ended_range_runs_to_now(con, server):
    t = con.table("navigation")
    t.filter(t.timestamp >= START).select("timestamp", "navigation__speedOverGround").to_pyarrow()

    [params] = server.values_requests()
    assert params["from"] == START.isoformat()
    # The History API needs a complete range, so `to` is filled in
    assert "to" in params


def test_time_bucketed_aggregate_is_pushed_down(con, server):
    t = con.table("navigation")
    expr = t.group_by(minute=t.timestamp.truncate("m")).aggregate(
        avg_sog=t.navigation__speedOverGround.mean(),
        max_cog=t.navigation__courseOverGroundTrue.max(),
    )
    result = expr.to_pyarrow()

    [params] = server.values_requests()
    assert params["paths"] == "navigation.speedOverGround:average,navigation.courseOverGroundTrue:max"
    assert params["resolution"] == "1m"
    assert set(result.column_names) == {"minute", "avg_sog", "max_cog"}


def test_overall_aggregates_are_computed_from_fetched_rows(con):
    t = con.table("navigation")
    sog = t.navigation__speedOverGround

    assert sog.mean().execute() == pytest.approx(2.75)
    assert sog.max().execute() == 3.5
    assert sog.count().execute() == 4  # the missing reading isn't counted
    assert t.count().execute() == 5


def test_sort_and_limit_apply_to_fetched_rows(con):
    t = con.table("navigation")
    expr = t.select("timestamp", sog="navigation__speedOverGround").order_by(ibis.desc("sog")).limit(2)
    assert expr.to_pyarrow()["sog"].to_pylist() == [3.5, 3.0]


def test_position_is_returned_as_json(con):
    t = con.table("navigation")
    df = t.select("timestamp", "navigation__position").execute()
    assert df["navigation__position"][0] == {"latitude": 55.9, "longitude": -4.9}


def test_empty_result_keeps_its_columns(con):
    t = con.table("navigation")
    later = TIMESTAMPS[-1].replace(year=2027)
    result = (
        t.filter(t.timestamp >= later, t.timestamp <= later)
        .select("timestamp", "navigation__speedOverGround")
        .to_pyarrow()
    )
    assert result.num_rows == 0
    assert result.column_names == ["timestamp", "navigation__speedOverGround"]


def test_join_across_tables_runs_locally_in_duckdb(con, server):
    pytest.importorskip("duckdb")
    nav = con.table("navigation").select("timestamp", sog="navigation__speedOverGround")
    env = con.table("environment").select("timestamp", aws="environment__wind__speedApparent")
    result = nav.join(env, "timestamp").order_by("timestamp").to_pyarrow()

    # One fetch per table, then joined locally
    assert len(server.values_requests()) == 2
    assert result["aws"].to_pylist() == [5.0, 6.0, 7.0, 8.0, 9.0]
    assert result["sog"].to_pylist() == [2.0, 2.5, 3.0, 3.5, None]


def test_backend_is_read_only(con):
    with pytest.raises(NotImplementedError):
        con.create_table("x", schema=ibis.schema({"a": "int"}))
