from __future__ import annotations

import ibis.expr.datatypes as dt

# SignalK uses SI units throughout — speeds in m/s, angles in radians, etc.
# Most paths are numbers, so anything not matched below is float64. The
# schema comes from path names alone (the History API's path list carries no
# types), so these rules cover the non-numeric paths in the SignalK spec; a
# path they miss still loads, with its non-numeric values as nulls (see
# transport.py).

# Objects and arrays, returned as JSON text
_JSON_PATHS = {
    "navigation.attitude",  # {roll, pitch, yaw}
    "navigation.gnss.satellitesInView",
    "design.aisShipType",
}
_JSON_SUFFIXES = (
    ".position",  # navigation.position, navigation.anchor.position, ...{latitude, longitude}
)
_JSON_PREFIXES = ("notifications.",)

# Plain text
_STRING_PATHS = {"name", "mmsi", "uuid", "url", "flag", "port"}
_STRING_SUFFIXES = (
    ".datetime",  # navigation.datetime, from NMEA RMC/ZDA: ISO 8601 text
    ".state",  # navigation.state, propulsion.*.state, steering.autopilot.state
    ".mode",  # steering.autopilot.mode, environment.mode
    ".methodQuality",  # navigation.gnss.*
    ".integrity",
    ".type",  # navigation.gnss.type
    ".chargingMode",  # electrical.chargers.*
    ".commonName",  # navigation.destination.commonName
    ".callsignVhf",
)


def path_to_ibis_type(path: str) -> dt.DataType:
    if path in _JSON_PATHS or path.endswith(_JSON_SUFFIXES) or path.startswith(_JSON_PREFIXES):
        return dt.json()
    if path in _STRING_PATHS or path.endswith(_STRING_SUFFIXES):
        return dt.string()
    return dt.float64()


def path_to_column_name(path: str) -> str:
    """navigation.speedOverGround -> navigation__speedOverGround"""
    return path.replace(".", "__")


def column_name_to_path(col: str) -> str:
    return col.replace("__", ".")
