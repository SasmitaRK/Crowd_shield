import math

import pytest

from crowdshield.geo import EARTH_RADIUS_M, adjacency, centroid, gap_m, haversine_m, ring_area_m2


def square(lon, lat, side_deg):
    return [[lon, lat], [lon + side_deg, lat], [lon + side_deg, lat + side_deg],
            [lon, lat + side_deg], [lon, lat]]


def test_area_of_a_small_square_at_the_equator():
    side_m = math.radians(0.001) * EARTH_RADIUS_M  # about 111.3 m
    assert ring_area_m2(square(0, 0, 0.001)) == pytest.approx(side_m ** 2, rel=1e-4)


def test_area_shrinks_with_latitude_like_the_map_does():
    # A degree of longitude is cos(lat) as wide, so the same square in degrees covers less ground.
    equator = ring_area_m2(square(81.88, 0, 0.001))
    prayagraj = ring_area_m2(square(81.88, 25.43, 0.001))
    assert prayagraj / equator == pytest.approx(math.cos(math.radians(25.43)), rel=1e-3)


def test_area_ignores_winding_order_and_the_closing_point():
    ring = square(10, 50, 0.002)
    assert ring_area_m2(ring[::-1]) == pytest.approx(ring_area_m2(ring))
    assert ring_area_m2(ring[:-1]) == pytest.approx(ring_area_m2(ring))


def test_haversine_matches_one_degree_of_latitude():
    assert haversine_m((0, 0), (0, 1)) == pytest.approx(math.radians(1) * EARTH_RADIUS_M)


def test_centroid_of_a_square_is_its_middle():
    lon, lat = centroid(square(81.88, 25.43, 0.002))
    assert lon == pytest.approx(81.881, abs=1e-6)
    assert lat == pytest.approx(25.431, abs=1e-6)


def test_gap_is_zero_for_touching_and_overlapping_zones():
    a = square(0, 0, 0.001)
    assert gap_m(a, square(0.001, 0, 0.001)) == 0        # shared edge
    assert gap_m(a, square(0.0005, 0.0005, 0.001)) == 0  # overlap
    assert gap_m(a, square(0.0002, 0.0002, 0.0002)) == 0  # one inside the other


def test_gap_between_separate_zones_is_the_distance_between_their_edges():
    gap = gap_m(square(0, 0, 0.001), square(0.002, 0, 0.001))
    assert gap == pytest.approx(math.radians(0.001) * EARTH_RADIUS_M, rel=1e-3)


def test_adjacency_links_only_zones_within_reach():
    zones = {"A": square(0, 0, 0.001), "B": square(0.001, 0, 0.001),
             "C": square(0.01, 0, 0.001)}
    assert adjacency(zones) == {"A": ["B"], "B": ["A"], "C": []}
    assert adjacency(zones, touch_m=2000)["C"] == ["A", "B"]


def test_degenerate_rings_are_rejected():
    with pytest.raises(ValueError):
        ring_area_m2([[0, 0], [1, 1]])
