"""Shared constants: zones, risk tiers, density standards and detection models."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Photos are shrunk so their longer side is at most this many pixels before counting. The
# networks' memory grows with pixel count, so a small server needs a smaller limit.
FULL_MAX_SIDE = 2048
# Measured peak memory of PET alone on a Kaggle CPU (results/pet_memory.json): 640 px 1.5 GB,
# 800 px 2.4 GB, 1024 px 2.8 GB, 1280 px 3.6 GB, 2048 px 8.4 GB. Streamlit Community Cloud gives
# an app about 2.7 GB, so it counts at 640 px; counts stay within a few percent.
SMALL_SERVER_MAX_SIDE = 640
SMALL_SERVER_BYTES = 6 * 1024 ** 3


def memory_limit_bytes() -> int | None:
    """The memory this process may use: the container's limit if it has one, else total RAM."""
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(path).read_text().strip()
        except OSError:
            continue
        if raw.isdigit() and int(raw) < 1 << 60:  # "max" or a huge number means no limit
            return int(raw)
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None


def on_streamlit_cloud() -> bool:
    """Streamlit Community Cloud checks apps out under /mount/src."""
    return str(REPO_ROOT).startswith("/mount/src")


def default_max_side() -> int:
    """CROWDSHIELD_MAX_SIDE if set; otherwise smaller on Streamlit Cloud or a small machine."""
    if os.environ.get("CROWDSHIELD_MAX_SIDE"):
        return int(os.environ["CROWDSHIELD_MAX_SIDE"])
    limit = memory_limit_bytes()
    if on_streamlit_cloud() or (limit is not None and limit < SMALL_SERVER_BYTES):
        return SMALL_SERVER_MAX_SIDE
    return FULL_MAX_SIDE

SEGMENTS = ["A", "B", "C", "D", "E"]
MAX_IMAGES_PER_SEGMENT = 4

RISK_LEVELS = ["Safe", "Moderate", "High Risk", "Critical"]

DEFAULT_THRESHOLDS = {
    "moderate": 30,
    "high":     60,
    "critical": 90,
}

# People per square metre at which each risk tier starts, after Fruin's
# Level of Service scale for pedestrian spaces.
FRUIN_PRESETS = {
    "Conservative (outdoor open areas)": {
        "moderate": 0.5,
        "high":     1.0,
        "critical": 2.0,
    },
    "Standard (mixed venues)": {
        "moderate": 1.0,
        "high":     2.0,
        "critical": 3.5,
    },
    "Crowded events / concerts": {
        "moderate": 1.5,
        "high":     3.0,
        "critical": 4.5,
    },
    "Enclosed corridors / gates": {
        "moderate": 0.5,
        "high":     1.0,
        "critical": 1.5,
    },
}

MODEL_REGISTRY = {
    "crowd_yolo": {
        "path":    "models/crowd_yolo.pt",
        "classes": [0, 1],
        "label":   "Custom Crowd YOLO (VisDrone best.pt)",
    },
    "yolov8l": {
        "path":    "models/yolov8l.pt",
        "classes": [0],
        "label":   "YOLOv8l (COCO standard large)",
    },
}
DEFAULT_MODEL_KEY = "crowd_yolo"

# Who counted a photo, as shown in the app.
COUNTER_LABELS = {
    "points":   "PET point model",
    "density":  "DM-Count density model",
    "detector": "YOLO (fallback)",
}

# Photo source -> model key; None means "use the globally selected model".
SOURCE_MODEL_MAP = {
    "auto":   None,
    "drone":  "crowd_yolo",
    "ground": "yolov8l",
}
