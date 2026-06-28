"""Phase 5 gate: idempotent diff + 72h(+buffer) retention, no duplicate ids."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.diff import merge_and_retain, iso_now, parse_iso, RETENTION_HOURS, BUFFER_HOURS  # noqa: E402

NOW = datetime(2026, 6, 28, 6, 0, 0, tzinfo=timezone.utc)


def rec(tid, crit="routine", **kw):
    d = {"tender_id": tid, "title": f"t-{tid}", "criticality": crit}
    d.update(kw)
    return d


def test_new_id_gets_first_seen():
    out = merge_and_retain([rec("A")], [], now=NOW)
    assert len(out) == 1
    assert out[0]["first_seen"] == iso_now(NOW)
    assert out[0]["last_seen"] == iso_now(NOW)
    assert out[0]["status"] == "active"


def test_idempotent_no_duplicates():
    first = merge_and_retain([rec("A"), rec("B")], [], now=NOW)
    later = NOW + timedelta(hours=6)
    second = merge_and_retain([rec("A"), rec("B")], first, now=later)
    ids = [r["tender_id"] for r in second]
    assert sorted(ids) == ["A", "B"]
    assert len(ids) == len(set(ids))  # no dups
    a = next(r for r in second if r["tender_id"] == "A")
    assert a["first_seen"] == iso_now(NOW)        # preserved
    assert a["last_seen"] == iso_now(later)       # refreshed


def test_retention_drops_old_keeps_recent():
    total = RETENTION_HOURS + BUFFER_HOURS  # 120h served window
    old = {"tender_id": "OLD", "title": "old", "criticality": "routine",
           "first_seen": iso_now(NOW - timedelta(hours=total + 1)),
           "last_seen": iso_now(NOW - timedelta(hours=total + 1))}
    fresh = {"tender_id": "FRESH", "title": "fresh", "criticality": "routine",
             "first_seen": iso_now(NOW - timedelta(hours=total - 1)),
             "last_seen": iso_now(NOW - timedelta(hours=total - 1))}
    out = merge_and_retain([], [old, fresh], now=NOW)
    ids = {r["tender_id"] for r in out}
    assert "FRESH" in ids and "OLD" not in ids


def test_live_72h_boundary_for_dashboard():
    # A record at 73h is still in the served file (buffer) but the dashboard's
    # own 72h filter would drop it; we assert the served-file keeps it.
    r73 = {"tender_id": "X", "title": "x", "criticality": "critical",
           "first_seen": iso_now(NOW - timedelta(hours=73)),
           "last_seen": iso_now(NOW - timedelta(hours=73))}
    out = merge_and_retain([], [r73], now=NOW)
    assert any(r["tender_id"] == "X" for r in out)
    # And a record beyond buffer is gone.
    r200 = {"tender_id": "Y", "title": "y", "criticality": "routine",
            "first_seen": iso_now(NOW - timedelta(hours=200)),
            "last_seen": iso_now(NOW - timedelta(hours=200))}
    out2 = merge_and_retain([], [r73, r200], now=NOW)
    assert {r["tender_id"] for r in out2} == {"X"}


def test_critical_sorted_first():
    out = merge_and_retain([rec("R", "routine"), rec("C", "critical")], [], now=NOW)
    assert out[0]["tender_id"] == "C"


def test_iso_roundtrip():
    assert parse_iso(iso_now(NOW)) == NOW


if __name__ == "__main__":
    for n, fn in dict(globals()).items():
        if n.startswith("test_"):
            fn(); print("ok:", n)
    print("ALL DIFF TESTS PASSED")
