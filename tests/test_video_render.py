"""The annotated video: analysed with a stand-in counter, drawn, and written as browser-playable H.264."""

from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")

from crowdshield import video_render  # noqa: E402
from crowdshield.monitor import VideoMonitor, Zone, points_to_grid  # noqa: E402

CLIP = Path(__file__).resolve().parent.parent / "assets" / "samples" / "paris_saint_lazare.mp4"


def frames(limit=90):
    cap = cv2.VideoCapture(str(CLIP))
    for _ in range(limit):
        ok, f = cap.read()
        if not ok:
            break
        yield f
    cap.release()


def test_capacity_levels_match_the_live_feed():
    assert [video_render.capacity_level(p, 40) for p in (10, 20, 30, 40)] == ["Safe", "Moderate", "High Risk", "Critical"]
    assert video_render.capacity_level(10, None) is None


def test_an_analysed_clip_becomes_a_playable_annotated_video(tmp_path):
    zones = [("Stairs", [(428, 90), (640, 90), (640, 360), (428, 360)])]
    heads = [(200.0 + i, 500.0) for i in range(30)]
    monitor = VideoMonitor(lambda f: points_to_grid(heads, f.shape), 30.0, [Zone(n, p) for n, p in zones])
    rows, events = monitor.run(frames())
    out = video_render.render(frames(), 30.0, tmp_path / "out.mp4", zones, rows, events, {"Stairs": 40},
                              [np.array(heads)] * 3, monitor.count_every)
    meta = next(imageio_ffmpeg.read_frames(str(out)))
    assert meta["codec"] == "h264" and meta["size"] == (640, 360)
    cap = cv2.VideoCapture(str(out))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 90
    cap.set(cv2.CAP_PROP_POS_FRAMES, 45)
    ok, frame = cap.read()
    original = list(frames(46))[-1]
    assert ok and np.abs(frame.astype(int) - original.astype(int)).mean() > 2  # something was drawn on it


def test_a_surge_banner_shows_after_an_alarm():
    frame = np.zeros((360, 640, 3), np.uint8)
    calm = video_render.annotate(frame, 1.0, [], {}, {})
    alarm = video_render.annotate(frame, 1.0, [], {}, {}, surge="much faster than normal")
    assert alarm[-20:].mean() > calm[-20:].mean() + 20  # a red bar along the bottom
