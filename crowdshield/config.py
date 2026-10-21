"""Shared constants: zones, risk tiers, density standards and detection models."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

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
