"""
queries/loader.py
─────────────────
Loads all TOML query files once at import time and exposes typed namespaces.

Usage
-----
    from queries.loader import EmployeeQ, AttendanceQ, BreakQ, LeaveQ

    row = await conn.fetchrow(EmployeeQ.employee.insert, name, photo, encoding)
"""

import tomllib
from pathlib import Path
from types import SimpleNamespace

_QUERIES_DIR = Path(__file__).parent


def _load(filename: str) -> SimpleNamespace:
    """Parse a TOML file into a nested SimpleNamespace for dot-access."""
    path = _QUERIES_DIR / filename
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    def _ns(obj):
        if isinstance(obj, dict):
            return SimpleNamespace(**{k: _ns(v) for k, v in obj.items()})
        return obj

    return _ns(raw)


# ── Public singletons ─────────────────────────────────────────────────────────

EmployeeQ   = _load("Employeequeries.toml")
AttendanceQ = _load("Attendancequeries.toml")
BreakQ      = _load("Breakqueires.toml")
LeaveQ      = _load("Leavequeries.toml")