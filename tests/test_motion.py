import numpy as np
import pytest

from crowdshield.motion import SpeedAlarm, flow_stats
from eval.evaluate_motion import roc_auc, split_clips


def uniform_flow(dx, dy, shape=(64, 64)):
    flow = np.zeros((*shape, 2), dtype=np.float32)
    flow[..., 0], flow[..., 1] = dx, dy
    return flow


def test_everyone_moving_the_same_way_is_coherent():
    s = flow_stats(uniform_flow(3.0, 4.0))
    assert s["speed"] == pytest.approx(5.0)
    assert s["moving"] == pytest.approx(1.0)
    assert s["coherence"] == pytest.approx(1.0)
    assert s["turbulence"] == pytest.approx(0.0)


def test_opposite_flows_cancel_out_and_look_turbulent():
    flow = uniform_flow(2.0, 0.0)
    flow[::2, :, 0] = -2.0  # every other row walks the opposite way
    s = flow_stats(flow)
    assert s["coherence"] == pytest.approx(0.0, abs=1e-6)
    assert s["turbulence"] > 1.0


def test_still_scene_reports_no_movement():
    assert flow_stats(uniform_flow(0.1, 0.0))["moving"] == 0.0


def test_mask_excludes_pixels():
    flow = uniform_flow(1.0, 0.0)
    mask = np.ones(flow.shape[:2], dtype=bool)
    mask[:, :32] = False
    flow[:, :32] = 50.0  # a fast-moving overlay we want ignored
    assert flow_stats(flow, mask)["speed"] == pytest.approx(1.0)


def test_alarm_needs_a_sustained_jump_over_the_normal_pace():
    alarm = SpeedAlarm(baseline_frames=10, ratio=2.0, hold_frames=3)
    fired = [alarm.update(s) for s in [1.0] * 10 + [5.0, 1.0, 5.0, 5.0, 5.0, 5.0]]
    assert alarm.normal == pytest.approx(1.0)
    assert fired.index(True) == 14  # a lone spike doesn't count; three in a row do
    assert sum(fired) == 1


def test_alarm_re_arms_after_the_crowd_calms_down():
    alarm = SpeedAlarm(baseline_frames=5, ratio=2.0, hold_frames=2)
    speeds = [1.0] * 5 + [3.0] * 3 + [1.0] * 3 + [3.0] * 2
    assert sum(alarm.update(s) for s in speeds) == 2


def test_roc_auc():
    # positives 0.35 and 0.8 beat the negatives in 3 of 4 pairs
    assert roc_auc([0.1, 0.4, 0.35, 0.8], [False, False, True, True]) == pytest.approx(0.75)
    assert roc_auc([1, 1, 1, 1], [False, True, False, True]) == pytest.approx(0.5)


def test_clips_split_where_the_escape_label_turns_off():
    rows = [{"abnormal": bool(a)} for a in [0, 0, 1, 1, 0, 0, 1, 0]]
    assert split_clips(rows) == [(0, 4), (4, 7), (7, 8)]


def test_far_away_escape_is_caught_by_movement_energy_not_speed():
    from crowdshield.motion import MotionAlarm

    alarm = MotionAlarm(baseline_frames=10, speed_ratio=2.0, energy_ratio=8.0, hold_frames=3)
    calm = {"speed": 1.0, "energy": 0.02}
    for _ in range(10):
        assert not alarm.update(calm)
    # People far away start running: they look only 1.5x faster, but 10x more of the view moves.
    run = {"speed": 1.5, "energy": 0.2}
    fired = [alarm.update(run) for _ in range(5)]
    assert fired == [False, False, True, False, False]
    assert "movement" in alarm.reason


def test_energy_is_speed_times_moving_share():
    flow = np.zeros((10, 10, 2))
    flow[:5, :, 0] = 4.0  # half the view moves at 4 px per frame
    s = flow_stats(flow)
    assert s["energy"] == pytest.approx(s["speed"] * s["moving"]) == pytest.approx(2.0)
