# CrowdWatch Pro Prototype

## Overview

CrowdWatch Pro is a crowd monitoring prototype application built with Streamlit and OpenCV. It provides a modern dashboard interface for analyzing crowd density and segmentation from images or video feeds. The application uses computer vision techniques (OpenCV, NumPy) to process visual data and presents results through a polished, glass-morphism styled UI.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend & Application Framework
- **Framework**: Streamlit serves as both the frontend and backend, providing a single-file Python application (`main.py`) that handles UI rendering, state management, and image processing.
- **Styling**: Custom CSS is injected via `st.markdown()` to achieve a modern dark-themed dashboard with glass-morphism card effects, gradient backgrounds, and hover animations.
- **Layout**: Uses Streamlit's wide layout mode with an expanded sidebar for controls.

### Computer Vision Pipeline
- **Custom YOLOv8 (VisDrone-trained)**: Primary detector at `models/crowd_yolo.pt`. Trained on aerial crowd imagery, 10 classes; we use class 0 (pedestrian) and class 1 (people cluster). Falls back to generic `yolov8n.pt` if missing.
- **OpenCV Haar Cascades**: Secondary face/head detection. Catches heads of people whose bodies are not fully visible.
- **Fusion logic**: Detected faces matched to person boxes via IoU/containment; only unmatched faces are added as extras (no double-counting).
- All CV logic lives in `detection.py` and is shared by every page.

### App Structure (multi-page Streamlit)
- `main.py` — Home / overview (entry point, set in `.replit`).
- `pages/1_👥_Agents.py` — Assign Gmail addresses to segments A–E.
- `pages/2_📤_Upload.py` — Upload up to 4 images per segment, run detection in one go.
- `pages/3_📊_Analysis.py` — Heatmaps, charts, alert plan, email dispatch.
- `pages/4_⚙️_Settings.py` — Adjustable risk thresholds + email config status.
- `detection.py` — Shared CV pipeline (YOLO + Haar fusion).
- `emailer.py` — Gmail SMTP helper. Reads `GMAIL_USER` and `GMAIL_APP_PASSWORD` secrets.
- `shared_state.py` — Session-state init, segment list, global CSS.
- All cross-page data (uploaded images, detection results, agent emails, thresholds) lives in `st.session_state` so it persists as users navigate.

### Email Alerts
- Sent via Gmail SMTP (`smtp.gmail.com:587`, STARTTLS) using stdlib `smtplib`.
- Requires two secrets: `GMAIL_USER` (sender Gmail address) and `GMAIL_APP_PASSWORD` (16-char Google app password). Setup instructions are shown on the Settings page.

### Data Storage
- No database is currently used. The application processes data in-memory and displays results in real-time through the Streamlit interface.

## External Dependencies

- **streamlit** — Web application framework for the dashboard UI
- **opencv-python (cv2)** — Computer vision library for image/video processing
- **numpy** — Numerical computing for array operations
- **datetime** (stdlib) — Timestamp handling for monitoring sessions

No external APIs, databases, or third-party services are currently integrated. The application runs entirely locally with in-memory processing.