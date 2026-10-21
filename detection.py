"""Streamlit wrappers around the Crowd Shield core in crowdshield/."""

import streamlit as st

from crowdshield.config import DEFAULT_MODEL_KEY, MODEL_REGISTRY, SOURCE_MODEL_MAP
from crowdshield.detection import analyse_image_bytes
from crowdshield.risk import combine_counts, risk_level

__all__ = ["MODEL_REGISTRY", "get_active_model_key", "process_image",
           "process_segment", "risk_level"]


def get_active_model_key() -> str:
    return st.session_state.get("active_model", DEFAULT_MODEL_KEY)


@st.cache_data(show_spinner="🔍 Analyzing image...")
def process_image(image_bytes: bytes, model_key: str = DEFAULT_MODEL_KEY) -> dict:
    return analyse_image_bytes(image_bytes, model_key)


def process_segment(image_bytes_list: list,
                    model_key: str | None = None,
                    per_image_sources: list | None = None,
                    combine: str = "sum") -> dict:
    """Analyse up to 4 photos of one zone and merge their counts.

    `per_image_sources` ("auto" | "drone" | "ground", one per photo) picks the
    model for each photo. `combine` is "sum" when the photos show different
    parts of the zone and "max" when they show the same area, where adding
    them up would count the same people twice.
    """
    fallback_key = model_key or get_active_model_key()
    results = []
    for i, image_bytes in enumerate(image_bytes_list):
        src = (per_image_sources[i]
               if per_image_sources and i < len(per_image_sources) else None)
        results.append(process_image(image_bytes,
                                     model_key=SOURCE_MODEL_MAP.get(src) or fallback_key))

    count = combine_counts([r["count"] for r in results], combine)
    if combine == "max" and results:
        top = max(results, key=lambda r: r["count"])
        bodies, heads = top["body_count"], top["head_count"]
    else:
        bodies = sum(r["body_count"] for r in results)
        heads = sum(r["head_count"] for r in results)

    return {
        "count":            count,
        "body_count":       bodies,
        "head_count":       heads,
        "per_image":        results,
        "image_count":      len(image_bytes_list),
        "model_key":        fallback_key,
        "per_img_sources":  per_image_sources or [],
        "combine":          combine,
        "counter":          results[0].get("counter") if results else None,
    }
