"""
Sovereignty check for web/india-official.geojson.

Asserts that India's disputed / claimed regions fall INSIDE the rendered
landmass, so the dashboard always shows the complete sovereign map of India
(J&K & Ladakh incl. PoK, Gilgit-Baltistan, Aksai Chin, Shaksgam, Siachen; and
the full Arunachal Pradesh salient incl. Tawang).

Pure standard library — no GIS dependency. Run:  python tests/test_boundary.py
Also pytest-discoverable as test_sovereign_points().
"""
import json, os, sys

# (name, lon, lat) — must be INSIDE
SOVEREIGN = [
    ("Aksai Chin",            79.5, 35.1),
    ("Gilgit-Baltistan",      74.5, 35.9),
    ("PoK (Muzaffarabad)",    73.5, 34.4),
    ("Siachen",               77.0, 35.5),
    ("Shaksgam",              76.0, 36.0),
    ("Arunachal — Tawang",    91.86, 27.59),
    ("Arunachal — Anini",     95.9, 28.8),
    ("Arunachal — east tip",  97.0, 28.2),
    ("Kanyakumari (control)", 77.5, 8.1),
]
# (name, lon, lat) — must be OUTSIDE (open sea control)
OUTSIDE = [
    ("Bay of Bengal (control)", 88.0, 15.0),
]


def _find_geojson():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(here, "..", "web", "india-official.geojson"),
        os.path.join(here, "web", "india-official.geojson"),
        "web/india-official.geojson",
        "india-official.geojson",
    ):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError("india-official.geojson not found")


def _in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _in_polygon(lon, lat, polygon):
    # polygon = [outer_ring, hole1, hole2, ...]
    if not _in_ring(lon, lat, polygon[0]):
        return False
    for hole in polygon[1:]:
        if _in_ring(lon, lat, hole):
            return False
    return True


def _contains(lon, lat, geom):
    if geom["type"] == "Polygon":
        return _in_polygon(lon, lat, geom["coordinates"])
    if geom["type"] == "MultiPolygon":
        return any(_in_polygon(lon, lat, poly) for poly in geom["coordinates"])
    raise ValueError("unexpected geometry: " + geom["type"])


def _load_geom():
    gj = json.load(open(_find_geojson()))
    feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]
    return feats[0]["geometry"]


def test_sovereign_points():
    geom = _load_geom()
    failures = []
    for name, lon, lat in SOVEREIGN:
        if not _contains(lon, lat, geom):
            failures.append("EXPECTED INSIDE but OUTSIDE: " + name)
    for name, lon, lat in OUTSIDE:
        if _contains(lon, lat, geom):
            failures.append("EXPECTED OUTSIDE but INSIDE: " + name)
    assert not failures, "Boundary sovereignty check failed:\n  " + "\n  ".join(failures)


if __name__ == "__main__":
    try:
        test_sovereign_points()
    except AssertionError as e:
        print(e)
        sys.exit(1)
    geom = _load_geom()
    print("Sovereignty check PASSED — all claimed regions inside India:")
    for name, lon, lat in SOVEREIGN:
        print(f"  INSIDE   {name}")
    print("Controls (open sea) correctly OUTSIDE.")
