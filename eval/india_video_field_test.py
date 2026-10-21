# Runs as a Kaggle script (GPU, internet on). Kept here so the field test can be reproduced.
"""Crowd Shield on real Indian crowd video: freely licensed Wikimedia Commons clips, analysed by the
app's own video monitor (PET head counts once a second, optical-flow speed and the panic alarm).

There's no ground truth for these clips, so this is a field demonstration, not an accuracy test:
for every clip it saves the per-second readings, any alarms, a timeline chart and the busiest frame
with its head dots, so a person can check the counts by eye.
"""
import json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

OUT = Path("/kaggle/working")
WORK = Path("/tmp/video"); WORK.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/khushi-git-7/Crowd_shield.git",
                str(WORK / "repo")], check=True)
sys.path.insert(0, str(WORK / "repo"))
subprocess.run(["nvidia-smi", "-L"])

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from crowdshield.monitor import VideoMonitor, Zone  # noqa: E402
from crowdshield.points import count_points, point_grid  # noqa: E402

UA = {"User-Agent": "CrowdShieldVideoTest/1.0 (https://github.com/khushi-git-7/Crowd_shield)"}
API = "https://commons.wikimedia.org/w/api.php"
OK_LIC = re.compile(r"^(CC BY(-SA)? [234]\.0|CC BY(-SA)? 2\.5|CC0|Public domain|PD)", re.I)
QUERIES = ["Kumbh Mela crowd", "Kumbh Mela", "crowd India", "India crowd", "pilgrims India", "procession India",
           "festival India crowd", "railway station India", "Mumbai local train", "Mumbai crowd", "Kolkata street",
           "Chennai street", "Madurai", "Tamil Nadu festival", "temple festival Kerala", "Delhi street",
           "Ganesh visarjan", "Ganesh Chaturthi procession", "Rath Yatra", "Durga Puja crowd",
           "Madurai Chithirai", "Kallazhagar", "Meenakshi temple festival", "Thrissur Pooram",
           "Varanasi Ganga aarti", "Kolkata crowd", "Delhi crowd", "Howrah", "Holi crowd"]
MAX_CLIPS, MAX_SECONDS, WIDTH = 20, 45, 960


def api(**params):
    params.update(format="json", formatversion=2)
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print("retry", e, flush=True); time.sleep(10 * (attempt + 1))
    return {}


found = json.loads('{"File:Narrow gauge railway line Gwalior to Sheopur.webm": {"query": "crowd India", "license": "CC BY 3.0", "duration": 58.03, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/3/38/Narrow_gauge_railway_line_Gwalior_to_Sheopur.webm/Narrow_gauge_railway_line_Gwalior_to_Sheopur.webm.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Narrow_gauge_railway_line_Gwalior_to_Sheopur.webm", "author": "Yann Forget"}, "File:Solar eclipse of 2019 in RSC, Kozhikode 01.ogv": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 24.0, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/7/75/Solar_eclipse_of_2019_in_RSC%2C_Kozhikode_01.ogv/Solar_eclipse_of_2019_in_RSC%2C_Kozhikode_01.ogv.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Solar_eclipse_of_2019_in_RSC,_Kozhikode_01.ogv", "author": "Subins2000"}, "File:A video clip of Rolls-Royce Holi in Kolkata 2026 packed with devotional energy color and street celebration.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 26.133, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/d/d2/A_video_clip_of_Rolls-Royce_Holi_in_Kolkata_2026_packed_with_devotional_energy_color_and_street_celebration.webm/A_video_clip_of_Rolls-Royce_Holi_in_Kolkata_2026_packed_with_devotional_energy_color_and_street_celebration.webm.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clip_of_Rolls-Royce_Holi_in_Kolkata_2026_packed_with_devotional_energy_color_and_street_celebration.webm", "author": "Sumita Roy Dutta"}, "File:A Video clip of When Rolls-Royce Goes Holi Mode in Howrah.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 25.878, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/b/be/A_Video_clip_of_When_Rolls-Royce_Goes_Holi_Mode_in_Howrah.webm/A_Video_clip_of_When_Rolls-Royce_Goes_Holi_Mode_in_Howrah.webm.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_Video_clip_of_When_Rolls-Royce_Goes_Holi_Mode_in_Howrah.webm", "author": "Sumita Roy Dutta"}, "File:A Video clip of Luxury Meets Color Rolls-Royce Holi Celebration in Howrah.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 16.92, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/4/49/A_Video_clip_of_Luxury_Meets_Color_Rolls-Royce_Holi_Celebration_in_Howrah.webm/A_Video_clip_of_Luxury_Meets_Color_Rolls-Royce_Holi_Celebration_in_Howrah.webm.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_Video_clip_of_Luxury_Meets_Color_Rolls-Royce_Holi_Celebration_in_Howrah.webm", "author": "Sumita Roy Dutta"}, "File:A Video clip of Royal to Rainbow- Rolls-Royce Holi Transformation.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 26.433, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/9/96/A_Video_clip_of_Royal_to_Rainbow-_Rolls-Royce_Holi_Transformation.webm/A_Video_clip_of_Royal_to_Rainbow-_Rolls-Royce_Holi_Transformation.webm.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_Video_clip_of_Royal_to_Rainbow-_Rolls-Royce_Holi_Transformation.webm", "author": "Sumita Roy Dutta"}, "File:A Video clip of Rolls-Royce Covered in Colors?! Holi Madness in Howrah.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 10.233, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/6/68/A_Video_clip_of_Rolls-Royce_Covered_in_Colors%3F%21_Holi_Madness_in_Howrah.webm/A_Video_clip_of_Rolls-Royce_Covered_in_Colors%3F%21_Holi_Madness_in_Howrah.webm.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_Video_clip_of_Rolls-Royce_Covered_in_Colors%3F!_Holi_Madness_in_Howrah.webm", "author": "Sumita Roy Dutta"}, "File:A Video clip of Color Splash on Rolls-Royce Epic Holi Vibes in Howrah.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 19.900000000000002, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/7/7d/A_Video_clip_of_Color_Splash_on_Rolls-Royce_Epic_Holi_Vibes_in_Howrah.webm/A_Video_clip_of_Color_Splash_on_Rolls-Royce_Epic_Holi_Vibes_in_Howrah.webm.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_Video_clip_of_Color_Splash_on_Rolls-Royce_Epic_Holi_Vibes_in_Howrah.webm", "author": "Sumita Roy Dutta"}, "File:A video clip of Colorful Dreams - Rolls-Royce Holi in Howrah.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 9.133000000000001, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/3/37/A_video_clip_of_Colorful_Dreams_-_Rolls-Royce_Holi_in_Howrah.webm/A_video_clip_of_Colorful_Dreams_-_Rolls-Royce_Holi_in_Howrah.webm.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clip_of_Colorful_Dreams_-_Rolls-Royce_Holi_in_Howrah.webm", "author": "Sumita Roy Dutta"}, "File:A video clip of Holi 2026 Special - Rolls-Royce Parade in Howrah.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 16.6, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/3/37/A_video_clip_of_Holi_2026_Special_-_Rolls-Royce_Parade_in_Howrah.webm/A_video_clip_of_Holi_2026_Special_-_Rolls-Royce_Parade_in_Howrah.webm.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clip_of_Holi_2026_Special_-_Rolls-Royce_Parade_in_Howrah.webm", "author": "Sumita Roy Dutta"}, "File:Crowd of Bhagoriya 2026 in Ranapur.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 10.8, "url": "https://upload.wikimedia.org/wikipedia/commons/1/14/Crowd_of_Bhagoriya_2026_in_Ranapur.webm?utm_source=commons.wikimedia.org&utm_campaign=api&utm_content=original", "page": "https://commons.wikimedia.org/wiki/File:Crowd_of_Bhagoriya_2026_in_Ranapur.webm", "author": "Herdaisymione"}, "File:A video clips of Rolls-Royce Holi through Howrah bridge 02.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 13.128, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/1/1f/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_02.webm/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_02.webm.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_02.webm", "author": "Sumita Roy Dutta"}, "File:A video clips of Rolls-Royce Holi through Howrah bridge 01.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 13.92, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/b/bc/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_01.webm/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_01.webm.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_01.webm", "author": "Sumita Roy Dutta"}, "File:A video clips of Rolls-Royce Holi through Howrah bridge 03.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 13.833, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/8/8f/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_03.webm/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_03.webm.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_03.webm", "author": "Sumita Roy Dutta"}, "File:A video clips of Rolls-Royce Holi through Howrah bridge 04.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 11.700000000000001, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/b/bb/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_04.webm/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_04.webm.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_04.webm", "author": "Sumita Roy Dutta"}, "File:A video clips of Rolls-Royce Holi through Howrah bridge 05.webm": {"query": "crowd India", "license": "CC BY-SA 4.0", "duration": 10.200000000000001, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/b/b6/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_05.webm/A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_05.webm.1080p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:A_video_clips_of_Rolls-Royce_Holi_through_Howrah_bridge_05.webm", "author": "Sumita Roy Dutta"}, "File:Naga Sadhu and Pilgrims - Gangasagar Fair Transit Camp - Kolkata 2013-01-12 2582.ogv": {"query": "pilgrims India", "license": "CC BY 3.0", "duration": 30.84, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/0/0e/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2582.ogv/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2582.ogv.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2582.ogv", "author": "Biswarup Ganguly"}, "File:Naga Sadhu and Pilgrims - Gangasagar Fair Transit Camp - Kolkata 2013-01-12 2583.ogv": {"query": "pilgrims India", "license": "CC BY 3.0", "duration": 45.48, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/c/ca/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2583.ogv/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2583.ogv.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2583.ogv", "author": "Biswarup Ganguly"}, "File:Naga Sadhu and Pilgrims - Gangasagar Fair Transit Camp - Kolkata 2013-01-12 2597.ogv": {"query": "pilgrims India", "license": "CC BY 3.0", "duration": 32.16, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/5/59/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2597.ogv/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2597.ogv.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2597.ogv", "author": "Biswarup Ganguly"}, "File:Naga Sadhu and Pilgrims - Gangasagar Fair Transit Camp - Kolkata 2013-01-12 2606.ogv": {"query": "pilgrims India", "license": "CC BY 3.0", "duration": 35.04, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/f/fc/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2606.ogv/Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2606.ogv.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Naga_Sadhu_and_Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2606.ogv", "author": "Biswarup Ganguly"}, "File:Pilgrims - Gangasagar Fair Transit Camp - Kolkata 2013-01-12 2655.ogv": {"query": "pilgrims India", "license": "CC BY 3.0", "duration": 17.52, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/7/71/Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2655.ogv/Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2655.ogv.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2655.ogv", "author": "Biswarup Ganguly"}, "File:Pilgrims - Gangasagar Fair Transit Camp - Kolkata 2013-01-12 2688.ogv": {"query": "pilgrims India", "license": "CC BY 3.0", "duration": 27.84, "url": "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/a3/Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2688.ogv/Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2688.ogv.480p.vp9.webm", "page": "https://commons.wikimedia.org/wiki/File:Pilgrims_-_Gangasagar_Fair_Transit_Camp_-_Kolkata_2013-01-12_2688.ogv", "author": "Biswarup Ganguly"}}')
(OUT / "video_candidates.json").write_text(json.dumps(found, indent=1, ensure_ascii=False))


def read(path):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = []
    while len(frames) < int(fps * MAX_SECONDS):
        ok, f = cap.read()
        if not ok:
            break
        if f.shape[1] > WIDTH:
            s = WIDTH / f.shape[1]
            f = cv2.resize(f, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        frames.append(f)
    cap.release()
    return frames, fps


summary = []
for title, meta in found.items():
    if len(summary) >= MAX_CLIPS:
        break
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title.replace("File:", ""))[:60].strip("_")
    path = WORK / (slug + ".webm")
    try:
        req = urllib.request.Request(meta["url"], headers=UA)
        path.write_bytes(urllib.request.urlopen(req, timeout=180).read())
        frames, fps = read(path)
    except Exception as e:
        print("skip", title, e); continue
    if len(frames) < fps * 8:
        print("too short / unreadable", title); continue
    first = count_points(frames[0])
    if first["count"] < 15:  # not a crowd scene
        print("few people", title, first["count"]); continue
    h, w = frames[0].shape[:2]
    zones = [Zone("Left", [(0, 0), (w // 2, 0), (w // 2, h), (0, h)]),
             Zone("Right", [(w // 2, 0), (w, 0), (w, h), (w // 2, h)])]
    shifts = []
    for a_, b_ in zip(frames[:-1:3], frames[1::3]):
        ga = np.float32(cv2.cvtColor(cv2.resize(a_, None, fx=.25, fy=.25), cv2.COLOR_BGR2GRAY))
        gb = np.float32(cv2.cvtColor(cv2.resize(b_, None, fx=.25, fy=.25), cv2.COLOR_BGR2GRAY))
        (dx, dy), _ = cv2.phaseCorrelate(ga, gb)
        shifts.append(4 * np.hypot(dx, dy) * fps)  # full-size px/s
    camera_px_s = float(np.median(shifts)) if shifts else 0.0
    t0 = time.time()
    rows, events = VideoMonitor(point_grid, fps, zones).run(frames)
    secs = time.time() - t0

    import pandas as pd
    df = pd.DataFrame(rows)
    d = OUT / slug; d.mkdir(exist_ok=True)
    df.to_csv(d / "readings.csv", index=False)
    total = df.groupby("t")["people"].sum()
    speed = df.groupby("t")["speed"].mean()
    fig, ax = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    ax[0].plot(total.index, total.values, color="#2a78d6", lw=2); ax[0].set_ylabel("People (frame)")
    ax[1].plot(speed.index, speed.values, color="#eb6834", lw=2); ax[1].set_ylabel("Speed (px/s)")
    for e in events:
        for a in ax:
            a.axvline(e["t"], color="#ef4444", lw=1, ls="--")
    ax[1].set_xlabel("Seconds"); fig.suptitle(title.replace("File:", "")[:80], fontsize=9)
    fig.tight_layout(); fig.savefig(d / "timeline.png", dpi=110); plt.close(fig)

    peak_t = float(total.idxmax())
    frame = frames[min(len(frames) - 1, int(peak_t * fps))]
    res = count_points(frame)
    vis = frame.copy()
    for r_, c_ in np.asarray(res["points"]).reshape(-1, 2):
        cv2.circle(vis, (int(c_), int(r_)), 3, (255, 200, 60), -1, cv2.LINE_AA)
    cv2.putText(vis, f"{round(res['count'])} people", (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
    cv2.imwrite(str(d / "peak_frame.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 85])

    item = dict(meta, title=title, slug=slug, fps=round(fps, 2), seconds=round(len(frames) / fps, 1),
                frame_size=[w, h], people_min=round(float(total.min())), people_max=round(float(total.max())),
                people_mean=round(float(total.mean())), peak_t=peak_t, events=events,
                camera_motion_px_s=round(camera_px_s, 1), handheld=camera_px_s > 40,
                analysis_seconds=round(secs, 1))
    summary.append(item)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print("done", title, item["people_mean"], len(events), flush=True)

print("clips analysed:", len(summary))
