"""Phase 4 gate: offline geocoder resolves known pincodes/cities within tolerance."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.geocode import geocode, geocode_record  # noqa: E402


def near(a, b, tol=0.6):
    return math.isclose(a[0], b[0], abs_tol=tol) and math.isclose(a[1], b[1], abs_tol=tol)


def test_exact_pincode():
    assert near(geocode("786189"), (27.49, 95.36))      # Dinjan/Tinsukia (live scrape)
    assert near(geocode("400023"), (18.93, 72.83))      # Mumbai Fort
    assert near(geocode("530014"), (17.73, 83.30))      # Visakhapatnam


def test_pincode_with_spaces_or_noise():
    assert near(geocode("786 189"), (27.49, 95.36))
    assert near(geocode("Pin 786189"), (27.49, 95.36))


def test_city_name_fallback():
    assert near(geocode(None, "Kochi"), (9.931, 76.267))
    assert near(geocode(None, "Naval Base, Kochi"), (9.931, 76.267))
    assert near(geocode("", "Leh"), (34.152, 77.577))


def test_prefix_fallback_in_country():
    # Unknown exact pin, but 78xxxx -> Assam circle centroid (coarse, in-country).
    lat, lng = geocode("788701")
    assert lat is not None and lng is not None
    assert 6 < lat < 37 and 68 < lng < 98


def test_unresolvable_returns_none():
    assert geocode(None, "Atlantis") == (None, None)
    assert geocode("", "") == (None, None)


def test_triangulation_from_multiple_fields():
    # pincode wins when present
    assert near(geocode_record({"pincode": "786189"}), (27.49, 95.36))
    # else from the buyer address (Dist Tinsukia)
    assert near(geocode_record({"buyer_address": "GE Dinjan, Post Dinjan, Dist Tinsukia Assam"}),
                (27.49, 95.36))
    # else from the org-chain tail (CE SHILLONG ZONE -> Shillong)
    assert near(geocode_record({"org_chain": "MES ▸ CE EC AND CE SHILLONG ZONE"}), (25.57, 91.88))
    # else from a place name in the title (AFS KUMBHIRGRAM)
    assert near(geocode_record({"title": "RUNWAY WORKS AT AFS KUMBHIRGRAM"}), (24.91, 92.98))


def test_longest_place_wins():
    # 'new delhi' beats 'delhi'; 'port blair' resolves as a unit
    assert near(geocode_record({"location": "New Delhi"}), (28.613, 77.209))
    assert near(geocode_record({"title": "supply to HQ A&N Command Port Blair"}), (11.623, 92.726))


def test_record_prefix_fallback_and_none():
    assert geocode_record({"pincode": "788701"}) != (None, None)  # 78 -> Assam
    assert geocode_record({"title": "no place here", "pincode": ""}) == (None, None)


if __name__ == "__main__":
    for n, fn in dict(globals()).items():
        if n.startswith("test_"):
            fn(); print("ok:", n)
    print("ALL GEOCODE TESTS PASSED")
