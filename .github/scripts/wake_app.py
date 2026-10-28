"""Open the hosted app in a real browser and wake it if Streamlit Community Cloud put it to sleep.

Community Cloud sleeps an app after a while with no visitors, and only a browser visit (not a plain HTTP
request) counts as one. Run by .github/workflows/keep-awake.yml; exits non-zero if the app never loads.
"""

import sys
import time

from playwright.sync_api import sync_playwright

APP = "https://crowd-shield-india.streamlit.app/"
WAKE_BUTTON = "Yes, get this app back up"
READY_TEXT = "See crowd danger before it becomes a crush"  # the home page's headline
TIMEOUT_S = 300

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(APP, timeout=120_000)
    page.wait_for_timeout(8_000)
    if page.get_by_text(WAKE_BUTTON).count():
        print("The app was asleep; waking it.")
        page.get_by_text(WAKE_BUTTON).click()
    else:
        print("The app was awake.")
    start = time.time()
    while time.time() - start < TIMEOUT_S:
        app = page.frame_locator("iframe").first
        try:
            if app.get_by_text(READY_TEXT).count():
                print(f"The app is up ({time.time() - start:.0f} s).")
                break
        except Exception:
            pass  # the app's frame is not there yet
        page.wait_for_timeout(5_000)
    else:
        print(f"The app did not load within {TIMEOUT_S} s.")
        browser.close()
        sys.exit(1)
    browser.close()
