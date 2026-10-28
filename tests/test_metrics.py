import pytest

from crowdshield.metrics import bias, by_bucket, mae, rmse, summarise


def test_mae_rmse_and_bias():
    pred, true = [10, 20, 30], [12, 18, 36]
    assert mae(pred, true) == pytest.approx(10 / 3)
    assert rmse(pred, true) == pytest.approx(((4 + 4 + 36) / 3) ** 0.5)
    assert bias(pred, true) == pytest.approx(-2)


def test_buckets_show_where_a_method_undercounts():
    true = [10, 40, 600, 800]
    pred = [10, 40, 300, 300]
    buckets = {b["range"]: b for b in by_bucket(pred, true)}
    assert set(buckets) == {"0-50", "500-1000"}
    assert buckets["0-50"]["mae"] == 0
    assert buckets["500-1000"]["bias"] == -400
    assert buckets["500-1000"]["images"] == 2


def test_open_ended_last_bucket():
    [bucket] = by_bucket([1500], [2000])
    assert bucket["range"] == "1000+"


def test_summarise_has_overall_and_bucket_errors():
    s = summarise([5, 15], [10, 10])
    assert s["mae"] == 5 and s["bias"] == 0
    assert s["buckets"][0]["images"] == 2
