#!/usr/bin/env python3
"""Build the site, then check links, SEO, placeholders, and quiz behavior."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
ORIGIN = SITE["url"].rstrip("/")
BASE = SITE["baseurl"].rstrip("/")
HOST = "https://nicolasconnelly-bot.github.io"
EXTERNAL_OK = {
    "https://www.cpsc.gov/Recalls",
    "https://www.nhtsa.gov/vehicle-safety/car-seats-and-booster-seats",
    "https://github.com/nicolasconnelly-bot/bump-to-baby",
}
REQUIRED_PAGES = [
    "index.html",
    "quiz/index.html",
    "gear/index.html",
    "timeline/index.html",
    "newsletter/index.html",
    "privacy/index.html",
    "affiliate-disclosure/index.html",
    "disclaimer/index.html",
    "404.html",
    "robots.txt",
    "sitemap.xml",
    "llms.txt",
    ".nojekyll",
    "favicon.svg",
    "assets/og.png",
    "assets/css/style.css",
    "assets/js/quiz-engine.js",
    "assets/js/quiz-ui.js",
    "assets/js/timeline.js",
    "assets/js/site.js",
    "data/products.json",
]
failures = 0


def fail(message: str) -> None:
    global failures
    failures += 1
    print("FAIL:", message)


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = []
        self.in_title = False
        self.h1 = 0
        self.hidden_h1 = 0
        self.stack: list[str] = []
        self.ids: set[str] = set()
        self.links: list[tuple[str, str]] = []
        self.metas: list[tuple[str, str]] = []
        self.has_main = False
        self.has_skip = False
        self.has_lang = False
        self.has_viewport = False
        self.jsonld: list[str] = []
        self.in_jsonld = False
        self.jsonld_buf: list[str] = []
        self.labels: set[str] = set()
        self.inputs: list[dict] = []
        self.current_input: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        self.stack.append(tag)
        if tag == "html" and attr.get("lang", "").lower().startswith("en"):
            self.has_lang = True
        if tag == "title":
            self.in_title = True
        if tag == "main" and attr.get("id") == "content":
            self.has_main = True
        if tag == "h1":
            if self._hidden():
                self.hidden_h1 += 1
            else:
                self.h1 += 1
        if attr.get("id"):
            if attr["id"] in self.ids:
                fail(f"duplicate id #{attr['id']}")
            self.ids.add(attr["id"])
        if tag == "a":
            href = attr.get("href", "")
            if href == "#content":
                self.has_skip = True
            self.links.append(("a", href, attr.get("rel", ""), attr.get("target", "")))
        if tag in {"img", "script", "link"} and (attr.get("src") or attr.get("href")):
            ref = attr.get("src") or attr.get("href") or ""
            rel = attr.get("rel", "")
            if tag != "a":
                self.links.append((tag, ref if tag != "link" or rel in {"stylesheet", "icon", "canonical"} or ref.endswith(".svg") or ref.endswith(".png") or ref.endswith(".css") else ""))
            if tag == "link" and rel == "canonical":
                self.links.append(("canonical", attr.get("href", "")))
        if tag == "meta":
            key = attr.get("name") or attr.get("property") or ""
            self.metas.append((key, attr.get("content", "")))
            if key == "viewport":
                self.has_viewport = True
        if tag == "script" and attr.get("type") == "application/ld+json":
            self.in_jsonld = True
            self.jsonld_buf = []
        if tag == "label" and attr.get("for"):
            self.labels.add(attr["for"])
        if tag == "input":
            self.inputs.append(attr)
        if tag == "img" and not attr.get("alt") and attr.get("alt") != "":
            fail("image missing alt")

    def _hidden(self) -> bool:
        return False

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_jsonld:
            self.jsonld.append("".join(self.jsonld_buf))
            self.in_jsonld = False
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        if self.in_jsonld:
            self.jsonld_buf.append(data)


def run_build() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        fail("build failed\n" + result.stdout + result.stderr)
    else:
        print(result.stdout.strip())


def run_logic() -> None:
    result = subprocess.run(["node", str(ROOT / "scripts" / "logic.test.js")], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        fail("logic tests failed\n" + result.stdout + result.stderr)
    else:
        print(result.stdout.strip())


def local_file(url: str) -> Path | None:
    clean = url.split("#", 1)[0].split("?", 1)[0]
    if clean.startswith(ORIGIN):
        clean = clean[len(HOST):]
    if clean.startswith(BASE):
        rel = unquote(clean[len(BASE):])
    elif clean.startswith("/"):
        return None
    else:
        return None
    if rel in {"", "/"}:
        rel = "/index.html"
    elif rel.endswith("/"):
        rel = rel + "index.html"
    return ROOT / rel.lstrip("/")


def check_files() -> None:
    for rel in REQUIRED_PAGES:
        if not (ROOT / rel).exists():
            fail("missing " + rel)
    products_text = (ROOT / "data" / "products.json").read_text(encoding="utf-8")
    if "{{AFFILIATE_LINK}}" in products_text:
        fail("products.json still contains {{AFFILIATE_LINK}}")
    products = json.loads(products_text)
    tag = "tag=bumptobaby0d-20"
    dp_count = search_count = unlinked = 0
    for item in products["items"]:
        link = item.get("link")
        if link is False:
            unlinked += 1
            continue
        if not isinstance(link, str) or tag not in link or not link.startswith("https://www.amazon.com/"):
            fail(f"{item['id']} is missing an Amazon affiliate link")
            continue
        if "/dp/" in link:
            dp_count += 1
        elif link.startswith("https://www.amazon.com/s?k="):
            search_count += 1
        else:
            fail(f"{item['id']} link is neither a product page nor a search")
    print(f"affiliate links: {dp_count} verified /dp/, {search_count} search, {unlinked} unlinked")
    if dp_count < 1 or search_count < 1:
        fail("expected both verified product pages and search links")
    weeks = json.loads((ROOT / "data" / "weeks.json").read_text(encoding="utf-8"))["weeks"]
    if len(weeks) != 32:
        fail("weeks.json does not have 32 weeks")
    for week in weeks:
        page = ROOT / "timeline" / week["id"] / "index.html"
        if not page.exists():
            fail("missing week page " + week["id"])
    if not (ROOT / ".nojekyll").exists():
        fail("missing .nojekyll")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {ORIGIN}/sitemap.xml" not in robots:
        fail("robots.txt sitemap URL")
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    for week in weeks:
        loc = f"{ORIGIN}/timeline/{week['id']}/"
        if loc not in sitemap:
            fail("sitemap missing " + loc)
        if loc not in llms:
            fail("llms.txt missing " + loc)
    disclosure = "As an Amazon Associate I earn from qualifying purchases."
    gear = (ROOT / "gear" / "index.html").read_text(encoding="utf-8")
    if gear.count("tag=bumptobaby0d-20") < 40:
        fail("gear page should show Amazon affiliate links on commercial items")
    if 'rel="sponsored nofollow noopener"' not in gear or 'target="_blank"' not in gear:
        fail("gear affiliate links need rel and target")
    if disclosure not in gear:
        fail("footer missing the Amazon Associates disclosure")
    affiliate = (ROOT / "affiliate-disclosure" / "index.html").read_text(encoding="utf-8")
    if disclosure not in affiliate:
        fail("affiliate disclosure page missing the Amazon Associates sentence")
    embed = '<div class="ml-embedded" data-form="nv7GCt"></div>'
    script = "https://assets.mailerlite.com/js/universal.js"
    account = "ml('account', '2715249');"
    form_pages = [
        "index.html",
        "quiz/index.html",
        "gear/index.html",
        "timeline/index.html",
        "newsletter/index.html",
    ]
    form_pages.extend(f"timeline/{week['id']}/index.html" for week in weeks)
    for rel in form_pages:
        text = (ROOT / rel).read_text(encoding="utf-8")
        head = text.split("</head>", 1)[0]
        if embed not in text:
            fail(rel + " is missing the MailerLite embed")
        if script not in head or account not in head:
            fail(rel + " is missing the MailerLite universal script in the head")
        if "data-newsletter-placeholder" in text or "newsletter-form" in text:
            fail(rel + " still has the placeholder newsletter form")
    for rel in ("privacy/index.html", "affiliate-disclosure/index.html", "disclaimer/index.html", "404.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "ml-embedded" in text or "data-newsletter-placeholder" in text:
            fail(rel + " should not include the newsletter form")
    disclaimer = (ROOT / "disclaimer" / "index.html").read_text(encoding="utf-8")
    for phrase in ("not medical", "does not give doses", "certified"):
        if phrase not in disclaimer.lower() and phrase not in disclaimer:
            fail("disclaimer missing: " + phrase)
    if "ask your pediatrician" not in disclaimer.lower():
        fail("disclaimer should tell parents to ask a pediatrician")


def check_html() -> None:
    pages = [ROOT / "index.html", ROOT / "404.html"]
    pages.extend(
        path for path in ROOT.rglob("*.html")
        if "scripts" not in path.parts and path not in pages
    )
    seen = set()
    for path in pages:
        if path in seen:
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8")
        tokens = set(re.findall(r"\{\{[^}]+\}\}", text))
        if tokens:
            fail(f"{path.relative_to(ROOT)} has unexpected placeholders {tokens}")
        if re.search(r"\$\s?\d", text):
            fail(f"{path.relative_to(ROOT)} contains a price")
        copy = re.sub(r'href="[^"]*"', "", text)
        for percent in re.findall(r"\d+\s*[–-]\s*\d+\s*%|\d+\s*%", copy):
            compact = percent.replace(" ", "")
            if compact not in {"10–15%", "10-15%"}:
                fail(f"{path.relative_to(ROOT)} has unexpected percent {percent}")
        if re.search(r"\b(lorem ipsum|TODO|FIXME)\b", text, re.I):
            fail(f"{path.relative_to(ROOT)} has unfinished copy")
        parser = Parser()
        parser.feed(text)
        title = "".join(parser.title).strip()
        if not title:
            fail(f"{path} missing title")
        elif len(title) > 80:
            fail(f"{path} title is {len(title)} characters: {title}")
        description = dict(parser.metas).get("description", "")
        if path.name != "404.html" and not (50 <= len(description) <= 170):
            fail(f"{path.relative_to(ROOT)} description length {len(description)}: {description}")
        if parser.h1 != 1:
            fail(f"{path.relative_to(ROOT)} has {parser.h1} h1 elements")
        if not parser.has_main or not parser.has_lang or not parser.has_viewport or not parser.has_skip:
            fail(f"{path.relative_to(ROOT)} missing main, lang, viewport, or skip link")
        meta = dict(parser.metas)
        for key in ("og:title", "og:description", "og:url", "og:image"):
            if not meta.get(key):
                fail(f"{path.relative_to(ROOT)} missing {key}")
        if not parser.jsonld and path.name != "404.html":
            fail(f"{path.relative_to(ROOT)} missing JSON-LD")
        for block in parser.jsonld:
            try:
                json.loads(block)
            except json.JSONDecodeError as error:
                fail(f"{path.relative_to(ROOT)} JSON-LD: {error}")
        if path == ROOT / "index.html" and "FAQPage" not in text:
            fail("home page missing FAQPage schema")
        for attr in parser.inputs:
            if attr.get("type") in {"hidden", "radio", "checkbox", "submit"}:
                continue
            input_id = attr.get("id", "")
            if input_id not in parser.labels and not attr.get("aria-label"):
                fail(f"{path.relative_to(ROOT)} input {input_id or attr.get('type')} has no label")
        for entry in parser.links:
            kind, href = entry[0], entry[1]
            rel = entry[2] if len(entry) > 2 else ""
            target = entry[3] if len(entry) > 3 else ""
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("data:"):
                if href.startswith("#") and href != "#content":
                    anchor = href[1:]
                    if anchor and anchor not in parser.ids and kind == "a":
                        fail(f"{path.relative_to(ROOT)} missing anchor {href}")
                continue
            if "{{" in href:
                fail(f"{path.relative_to(ROOT)} uses a placeholder as a live href")
                continue
            parsed = urlparse(href)
            if parsed.scheme in {"http", "https"} and not href.startswith(ORIGIN) and not href.startswith(HOST + BASE):
                bare = href.split("#", 1)[0]
                if parsed.netloc == "www.amazon.com":
                    if "tag=bumptobaby0d-20" not in href:
                        fail(f"{path.relative_to(ROOT)} Amazon link missing the Associates tag: {href}")
                    if kind == "a" and (rel != "sponsored nofollow noopener" or target != "_blank"):
                        fail(f"{path.relative_to(ROOT)} Amazon link missing rel or target: {href}")
                    continue
                if bare not in EXTERNAL_OK and not bare.startswith(ORIGIN):
                    fail(f"{path.relative_to(ROOT)} unexpected external link {href}")
                continue
            target = local_file(href)
            if target is None or not target.is_file():
                fail(f"{path.relative_to(ROOT)} broken link {href}")
            elif "#" in href:
                anchor = href.split("#", 1)[1]
                target_text = target.read_text(encoding="utf-8")
                if f'id="{anchor}"' not in target_text:
                    fail(f"{path.relative_to(ROOT)} broken anchor {href}")


def browser_check() -> None:
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if not chrome:
        fail("chrome is not available for the browser smoke test")
        return
    parent = Path(tempfile.mkdtemp(prefix="btb-serve-"))
    link = parent / "bump-to-baby"
    link.symlink_to(ROOT)
    import http.server

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(parent), **kwargs)

        def log_message(self, format: str, *args) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}/bump-to-baby"
    quiz = base + "/quiz/?tier=mid&space=nursery&feed=combo&season=fall&move=mix&first=yes&care=home&laundry=normal"
    checks = {
        base + "/": ["What do you actually need?", "Start the quiz"],
        quiz: ["Your Must-Have List (Middle · Nursery · Combo)", "We've hidden", "tag=bumptobaby0d-20", "sponsored nofollow noopener", "Video monitor", "4–6 bottles", 'data-form="nv7GCt"'],
        base + "/newsletter/": ["Weekly notes for your due date", 'data-form="nv7GCt"', "ml('account', '2715249')"],
        base + "/timeline/w-12/": ["Buy and Install the Car Seat", "Buy now", "Car seat"],
    }
    profiles: list[Path] = []
    try:
        for url, needles in checks.items():
            profile = Path(tempfile.mkdtemp(prefix="btb-chrome-"))
            profiles.append(profile)
            command = [
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
                f"--user-data-dir={profile}", "--virtual-time-budget=12000", "--dump-dom", url,
            ]
            try:
                result = subprocess.run(command, text=True, capture_output=True, timeout=25)
                dom = result.stdout
                code = result.returncode
                err = result.stderr
            except subprocess.TimeoutExpired as exc:
                # This environment's Chrome prints the DOM, then does not exit.
                dom = exc.stdout or ""
                if isinstance(dom, bytes):
                    dom = dom.decode("utf-8", "replace")
                code = 0 if "<html" in dom.lower() else 1
                err = exc.stderr or ""
                if isinstance(err, bytes):
                    err = err.decode("utf-8", "replace")
            if code != 0 or "<html" not in dom.lower():
                fail(f"chrome failed for {url}\n{err[:500]}")
                continue
            for needle in needles:
                if needle not in dom:
                    fail(f"{url} did not contain {needle!r}")
            if url == quiz and "Left off because you are planning to use formula" in dom:
                fail("combo result incorrectly removed breastfeeding items")
    finally:
        server.shutdown()
        shutil.rmtree(parent, ignore_errors=True)
        for profile in profiles:
            shutil.rmtree(profile, ignore_errors=True)


def main() -> None:
    run_build()
    run_logic()
    check_files()
    check_html()
    browser_check()
    if failures:
        print(f"\n{failures} smoke check(s) failed")
        sys.exit(1)
    print("\nsmoke test passed")


if __name__ == "__main__":
    main()
