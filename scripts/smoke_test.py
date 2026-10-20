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
from datetime import date, timedelta
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
    if dp_count < 80 or unlinked != 4:
        fail(f"expected at least 80 verified product pages and 4 unlinked items, found {dp_count} and {unlinked}")
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
    sheets_image = f"{BASE}/assets/img/products/sheets.webp"
    if sheets_image not in gear or 'id="sheets"' not in gear:
        fail("gear list is missing the fitted-sheet photo")
    if "Burt&#x27;s Bees Baby fitted crib sheet" not in gear:
        fail("fitted-sheet photo is missing alt text")
    thumbs = re.findall(r'<img class="item-thumb"[^>]*>', gear)
    linked = sum(1 for item in products["items"] if item.get("link") is not False)
    if len(thumbs) != linked:
        fail(f"expected {linked} product photos on the gear list, found {len(thumbs)}")
    for thumb in thumbs:
        alt = re.search(r'alt="([^"]*)"', thumb)
        src = re.search(r'src="([^"]+)"', thumb)
        if not alt or not alt.group(1).strip():
            fail("product photo missing alt text")
        if not src or "/assets/img/products/" not in src.group(1) or not src.group(1).endswith(".webp"):
            fail(f"product photo is not a local file: {thumb[:120]}")
    if 'class="item-placeholder"' in gear:
        fail("linked gear cards should use a photo, not a placeholder")
    if 'id="bumpers"' in gear:
        bumper = gear.split('id="bumpers"', 1)[1].split("</article>", 1)[0]
        if "item-thumb" in bumper or "item-placeholder" in bumper or "amazon.com" in bumper:
            fail("crib bumpers should stay unlinked and without a product image")
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
    seen_titles: dict[str, Path] = {}
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
        elif len(title) > 60:
            fail(f"{path.relative_to(ROOT)} title is {len(title)} characters: {title}")
        else:
            other = seen_titles.get(title)
            if other:
                fail(f"{path.relative_to(ROOT)} title duplicates {other.relative_to(ROOT)}: {title}")
            else:
                seen_titles[title] = path
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
        if title and (meta.get("og:title") != title or meta.get("twitter:title") != title):
            fail(f"{path.relative_to(ROOT)} social title does not match the document title")
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
                if parsed.netloc == "m.media-amazon.com" and kind == "img":
                    fail(f"{path.relative_to(ROOT)} hotlinked Amazon image {href}")
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


SHORTHAND = re.compile(r"\bW[+-]\d+\b")
NEUTRAL_PRODUCT = "This is a real product, and this list does not point to one store page."
TASK_PRODUCT = "This is a task, not a store listing."


def plain_week_label(offset: int) -> str:
    count = -offset if offset < 0 else offset
    unit = "week" if count == 1 else "weeks"
    when = "before due date" if offset < 0 else "after birth"
    return f"{count} {unit} {when}"


def due_iso_for_offset(offset: int) -> str:
    """A due date that lands in the given week window for today's local date."""
    today = date.today()
    if offset < 0:
        return (today + timedelta(days=(-offset - 1) * 7 + 3)).isoformat()
    return (today - timedelta(days=(offset - 1) * 7 + 3)).isoformat()


# Kept in step with WEEK_TITLE_TOPICS in scripts/build.py.
WEEK_TITLE_TOPICS = {
    "w-22": "Stroller Shopping Made Simple",
    "w-26": "Check Insurance for Your Pump",
    "w-5": "Stock the Freezer and Pantry",
}


def expected_document_title(week: dict) -> str:
    offset = week["offset"]
    count = -offset if offset < 0 else offset
    unit = "Week" if count == 1 else "Weeks"
    when = "Before Your Due Date" if offset < 0 else "After Birth"
    topic = WEEK_TITLE_TOPICS.get(week["id"], week["title"])
    return f"{count} {unit} {when}: {topic}"


def check_week_seo() -> None:
    weeks = json.loads((ROOT / "data" / "weeks.json").read_text(encoding="utf-8"))["weeks"]
    for week in weeks:
        path = ROOT / "timeline" / week["id"] / "index.html"
        text = path.read_text(encoding="utf-8")
        parser = Parser()
        parser.feed(text)
        title = "".join(parser.title).strip()
        expected = expected_document_title(week)
        if title != expected:
            fail(f"{week['id']} title is {title!r}")
        if len(title) > 60:
            fail(f"{week['id']} title is {len(title)} characters: {title}")
        meta = dict(parser.metas)
        description = meta.get("description", "")
        if not 120 <= len(description) <= 160:
            fail(f"{week['id']} description length {len(description)}: {description}")
        if "Buy now:" in description:
            fail(f"{week['id']} description still includes 'Buy now:'")
        if meta.get("og:title") != title or meta.get("twitter:title") != title:
            fail(f"{week['id']} social title does not match the document title")
        if meta.get("og:description") != description or meta.get("twitter:description") != description:
            fail(f"{week['id']} social description does not match the meta description")
        if not parser.jsonld:
            fail(f"{week['id']} missing JSON-LD")
            continue
        graph = json.loads(parser.jsonld[0]).get("@graph", [])
        article = next((node for node in graph if node.get("@type") == "Article"), None)
        if article is None:
            fail(f"{week['id']} missing Article JSON-LD")
            continue
        if article.get("headline") != expected:
            fail(f"{week['id']} JSON-LD headline is {article.get('headline')!r}")
        if article.get("description") != description:
            fail(f"{week['id']} JSON-LD description does not match the meta description")
        label = plain_week_label(week["offset"])
        crumb = f"{label}: {week['title']}"
        if f"<h1>{week['title']}</h1>" not in text:
            fail(f"{week['id']} changed the on-page heading")
        if f"<span>{crumb}</span>" not in text:
            fail(f"{week['id']} breadcrumb is not the plain week label")
        if week["offset"] < 0:
            eyebrow = f"{label} · roughly week {40 + week['offset']} of a 40-week pregnancy."
        else:
            eyebrow = label
        if f"<p class=\"eyebrow\">{eyebrow}</p>" not in text:
            fail(f"{week['id']} eyebrow is {eyebrow!r} missing")
        found = SHORTHAND.search(text)
        if found:
            fail(f"{week['id']} still shows shorthand {found.group(0)}")
        crumbs_ld = next((node for node in graph if node.get("@type") == "BreadcrumbList"), None)
        if crumbs_ld is None:
            fail(f"{week['id']} missing BreadcrumbList JSON-LD")
        else:
            names = [item.get("name") for item in crumbs_ld.get("itemListElement", [])]
            if names != ["Home", "Timeline", crumb]:
                fail(f"{week['id']} BreadcrumbList names are {names!r}")
        index = weeks.index(week)
        if index > 0:
            previous = plain_week_label(weeks[index - 1]["offset"])
            if f"Previous: {previous}" not in text:
                fail(f"{week['id']} previous link is not {previous!r}")
        if index < len(weeks) - 1:
            nxt = plain_week_label(weeks[index + 1]["offset"])
            if f"Next: {nxt}" not in text:
                fail(f"{week['id']} next link is not {nxt!r}")
        if '<h2 class="buy-now">Buy now</h2>' not in text:
            fail(f"{week['id']} changed the buy-now heading")
        if f"/timeline/{week['id']}/" not in text:
            fail(f"{week['id']} changed its own URL")
    for rel in ("index.html", "timeline/index.html", "gear/index.html", "llms.txt", "affiliate-disclosure/index.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        found = SHORTHAND.search(text)
        if found:
            fail(f"{rel} still shows shorthand {found.group(0)}")
    timeline = (ROOT / "timeline" / "index.html").read_text(encoding="utf-8")
    for week in weeks:
        label = plain_week_label(week["offset"])
        if f'<span class="week-code">{label}</span>' not in timeline:
            fail(f"timeline index is missing the plain label for {week['id']}")
        if f'"{label}: {week["title"]}"' not in timeline:
            fail(f"timeline ItemList is missing the plain name for {week['id']}")
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    for sample, offset in (("w-28", -28), ("w-12", -12), ("w-plus-1", 1)):
        if f'<p class="week-code">{plain_week_label(offset)}</p>' not in home:
            fail(f"home preview is missing the plain label for {sample}")
    week8 = (ROOT / "timeline" / "w-8" / "index.html").read_text(encoding="utf-8")
    gear = (ROOT / "gear" / "index.html").read_text(encoding="utf-8")
    if week8.count(TASK_PRODUCT) != 1 or gear.count(TASK_PRODUCT) != 1:
        fail("only the detector check should be described as a task")
    if week8.count(NEUTRAL_PRODUCT) != 1 or gear.count(NEUTRAL_PRODUCT) != 1:
        fail("saline drops should use neutral wording instead of a task label")
    affiliate = (ROOT / "affiliate-disclosure" / "index.html").read_text(encoding="utf-8")
    if "Saline drops are a product" not in affiliate or "are tasks rather than a single product" in affiliate:
        fail("affiliate disclosure still calls saline drops a task")
    script = (ROOT / "assets" / "js" / "timeline.js").read_text(encoding="utf-8")
    found = SHORTHAND.search(script)
    if found:
        fail(f"timeline.js still shows shorthand {found.group(0)}")


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
        base + "/": ["What do you actually need?", "Start the quiz", "28 weeks before due date", "1 week after birth"],
        quiz: ["Your Must-Have List (Middle · Nursery · Combo)", "We've hidden", "tag=bumptobaby0d-20", "sponsored nofollow noopener", "Video monitor", "4–6 bottles", 'data-form="nv7GCt"', f"{BASE}/assets/img/products/sheets.webp", "Burt's Bees Baby fitted crib sheet"],
        base + "/newsletter/": ["Weekly notes for your due date", 'data-form="nv7GCt"', "ml('account', '2715249')"],
        base + "/timeline/w-12/": [
            "12 Weeks Before Your Due Date: Buy and Install the Car Seat",
            "12 weeks before due date",
            "Buy and Install the Car Seat",
            "Buy now",
            "Car seat",
            "Previous: 13 weeks before due date",
            "Next: 11 weeks before due date",
        ],
        base + "/timeline/w-20/": [
            "20 Weeks Before Your Due Date: Halfway There",
            "20 weeks before due date",
            "Halfway There",
            "Buy now",
        ],
        base + "/timeline/w-8/": [
            "8 Weeks Before Your Due Date: Health Kit",
            "8 weeks before due date",
            "Previous: 9 weeks before due date",
            "Next: 7 weeks before due date",
            NEUTRAL_PRODUCT,
            TASK_PRODUCT,
        ],
        base + "/timeline/w-plus-1/": [
            "1 Week After Birth: Welcome Home",
            "1 week after birth",
            "Welcome Home",
            "Buy now",
            "Previous: 1 week before due date",
            "Next: 2 weeks after birth",
        ],
        base + "/timeline/?due=" + due_iso_for_offset(-8): [
            "8 weeks before due date: Health Kit",
            "Read 8 weeks before due date",
            "This is your week.",
        ],
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
    check_week_seo()
    browser_check()
    if failures:
        print(f"\n{failures} smoke check(s) failed")
        sys.exit(1)
    print("\nsmoke test passed")


if __name__ == "__main__":
    main()
