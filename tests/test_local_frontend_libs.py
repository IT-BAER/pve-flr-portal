"""The pages load their JavaScript from /static, never from a CDN.

A script from a third-party host runs with the page's full access, and
the login page is where users type their PVE password, so a compromised
or hijacked CDN could read it. htmx and Alpine are served from
backend/static/vendor/ instead. The same goes for fonts and styles: no
page or stylesheet makes the browser contact another host.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted((ROOT / "backend" / "templates").rglob("*.html"))
EXTERNAL_SCRIPT = re.compile(r"<script[^>]*\ssrc=[\"']?(https?:)?//", re.IGNORECASE)
EXTERNAL_LINK = re.compile(r"<link[^>]*\shref=[\"']?(https?:)?//", re.IGNORECASE)
EXTERNAL_CSS_URL = re.compile(r"(url\(\s*[\"']?|@import\s+[\"']?)(https?:)?//", re.IGNORECASE)


def test_no_page_loads_a_script_from_another_host():
    offenders = [
        f"{page.relative_to(ROOT)}: {match.group(0)}"
        for page in PAGES
        for match in EXTERNAL_SCRIPT.finditer(page.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_no_page_or_stylesheet_loads_from_another_host():
    offenders = [
        f"{page.relative_to(ROOT)}: {match.group(0)}"
        for page in PAGES
        for match in EXTERNAL_LINK.finditer(page.read_text(encoding="utf-8"))
    ]
    offenders += [
        f"{css.relative_to(ROOT)}: {match.group(0)}"
        for css in sorted((ROOT / "backend" / "static").rglob("*.css"))
        for match in EXTERNAL_CSS_URL.finditer(css.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_bundled_fonts_are_present_and_licensed():
    fonts = ROOT / "backend" / "static" / "fonts"
    for weight in (400, 600, 700):
        assert (fonts / f"open-sans-latin-{weight}-normal.woff2").stat().st_size > 0, weight
    assert "SIL Open Font License" in (fonts / "OFL.txt").read_text(encoding="utf-8")


def test_vendored_libraries_are_present_and_licensed():
    vendor = ROOT / "backend" / "static" / "vendor"
    for name in ("htmx.min.js", "alpine.min.js", "htmx.LICENSE", "alpine.LICENSE.md"):
        assert (vendor / name).stat().st_size > 0, name
