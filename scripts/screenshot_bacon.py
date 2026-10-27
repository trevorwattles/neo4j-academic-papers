"""Screenshot the Bacon path to Nora Ephron in the real Neo4j Browser (headless Chromium)."""
import re
import sys

from playwright.sync_api import sync_playwright

from db import PASSWORD, ROOT, USER

QUERY = '''MATCH p = shortestPath(
  (bacon:Person {name: "Kevin Bacon"})-[*]-(nora:Person {name: "Nora Ephron"})
)
RETURN p'''
debug_dir = sys.argv[1] if len(sys.argv) > 1 else None

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
    page.goto("http://localhost:7474/browser/", wait_until="networkidle")

    # Log in using the credentials from .env
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASSWORD)
    page.click('[data-testid="connection-form-submit"]')
    page.wait_for_timeout(4000)
    if debug_dir:
        page.screenshot(path=f"{debug_dir}/after_login.png")

    # Type the query into the Cypher editor (CodeMirror) and run it
    editor = page.locator(".cm-content").first
    editor.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(QUERY)
    page.keyboard.press("Escape")  # close the autocomplete dropdown
    page.click('[data-testid="run-button"]')
    page.wait_for_timeout(6000)  # let the force-directed layout settle

    # Dismiss the "Work in tabs" onboarding tour if it is showing
    for _ in range(5):
        buttons = page.get_by_role("button", name=re.compile(r"^(Next|Done|Skip|Got it|Close|Finish)", re.I))
        if buttons.count() == 0:
            break
        buttons.first.click()
        page.wait_for_timeout(500)
    page.keyboard.press("Escape")
    page.mouse.click(1000, 30)
    page.wait_for_timeout(1000)

    # Crop to the result frame (query bar + graph + results overview)
    out = ROOT / "bacon_path_nora_ephron.png"
    page.screenshot(path=str(out), clip={"x": 410, "y": 180, "width": 980, "height": 650})
    print("saved", out)
    browser.close()
