"""Shared crowd-detection logic used across all pages."""

import os
import cv2
import numpy as np
import streamlit as st

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

# Source → model key (mirrors shared_state for use inside detection)
_SOURCE_MODEL_MAP = {
    "auto":   None,
    "drone":  "crowd_yolo",
    "ground": "yolov8l",
}


@st.cache_resource(show_spinner="Loading detection model...")
def _load_yolo(model_key: str):
    try:
        from ultralytics import YOLO
        cfg = MODEL_REGISTRY.get(model_key, MODEL_REGISTRY[DEFAULT_MODEL_KEY])
        if os.path.exists(cfg["path"]):
            return YOLO(cfg["path"])
        return YOLO("yolov8n.pt")
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def _load_cascades():
    face = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_profileface.xml")
    return face, profile


def get_active_model_key() -> str:
    return st.session_state.get("active_model", DEFAULT_MODEL_KEY)


def load_models(model_key: str | None = None):
    if model_key is None:
        model_key = get_active_model_key()
    return _load_yolo(model_key), *_load_cascades()


# ---------------------------------------------------------------------------
# Risk level (4-tier)
# ---------------------------------------------------------------------------

def risk_level(count: int, thresholds: dict) -> str:
    """Return Safe / Moderate / High Risk / Critical."""
    if count < thresholds.get("moderate", 30):
        return "Safe"
    if count < thresholds.get("high", 60):
        return "Moderate"
    if count < thresholds.get("critical", 90):
        return "High Risk"
    return "Critical"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _iou(a, b):
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2 = min(ax1 + aw, bx1 + bw)
    iy2 = min(ay1 + ah, by1 + bh)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    return inter / (aw * ah + bw * bh - inter)


def _box_contains(outer, inner):
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    cx, cy = ix + iw // 2, iy + ih // 2
    return ox <= cx <= ox + ow and oy <= cy <= oy + oh


# ---------------------------------------------------------------------------
# Per-image detection (cached by bytes + model key)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="🔍 Analyzing image...")
def process_image(image_bytes: bytes, model_key: str = DEFAULT_MODEL_KEY) -> dict:
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"count": 0, "body_count": 0, "head_count": 0,
                "overlay": None, "model_key": model_key}

    h_img, w_img = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    yolo_model, face_cascade, profile_cascade = load_models(model_key)
    cfg = MODEL_REGISTRY.get(model_key, MODEL_REGISTRY[DEFAULT_MODEL_KEY])
    class_ids = cfg["classes"]

    person_boxes = []
    yolo_used = False
    if yolo_model is not None:
        try:
            results = yolo_model(img, classes=class_ids, conf=0.25, verbose=False)
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    person_boxes.append((x1, y1, x2 - x1, y2 - y1))
            yolo_used = True
        except Exception:
            yolo_used = False

    if not yolo_used:
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        boxes_raw, _ = hog.detectMultiScale(gray, winStride=(4, 4),
                                            padding=(8, 8), scale=1.05)
        for box in boxes_raw:
            person_boxes.append(tuple(box))

    min_face = max(20, min(h_img, w_img) // 20)
    frontal = face_cascade.detectMultiScale(gray, 1.1, 4,
                                            minSize=(min_face, min_face))
    profile = profile_cascade.detectMultiScale(gray, 1.1, 4,
                                               minSize=(min_face, min_face))
    all_faces = []
    if len(frontal):
        all_faces.extend([tuple(f) for f in frontal])
    if len(profile):
        all_faces.extend([tuple(f) for f in profile])

    extra_heads = [
        face for face in all_faces
        if not any(_box_contains(p, face) or _iou(p, face) > 0.15
                   for p in person_boxes)
    ]

    all_boxes = person_boxes + extra_heads
    heatmap = np.zeros((h_img, w_img), dtype=np.float32)
    for (x, y, w, h) in all_boxes:
        heatmap[y:min(y + h, h_img), x:min(x + w, w_img)] += 1.0
    if np.max(heatmap) > 0:
        heatmap /= np.max(heatmap)

    heat_color = cv2.applyColorMap((heatmap * 255).astype(np.uint8),
                                   cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(img, 0.6, heat_color, 0.4, 0)
    for (x, y, w, h) in person_boxes:
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
    for (x, y, w, h) in extra_heads:
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 255), 2)

    return {
        "count":       len(all_boxes),
        "body_count":  len(person_boxes),
        "head_count":  len(extra_heads),
        "overlay":     overlay,
        "model_key":   model_key,
    }


# ---------------------------------------------------------------------------
# Per-segment aggregation — supports per-image source types
# ---------------------------------------------------------------------------

def process_segment(image_bytes_list: list,
                    model_key: str | None = None,
                    per_image_sources: list | None = None) -> dict:
    """Process up to 4 images for one segment.

    `per_image_sources` is an optional list of source strings
    ("auto" | "drone" | "ground"), one per image, that overrides
    `model_key` on a per-image basis so mixed feeds work correctly.
    """
    fallback_key = model_key or get_active_model_key()
    results, total, bodies, heads = [], 0, 0, 0

    for i, b in enumerate(image_bytes_list):
        # Resolve per-image model
        if per_image_sources and i < len(per_image_sources):
            src = per_image_sources[i]
            img_model = _SOURCE_MODEL_MAP.get(src) or fallback_key
        else:
            img_model = fallback_key

        r = process_image(b, model_key=img_model)
        results.append(r)
        total  += r["count"]
        bodies += r["body_count"]
        heads  += r["head_count"]

    return {
        "count":            total,
        "body_count":       bodies,
        "head_count":       heads,
        "per_image":        results,
        "image_count":      len(image_bytes_list),
        "model_key":        fallback_key,
        "per_img_sources":  per_image_sources or [],
    }
