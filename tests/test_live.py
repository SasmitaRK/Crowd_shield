import json
from pathlib import Path

import numpy as np
import pytest

from crowdshield import live
from crowdshield.monitor import CELL, points_to_grid

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "samples" / "paris_saint_lazare.mp4"
SHAPE = (360, 640, 3)


def box(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def counter_with(people_left, people_right):
    """A fake counter: that many points in the left half and the right half of the frame."""
    def count(frame):
        pts = [(100.0 + i % 50, 50.0 + i % 200) for i in range(people_left)]
        pts += [(100.0 + i % 50, 400.0 + i % 200) for i in range(people_right)]
        return points_to_grid(pts or np.zeros((0, 2)), frame.shape)
    return count


def two_zones():
    return {"Left": {"polygon": box(0, 0, 320, 360), "thresholds": live.capacity_thresholds(40)},
            "Right": {"polygon": box(320, 0, 640, 360), "thresholds": live.capacity_thresholds(40)}}


def test_capacity_sets_the_risk_levels():
    assert live.capacity_thresholds(40) == {"moderate": 20, "high": 30, "critical": 40}


def test_counts_are_kept_per_zone_and_risk_follows_capacity():
    monitor = live.LiveMonitor(two_zones(), counter_with(10, 35))
    result = monitor.update(0.0, np.zeros(SHAPE, np.uint8))
    assert round(result["zones"]["Left"]["count"]) == 10 and result["zones"]["Left"]["risk"] == "Safe"
    assert round(result["zones"]["Right"]["count"]) == 35 and result["zones"]["Right"]["risk"] == "High Risk"


def test_a_zone_getting_worse_raises_one_event_not_one_per_frame():
    state = {"n": 10}
    monitor = live.LiveMonitor(two_zones(), lambda f: counter_with(state["n"], 0)(f), cooldown_s=600)
    frame = np.zeros(SHAPE, np.uint8)
    assert monitor.update(0, frame)["events"] == []
    state["n"] = 35
    events = monitor.update(30, frame)["events"]
    assert [(e["zone"], e["risk"]) for e in events] == [("Left", "High Risk")]
    assert monitor.update(60, frame)["events"] == []          # still High Risk: no repeat
    state["n"] = 45
    assert [(e["zone"], e["risk"]) for e in monitor.update(90, frame)["events"]] == [("Left", "Critical")]


def test_the_same_level_is_not_announced_again_inside_the_cooldown():
    state = {"n": 35}
    monitor = live.LiveMonitor(two_zones(), lambda f: counter_with(state["n"], 0)(f), cooldown_s=600)
    frame = np.zeros(SHAPE, np.uint8)
    assert monitor.update(0, frame)["events"]
    state["n"] = 5; monitor.update(30, frame)                  # calms down
    state["n"] = 35
    assert monitor.update(60, frame)["events"] == []           # back up within 10 minutes: stay quiet
    state["n"] = 5; monitor.update(700, frame); state["n"] = 35
    assert monitor.update(730, frame)["events"]                # long enough ago: announce again


def test_a_fast_build_up_is_flagged_before_the_limit():
    zones = {"Hall": {"polygon": box(0, 0, 320, 360), "thresholds": live.capacity_thresholds(100)}}
    series = iter([52, 55, 60, 74])                     # +42% in four samples, still under the 75 limit
    monitor = live.LiveMonitor(zones, lambda f: counter_with(next(series), 0)(f))
    frame = np.zeros(SHAPE, np.uint8)
    out = [monitor.update(30 * i, frame) for i in range(4)]
    assert all(r["events"] == [] for r in out[:-1])
    assert [(e["kind"], e["risk"]) for e in out[-1]["events"]] == [("build-up", "Moderate")]


def test_a_rising_trend_gives_a_time_to_full():
    series = iter([10, 14, 18, 22, 26])
    monitor = live.LiveMonitor(two_zones(), lambda f: counter_with(next(series), 0)(f))
    frame = np.zeros(SHAPE, np.uint8)
    last = [monitor.update(30 * i, frame) for i in range(5)][-1]
    eta = last["zones"]["Left"]["eta_s"]
    assert eta is not None and 100 < eta < 140                 # +4 per 30 s, 14 more to 40


@pytest.mark.parametrize("url", ["ftp://example.com/a", "file:///etc/passwd", "javascript:alert(1)", "http://"])
def test_odd_addresses_are_refused(url):
    ok, reason = live.check_url(url)
    assert not ok and reason


def test_private_and_local_addresses_are_refused_on_a_hosted_app(monkeypatch):
    for host in ("127.0.0.1", "192.168.1.20", "10.0.0.5", "169.254.169.254", "::1"):
        monkeypatch.setattr(live.socket, "getaddrinfo", lambda *a, h=host, **k: [(0, 0, 0, "", (h, 80))])
        ok, reason = live.check_url("http://camera.example/stream", allow_private=False)
        assert not ok and "private" in reason


def test_a_public_address_is_allowed_and_private_ones_can_be_enabled(monkeypatch):
    monkeypatch.setattr(live.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 80))])
    assert live.check_url("https://example.com/live.m3u8", allow_private=False)[0]
    monkeypatch.setattr(live.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("192.168.1.20", 554))])
    assert live.check_url("rtsp://192.168.1.20/stream", allow_private=True)[0]


cv2 = pytest.importorskip("cv2")


def test_frames_can_be_grabbed_from_a_file_and_a_missing_one_gives_none():
    frame = live.grab_frame(str(SAMPLE))
    assert frame is not None and frame.shape[1] <= live.MAX_WIDTH and frame.ndim == 3
    assert live.grab_frame("definitely_not_a_video.mp4", timeout_ms=1000) is None


def test_the_demo_feed_steps_through_the_clip_and_loops():
    feed = live.DemoFeed(SAMPLE, step_s=4.0)
    frames = [feed.next_frame() for _ in range(6)]             # 15 s clip: wraps after about 4 steps
    assert all(f is not None for f in frames)
    assert not np.array_equal(frames[0], frames[1])


def test_the_command_line_monitor_counts_one_frame(tmp_path, monkeypatch, capsys):
    from crowdshield import live_cli, points

    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({"Stairs": {"box": [0.6, 0.2, 1.0, 1.0], "capacity": 20},
                                 "Floor": {"box": [0.0, 0.5, 0.6, 1.0], "capacity": 20}}))
    monkeypatch.setattr(points, "point_grid", counter_with(25, 3))
    assert live_cli.main(["--source", str(SAMPLE), "--zones", str(zones), "--once"]) == 0
    out = capsys.readouterr().out
    assert "Stairs" in out and "Floor" in out


def test_the_command_line_monitor_writes_a_csv_log(tmp_path, monkeypatch, capsys):
    from crowdshield import live_cli, points

    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({"Stairs": {"box": [0.6, 0.2, 1.0, 1.0], "capacity": 20}}))
    monkeypatch.setattr(points, "point_grid", counter_with(25, 3))
    log = tmp_path / "counts.csv"
    for _ in range(2):  # a second run appends, with no second header
        assert live_cli.main(["--source", str(SAMPLE), "--zones", str(zones), "--once", "--log", str(log)]) == 0
    rows = log.read_text().splitlines()
    assert rows[0] == "time,zone,people,risk,minutes_to_full" and len(rows) == 3
    assert rows[1].split(",")[1] == "Stairs"


def test_a_bad_frame_does_not_stop_the_command_line_monitor(tmp_path, monkeypatch, capsys):
    from crowdshield import live_cli, points

    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({"Stairs": {"box": [0.6, 0.2, 1.0, 1.0], "capacity": 20}}))
    calls = {"n": 0}

    def flaky(frame):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("model hiccup")
        return counter_with(25, 3)(frame)

    monkeypatch.setattr(points, "point_grid", flaky)
    monkeypatch.setattr(live_cli.time, "sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt()) if calls["n"] >= 2 else None)
    assert live_cli.main(["--source", str(SAMPLE), "--zones", str(zones), "--interval", "1"]) == 0
    captured = capsys.readouterr()
    assert "Stairs" in captured.out and "Could not count this frame" in captured.err and "Stopped." in captured.out


@pytest.mark.parametrize("url, alias", [
    ("https://ipcamlive.com/6745eb6be37dd", "6745eb6be37dd"),
    ("https://g0.ipcamlive.com/player/player.php?alias=6745eb6be37dd&autoplay=1", "6745eb6be37dd"),
    ("http://s31.ipcamlive.com/streams/abc/stream.m3u8", None),
    ("https://example.com/6745eb6be37dd", None),
])
def test_ipcamlive_links_are_recognised(url, alias):
    assert live.ipcamlive_alias(url) == alias


def test_an_ipcamlive_page_is_turned_into_its_current_stream(monkeypatch):
    import io
    import urllib.request

    reply = {"details": {"streamavailable": "1", "streamid": "xyz", "address": "http://s31.ipcamlive.com/"}}
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(reply).encode()))
    assert live.resolve_stream("https://ipcamlive.com/6745eb6be37dd") == (
        "http://s31.ipcamlive.com/streams/xyz/stream.m3u8", "")
    reply["details"]["streamavailable"] = "0"
    stream, why = live.resolve_stream("https://ipcamlive.com/6745eb6be37dd")
    assert stream is None and "offline" in why
    assert live.resolve_stream("rtsp://cam.example.com/live") == ("rtsp://cam.example.com/live", "")
