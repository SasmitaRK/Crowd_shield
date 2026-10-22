"""Watch a camera from the command line, with no browser: count every few seconds and send alerts.

    python -m crowdshield.live_cli --source rtsp://192.168.1.20/stream --zones zones.json --interval 20 --notify

`zones.json` names each zone as a box (fractions of the picture: left, top, right, bottom) and how many
people it holds comfortably:

    {"Gate": {"box": [0.0, 0.4, 0.5, 1.0], "capacity": 60},
     "Stairs": {"box": [0.5, 0.2, 1.0, 1.0], "capacity": 40}}

With --notify, a new High Risk or Critical zone is sent to Telegram and email (whichever is set up
through TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID and GMAIL_USER / GMAIL_APP_PASSWORD). A camera on your own
network needs CROWDSHIELD_ALLOW_PRIVATE_URLS=1.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import notify
from .live import LiveMonitor, capacity_thresholds, check_url, grab_frame


def load_zones(path: Path, frame_shape) -> dict:
    h, w = frame_shape[:2]
    zones = {}
    for name, spec in json.loads(Path(path).read_text(encoding="utf-8")).items():
        x0, y0, x1, y1 = spec["box"]
        zones[name] = {"polygon": [(x0 * w, y0 * h), (x1 * w, y0 * h), (x1 * w, y1 * h), (x0 * w, y1 * h)],
                       "thresholds": capacity_thresholds(spec["capacity"]),
                       "area_m2": spec.get("area_m2")}
    return zones


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="rtsp:// or http(s):// stream, or a video file")
    ap.add_argument("--zones", required=True, type=Path)
    ap.add_argument("--interval", type=float, default=20.0, help="seconds between counts")
    ap.add_argument("--notify", action="store_true", help="send alerts to the channels that are set up")
    ap.add_argument("--once", action="store_true", help="count one frame and stop")
    args = ap.parse_args(argv)

    if "://" in args.source:
        ok, reason = check_url(args.source)
        if not ok:
            print(reason, file=sys.stderr)
            return 2
    from .points import point_grid

    frame = None
    while frame is None:
        frame = grab_frame(args.source)
        if frame is None:
            print("Could not read the stream; retrying in 10 s.", file=sys.stderr)
            time.sleep(10)
    monitor = LiveMonitor(load_zones(args.zones, frame.shape), point_grid)
    start = time.time()
    while True:
        result = monitor.update(time.time() - start, frame)
        stamp = time.strftime("%H:%M:%S")
        print(stamp, " | ".join(f"{z}: {r['count']:.0f} ({r['risk']})" for z, r in result["zones"].items()), flush=True)
        for event in result["events"]:
            text = notify.alert_text(event["zone"], event["zone"], event["risk"], event["count"],
                                     event["per_m2"], None if event["eta_s"] is None else event["eta_s"] / 60)
            print("  ALERT:", text.splitlines()[0], flush=True)
            if args.notify:
                for line in notify.broadcast(text):
                    print("  ", line, flush=True)
        if args.once:
            return 0
        time.sleep(max(1.0, args.interval))
        fresh = grab_frame(args.source)
        if fresh is not None:   # keep the last picture if the stream hiccups
            frame = fresh


if __name__ == "__main__":
    raise SystemExit(main())
