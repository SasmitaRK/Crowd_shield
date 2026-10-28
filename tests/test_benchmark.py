import pytest

from crowdshield.benchmark import INDIA, _outside, accuracy, by_scene, load, scene_of

pytestmark = pytest.mark.skipif(not (INDIA / "labels.json").exists(), reason="India test set not present")


def test_pilot_numbers_match_the_published_ones():
    rows = load()
    assert len(rows) == 10
    assert sum(r["true"] for r in rows) == 3507
    assert accuracy(rows) == pytest.approx(0.911, abs=0.001)


def test_ignore_zones_drop_points_from_both_sides():
    assert _outside([[5, 5], [50, 50]], [[0, 0, 10, 10]]) == [[50, 50]]


def test_scenes_cover_every_photo():
    assert scene_of("Crowded Thane station") == "Stations and transport"
    assert {s["scene"] for s in by_scene(load())} <= {
        "Melas and pilgrimages", "Stations and transport", "Temples and processions", "Festivals",
        "Stadiums, ghats and rallies", "Streets and markets"}


def test_stored_points_are_drawn_where_the_heads_are():
    """Stored points are (x, y). Drawn as (row, column) they would land in the wrong place."""
    import numpy as np
    from crowdshield import benchmark

    assert benchmark.points_rc([(10, 20)]) == [(20, 10)]
    row = next(r for r in benchmark.load() if r["image"] == "IN_12.jpg")
    truth = np.array(row["truth_points"], float)
    drawn = np.array([(x, y) for y, x in benchmark.points_rc(row["model_points"])], float)
    nearest = np.median([np.min(np.hypot(*(truth - p).T)) for p in drawn])
    assert nearest < 40  # model points sit on the hand-marked heads
