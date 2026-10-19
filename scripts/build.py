#!/usr/bin/env python3
"""Generate the static Bump to Baby site from data/*.json."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
PRODUCTS = json.loads((DATA / "products.json").read_text(encoding="utf-8"))
QUIZ = json.loads((DATA / "quiz.json").read_text(encoding="utf-8"))
WEEKS = json.loads((DATA / "weeks.json").read_text(encoding="utf-8"))["weeks"]
FAQ = json.loads((DATA / "faq.json").read_text(encoding="utf-8"))["questions"]

BASE = SITE["baseurl"].rstrip("/")
ORIGIN = SITE["url"].rstrip("/")
NAME = SITE["name"]
PUBLISHED = SITE["published"]
OG_IMAGE = f"{ORIGIN}/assets/og.png"
PLACEHOLDER = PRODUCTS["affiliatePlaceholder"]

WEEK_GROUPS = [
    ("Before you buy much", ["w-28", "w-27", "w-26", "w-25", "w-24", "w-23", "w-22", "w-21", "w-20"]),
    ("Set up the room", ["w-19", "w-18", "w-17", "w-16", "w-15", "w-14"]),
    ("Shopping weeks", ["w-13", "w-12", "w-11", "w-10", "w-9", "w-8", "w-7", "w-6"]),
    ("Almost here", ["w-5", "w-4", "w-3", "w-2", "w-1"]),
    ("The first month", ["w-plus-1", "w-plus-2", "w-plus-3", "w-plus-4"]),
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def site_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return BASE + path


def canonical(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if path == "/":
        return ORIGIN + "/"
    return ORIGIN + path


def jsonld(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    return raw.replace("<", "\\u003c")


def week_plain_label(offset: int) -> str:
    """Visible week phrase, such as '8 weeks before due date' or '1 week after birth'."""
    if offset < 0:
        count = -offset
        when = "before due date"
    elif offset > 0:
        count = offset
        when = "after birth"
    else:
        raise ValueError(f"week offset must be non-zero, got {offset}")
    unit = "week" if count == 1 else "weeks"
    return f"{count} {unit} {when}"


def week_eyebrow(offset: int) -> str:
    """Plain week label, plus the pregnancy week when the baby has not arrived."""
    label = week_plain_label(offset)
    if offset < 0:
        return f"{label} · roughly week {40 + offset} of a 40-week pregnancy."
    return label


def week_search_label(offset: int) -> str:
    """Plain week phrase for titles and snippets, such as '20 Weeks Before Your Due Date'."""
    if offset < 0:
        count = -offset
        when = "Before Your Due Date"
    elif offset > 0:
        count = offset
        when = "After Birth"
    else:
        raise ValueError(f"week offset must be non-zero, got {offset}")
    unit = "Week" if count == 1 else "Weeks"
    return f"{count} {unit} {when}"


# Search snippets for each week page. On-page copy stays in data/weeks.json.
WEEK_DESCRIPTIONS = {
    "w-28": "Six months out, skip the shopping. Take the registry quiz, start a shared baby list, and let suggested gear wait until you know what you actually need.",
    "w-27": "Agree on a total baby budget, a cap for big gear, and what you hope gifts will cover. Decide your secondhand rules now so the later shopping weeks stay calm.",
    "w-26": "Call your insurer and ask which breast pumps are covered, when you can order, and if upgrades cost extra. Buy the pump only after you have that answer.",
    "w-25": "Choose a pediatrician now. Ask about the after-hours line, same-day sick visits, and how far the office is, then save the number where you will actually see it.",
    "w-24": "Turn your quiz results into a short registry: must-haves first, then a few nice-to-haves at different prices. This week is for registering, not for buying.",
    "w-23": "Compare an infant car seat with a convertible one and check that it fits your car. Hospitals expect a rear-facing seat for the ride home; buying can wait a bit.",
    "w-22": "Judge strollers by trunk fit, a one-hand fold, and car-seat compatibility. Push a few in a store this weekend, and leave the purchase for a later week.",
    "w-21": "Measure the sleep space and sketch the crib, dresser, and chair away from windows and cords. Paint now if you need to, and leave the furniture order for later.",
    "w-20": "Halfway there: review budget, insurance, pediatrician, registry, car seat, and stroller. If half of that is underway, you are on track and can skip shopping.",
    "w-19": "Order a fixed-side crib and a firm, tight-fitting mattress now so delivery and assembly finish before the last weeks. Sheets and nursery decor can wait.",
    "w-18": "Get a dresser with a changing topper instead of a changing table, and anchor it to the wall. Keep diapers, wipes, and cream within arm's reach of the pad.",
    "w-17": "Book childbirth, breastfeeding, infant CPR, and newborn classes before they fill, and bring a partner along. Wait to buy feeding gear until after class.",
    "w-16": "Wait on most baby clothes until after the shower. Buy only a few 0–3 month zip-up sleepers for now, and leave newborn sizes for gifts.",
    "w-15": "Set up safe sleep: a firm flat mattress in a crib or bassinet, with nothing else in it. Add swaddles and white noise this week, and let the monitor wait.",
    "w-14": "Send the registry, thank people as gifts arrive, and keep receipts for easy exchanges. Shop the gaps only after the shower, not before.",
    "w-13": "Check shower gifts against your quiz list, return duplicates and skip items, and use a completion discount on leftover must-haves. Nice-to-haves can wait.",
    "w-12": "Buy the car seat, install it, and get a certified or free fire-station check, then register the seat for recalls. Mirrors and seat organizers can wait.",
    "w-11": "Gather a small feeding kit: pump supplies, one can of formula, or a few bottles, plus a brush and drying rack. Sterilizers and formula makers can wait.",
    "w-10": "Buy a small newborn diaper pack, a box of size 1, wipes, and cream, and keep the receipts. Skip a huge newborn stash; that size goes fast.",
    "w-9": "Get an infant tub, gentle wash, hooded towels, washcloths, and nail clippers. A few baths a week is enough for a newborn, so bath toys can wait.",
    "w-8": "Build a small night kit: thermometer, nasal aspirator, and saline, and save the pediatrician's after-hours number. Ask before using infant medicine.",
    "w-7": "Wash clothes, sheets, swaddles, and burp cloths in fragrance-free detergent, then dress the bassinet and crib. Fold by size so the next size is easy to find.",
    "w-6": "Pack bags for the baby and both adults: going-home clothes, toiletries, chargers, and snacks. Set the bag by the door and put the car seat base in the car.",
    "w-5": "Freeze easy meals, stock one-handed snacks, and order staples like soap and toilet paper. A full freezer will help more than another piece of baby gear.",
    "w-4": "Set up a night feeding spot and each changing station with water, a burp cloth, and a dim light. A new glider can wait if you already have a comfortable chair.",
    "w-3": "Check the car seat, hospital bag, driving route, pediatrician, and care for pets or older kids, then rest. Nothing new needs buying this week.",
    "w-2": "Rest, walk, and charge your phone. Anything still missing can be delivered after the baby arrives, so skip one last round of just-in-case shopping.",
    "w-1": "Due week stays short: gas in the car, bag packed, phone charged, car seat ready, and a plan for when to call. There is nothing new to buy.",
    "w-plus-1": "Week one at home is feeds, diapers, and sleep. Track diapers for the pediatrician, accept meal help, and reorder only what you are actually running out of.",
    "w-plus-2": "If feeding is hard, book a lactation visit, try another bottle nipple, or buy more of a formula that works. Skip new gadgets until one of those actually helps.",
    "w-plus-3": "Red marks from snaps or diapers mean it is time for size 1 and 0–3 month clothes. Pack away the outgrown pieces, and add a carrier if walks would help.",
    "w-plus-4": "At one month, add a play mat and high-contrast books, and plan a sleep sack for when rolling starts. High chairs, gates, and activity centers can still wait.",
}


def meta_description(week: dict) -> str:
    text = WEEK_DESCRIPTIONS.get(week["id"])
    if not text:
        raise SystemExit(f"{week['id']} is missing a search description")
    text = re.sub(r"\s+", " ", text).strip()
    if "Buy now:" in text:
        raise SystemExit(f"{week['id']} search description still includes 'Buy now:'")
    if not 120 <= len(text) <= 160:
        raise SystemExit(f"{week['id']} search description is {len(text)} characters")
    return text


def item_map() -> dict:
    return {item["id"]: item for item in PRODUCTS["items"]}


def link_token(item: dict) -> str | None:
    if item.get("link") is False:
        return None
    if isinstance(item.get("link"), str) and item["link"]:
        return item["link"]
    return PLACEHOLDER


def thumb_html(item: dict) -> str:
    image = item.get("image")
    if isinstance(image, str) and image:
        src = site_path(image) if image.startswith("/") else image
        alt = item.get("imageAlt") or item["name"]
        return (
            f'<img class="item-thumb" src="{esc(src)}" alt="{esc(alt)}" width="72" height="72" loading="lazy">'
        )
    link = item.get("link")
    if item.get("unsafe") or not isinstance(link, str) or not link:
        return ""
    return (
        f'<span class="item-placeholder" data-category="{esc(item["category"])}" aria-hidden="true"></span>'
    )


def affiliate_html(item: dict) -> str:
    token = link_token(item)
    if token is None:
        if item.get("unsafe"):
            return '<p class="affiliate">No product link. This item is unsafe for sleep, so it is not for sale here.</p>'
        if item.get("task"):
            return '<p class="affiliate">No product link. This is a task, not a store listing.</p>'
        return (
            '<p class="affiliate">No product link. This is a real product, '
            "and this list does not point to one store page.</p>"
        )
    if token.startswith("http://") or token.startswith("https://"):
        return (
            f'<p class="affiliate"><a href="{esc(token)}" rel="sponsored nofollow noopener" '
            f'target="_blank">Product link for {esc(item["name"])}</a></p>'
        )
    return f'<p class="affiliate">Link placeholder: <code translate="no">{esc(token)}</code></p>'


def badge_for(item: dict) -> tuple[str, str]:
    if item.get("unsafe"):
        return "Skip — unsafe", "badge-unsafe"
    return {
        "must": ("Must-have", "badge-must"),
        "nice": ("Nice-to-have", "badge-nice"),
        "wait": ("Wait", "badge-wait"),
        "skip": ("Skip", "badge-skip"),
        "exclude": ("Depends on your answers", "badge-exclude"),
    }[item["status"]]


def quantity_html(item: dict) -> str:
    parts = []
    for part in item.get("quantities") or []:
        if part["low"] == part["high"]:
            parts.append(f'{part["low"]} {part["item"]}')
        else:
            parts.append(f'{part["low"]}–{part["high"]} {part["item"]}')
    if not parts:
        return ""
    return f'<p class="plan-line">{esc(", ".join(parts))}</p>'


def picks_html(item: dict) -> str:
    labels = (("budget", "Budget"), ("mid", "Middle"), ("premium", "Premium"))
    rows = []
    picks = item.get("picks") or {}
    for key, label in labels:
        if picks.get(key):
            rows.append(f"<div><dt>{label}</dt><dd>{esc(picks[key])}</dd></div>")
    if not rows:
        return ""
    return f'<dl class="picks">{"".join(rows)}</dl>'


LOGO = """<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#23483d"/><path d="M16 25V14" stroke="#f6ddd0" stroke-width="2" stroke-linecap="round"/><path d="M16 16c2-3 5-3 6-6-3 0-5 2-6 6z" fill="#f4efe6"/><path d="M16 18c-2-2.5-5-2.8-6.5-5.5 3.2.2 5.2 2 6.5 5.5z" fill="#e7b199"/></svg>"""


def nav(current: str) -> str:
    links = [
        ("/quiz/", "Quiz"),
        ("/timeline/", "Timeline"),
        ("/gear/", "Gear list"),
        ("/newsletter/", "Newsletter"),
    ]
    items = []
    for path, label in links:
        current_attr = ' aria-current="page"' if path == current else ""
        items.append(f'<a href="{site_path(path)}"{current_attr}>{label}</a>')
    return f"""
<a class="skip-link" href="#content">Skip to content</a>
<header class="site-header">
  <div class="header-bar">
    <a class="logo" href="{site_path("/")}">{LOGO}<span>{esc(NAME)}</span></a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
  </div>
  <nav id="site-nav" aria-label="Primary">{"".join(items)}</nav>
</header>"""


def footer() -> str:
    return f"""
<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <h2>About this site</h2>
      <p class="fine-print">Bump to Baby is a free planning guide for expecting parents. It runs as a static site: the quiz stays in your browser, and the week-by-week notes are ordinary web pages.</p>
      <p class="fine-print">General information only. Safe-sleep, car-seat, and medicine notes are not personal medical advice. <a href="{site_path("/disclaimer/")}">Read the disclaimer</a>.</p>
      <p class="fine-print">As an Amazon Associate I earn from qualifying purchases.</p>
    </div>
    <div>
      <h2>Explore</h2>
      <ul>
        <li><a href="{site_path("/quiz/")}">Registry quiz</a></li>
        <li><a href="{site_path("/timeline/")}">Week-by-week timeline</a></li>
        <li><a href="{site_path("/gear/")}">Master gear list</a></li>
        <li><a href="{site_path("/newsletter/")}">Newsletter</a></li>
      </ul>
    </div>
    <div>
      <h2>Good to know</h2>
      <ul>
        <li><a href="{site_path("/disclaimer/")}">Medical and safety disclaimer</a></li>
        <li><a href="{site_path("/privacy/")}">Privacy</a></li>
        <li><a href="{site_path("/affiliate-disclosure/")}">Affiliate disclosure</a></li>
        <li><a href="{site_path("/llms.txt")}">Machine-readable guide</a></li>
      </ul>
    </div>
  </div>
</footer>"""


MAILERLITE_HEAD = """
  <!-- MailerLite Universal -->
  <script>
    (function(w,d,e,u,f,l,n){w[f]=w[f]||function(){(w[f].q=w[f].q||[])
    .push(arguments);},l=d.createElement(e),l.async=1,l.src=u,
    n=d.getElementsByTagName(e)[0],n.parentNode.insertBefore(l,n);})
    (window,document,'script','https://assets.mailerlite.com/js/universal.js','ml');
    ml('account', '2715249');
  </script>
  <!-- End MailerLite Universal -->"""


def newsletter(compact: bool = False) -> str:
    if compact:
        copy = """<h2 id="newsletter-heading">Want the weekly version?</h2>
        <p>One note a week with what to buy now, keyed to your due date. Add your email and due date below.</p>"""
    else:
        copy = """<p class="eyebrow">Newsletter</p>
        <h2 id="newsletter-heading">One week at a time, by email</h2>
        <p>Each week you get the buy-now note for where you are, from 28 weeks before your due date through the first month home. The form asks for your email and due date so those notes can follow that date.</p>"""
    return f"""
<section class="newsletter" id="newsletter" aria-labelledby="newsletter-heading">
  <div class="newsletter-copy">{copy}</div>
  <div class="ml-embedded" data-form="nv7GCt"></div>
</section>"""


def crumbs(parts: list[tuple[str, str]]) -> str:
    bits = [f'<a href="{site_path("/")}">Home</a>']
    for path, label in parts[:-1]:
        bits.append(f'<a href="{site_path(path)}">{esc(label)}</a>')
    bits.append(f"<span>{esc(parts[-1][1])}</span>")
    return '<nav class="breadcrumb" aria-label="Breadcrumb">' + " / ".join(bits) + "</nav>"


def page(title: str, description: str, path: str, body: str, structured: dict | None = None,
         og_type: str = "website", robots: str | None = None, scripts: list[str] | None = None,
         current: str = "", brand_sep: str = " · ") -> str:
    full_title = title if title == NAME or title.startswith(NAME) else f"{title}{brand_sep}{NAME}"
    robots_tag = f'\n  <meta name="robots" content="{esc(robots)}">' if robots else ""
    ld = ""
    if structured:
        ld = f'\n  <script type="application/ld+json">\n{jsonld(structured)}\n  </script>'
    script_tags = []
    for src in scripts or ["/assets/js/site.js"]:
        script_tags.append(f'  <script src="{site_path(src)}" defer></script>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="btb-base" content="{esc(BASE)}">
  <meta name="theme-color" content="{esc(SITE["themeColor"])}">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical(path))}">{robots_tag}
  <meta property="og:type" content="{esc(og_type)}">
  <meta property="og:site_name" content="{esc(NAME)}">
  <meta property="og:locale" content="{esc(SITE["locale"])}">
  <meta property="og:title" content="{esc(full_title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical(path))}">
  <meta property="og:image" content="{esc(OG_IMAGE)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(full_title)}">
  <meta name="twitter:description" content="{esc(description)}">
  <meta name="twitter:image" content="{esc(OG_IMAGE)}">
  <link rel="icon" href="{site_path("/favicon.svg")}" type="image/svg+xml">
  <link rel="alternate" type="text/plain" title="llms.txt" href="{site_path("/llms.txt")}">
  <link rel="stylesheet" href="{site_path("/assets/css/style.css")}">
  <script>document.documentElement.classList.add("js")</script>{ld}{MAILERLITE_HEAD if 'class="ml-embedded"' in body else ""}
</head>
<body>
{nav(current)}
<main id="content" class="wrap">
{body}
</main>
{footer()}
{chr(10).join(script_tags)}
</body>
</html>
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


def website_node() -> dict:
    return {
        "@type": "WebSite",
        "@id": canonical("/") + "#website",
        "name": NAME,
        "url": canonical("/"),
        "description": SITE["description"],
        "inLanguage": "en",
    }


def breadcrumb_ld(parts: list[tuple[str, str]]) -> dict:
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": canonical("/")}]
    for index, (path, label) in enumerate(parts, start=2):
        items.append({
            "@type": "ListItem",
            "position": index,
            "name": label,
            "item": canonical(path),
        })
    return {"@type": "BreadcrumbList", "itemListElement": items}


def home_page() -> None:
    by_id = item_map()
    samples = ["car-seat", "mattress", "diapers", "thermometer"]
    sample_items = "".join(f"<li>{esc(by_id[item_id]['name'])}</li>" for item_id in samples)
    preview = []
    for week_id in ("w-28", "w-12", "w-plus-1"):
        week = next(week for week in WEEKS if week["id"] == week_id)
        preview.append(
            f'<a class="week-link" href="{site_path("/timeline/" + week["id"] + "/")}">'
            f'<p class="week-code">{esc(week_plain_label(week["offset"]))}</p>'
            f"<h3>{esc(week['title'])}</h3>"
            f'<p class="week-buy">Buy now: {esc(week["buyNow"])}</p></a>'
        )
    faqs = []
    for entry in FAQ:
        faqs.append(
            f'<article class="faq-item"><h3>{esc(entry["question"])}</h3>'
            f"<p>{esc(entry['answer'])}</p></article>"
        )
    body = f"""
<section class="hero">
  <div>
    <p class="eyebrow">For expecting parents</p>
    <h1>What do you actually need?</h1>
    <p class="lede">Eight questions build a must-have list for your home, your feeding plan, and your season. Thirty-two weekly pages tell you what to buy now and what can wait.</p>
    <div class="actions">
      <a class="button" href="{site_path("/quiz/")}">Start the quiz</a>
      <a class="button button-secondary" href="{site_path("/timeline/")}">Browse the timeline</a>
    </div>
  </div>
  <aside class="sample-card">
    <p class="eyebrow">On almost every list</p>
    <h2>Start here, then let the quiz edit it</h2>
    <ol>{sample_items}</ol>
    <p>The full list also names what to skip, including a few things that are unsafe for sleep.</p>
  </aside>
</section>
<section class="section" aria-labelledby="how-heading">
  <h2 id="how-heading">How it works</h2>
  <ol class="steps">
    <li><strong>Answer 8 questions</strong> Budget, space, feeding, season, getting around, first baby or not, childcare, and laundry.</li>
    <li><strong>Get a list, not a catalog</strong> Must-haves, nice-to-haves, what can wait, and what to skip. Example picks follow your budget style.</li>
    <li><strong>Buy on a calendar</strong> Enter a due date. The timeline highlights the week you are in, from 28 weeks out through the first month home.</li>
  </ol>
</section>
<section class="section" aria-labelledby="due-heading">
  <h2 id="due-heading">What should you buy this week?</h2>
  <p class="section-intro">The last week before your due date is the 7 days ending on that date. The first week after birth starts the next day. If you are earlier than 28 weeks out, begin at the welcome note. Nothing there needs buying yet.</p>
  <form class="due-form panel" data-due-redirect method="get" action="{site_path("/timeline/")}">
    <div class="field">
      <label for="home-due">Due date</label>
      <input id="home-due" name="due" type="date" required>
    </div>
    <button class="button" type="submit">Show my week</button>
  </form>
</section>
<section class="section" aria-labelledby="preview-heading">
  <h2 id="preview-heading">A few weeks from the timeline</h2>
  <div class="week-grid">{"".join(preview)}</div>
  <p><a href="{site_path("/timeline/")}">See all 32 weeks</a></p>
</section>
<section class="section" aria-labelledby="faq-heading">
  <h2 id="faq-heading">Questions parents actually ask</h2>
  <div class="faq-list">{"".join(faqs)}</div>
</section>
{newsletter()}
<p class="disclaimer-strip">Safe sleep, car seats, and medicine on this site are general notes. Your prenatal clinician, your baby's pediatrician, and a certified car seat technician are the right people for your family. <a href="{site_path("/disclaimer/")}">Medical and safety disclaimer</a>.</p>
"""
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            website_node(),
            {
                "@type": "FAQPage",
                "@id": canonical("/") + "#faq",
                "url": canonical("/"),
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": entry["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": entry["answer"]},
                    }
                    for entry in FAQ
                ],
            },
        ],
    }
    write(ROOT / "index.html", page(
        "Bump to Baby — What you actually need",
        SITE["description"],
        "/",
        body,
        graph,
        current="/",
    ))


def quiz_page() -> None:
    topics = "".join(f"<li>{esc(question['prompt'])}</li>" for question in QUIZ["questions"])
    body = f"""
<div class="quiz-intro">
{crumbs([("/quiz/", "Quiz")])}
<p class="eyebrow">Registry quiz</p>
<h1>What do you actually need?</h1>
<p class="lede">Eight questions. Your answers stay in this browser and build a must-have list from the gear guide. We don't receive them.</p>
<ol class="check-list">{topics}</ol>
</div>
<div id="quiz-app" aria-live="polite">
  <noscript>
    <p class="callout">The personalized list needs JavaScript. You can still read the <a href="{site_path("/gear/")}">gear list</a> and the <a href="{site_path("/timeline/")}">week-by-week timeline</a>.</p>
  </noscript>
</div>
{newsletter(compact=True)}
"""
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            website_node(),
            breadcrumb_ld([("/quiz/", "Registry quiz")]),
            {
                "@type": "WebPage",
                "name": "Registry quiz",
                "url": canonical("/quiz/"),
                "description": "Answer eight questions and get a personalized must-have baby list.",
            },
        ],
    }
    write(ROOT / "quiz" / "index.html", page(
        "Registry quiz",
        "Answer eight questions and get a personalized must-have baby list based on your space, feeding plan, season, and how you get around.",
        "/quiz/",
        body,
        structured,
        current="/quiz/",
        scripts=["/assets/js/quiz-engine.js", "/assets/js/quiz-ui.js", "/assets/js/site.js"],
    ))


def gear_page() -> None:
    jumps = []
    blocks = []
    position = 1
    list_items = []
    for category in PRODUCTS["categories"]:
        jumps.append(f'<li><a href="#{esc(category["id"])}">{esc(category["name"])}</a></li>')
        cards = []
        for item in PRODUCTS["items"]:
            if item["category"] != category["id"]:
                continue
            label, tone = badge_for(item)
            note = f'<p class="item-note">{esc(item["note"])}</p>' if item.get("note") else ""
            media = thumb_html(item)
            card_class = "item-card has-media" if media else "item-card"
            body = (
                f'<div class="item-card-head"><h3>{esc(item["name"])}</h3>'
                f'<p class="badge {tone}">{esc(label)}</p></div>'
                f"{quantity_html(item)}{picks_html(item)}{note}{affiliate_html(item)}"
            )
            if media:
                body = f'<div class="item-media">{media}</div><div class="item-copy">{body}</div>'
            cards.append(f'<article class="{card_class}" id="{esc(item["id"])}">{body}</article>')
            description = label
            if item.get("note"):
                description += ". " + item["note"]
            list_items.append({
                "@type": "ListItem",
                "position": position,
                "name": item["name"],
                "description": description,
                "url": canonical("/gear/") + "#" + item["id"],
            })
            position += 1
        blocks.append(
            f'<section class="gear-block" aria-labelledby="cat-{esc(category["id"])}">'
            f'<h2 id="{esc(category["id"])}">{esc(category["name"])}</h2>'
            f'<p class="section-intro">{esc(category["intro"])}</p>'
            f'<div class="gear-list">{"".join(cards)}</div></section>'
        )
    body = f"""
{crumbs([("/gear/", "Gear list")])}
<p class="eyebrow">Master list</p>
<h1>The baby gear list, without the haul</h1>
<p class="lede">Must-have, nice-to-have, wait, and skip. Picks are well-known examples. Check current models and recalls before you buy. There are no prices and no reviews here.</p>
<ul class="legend">
  <li><span class="badge badge-must">Must-have</span></li>
  <li><span class="badge badge-nice">Nice-to-have</span></li>
  <li><span class="badge badge-wait">Wait</span></li>
  <li><span class="badge badge-skip">Skip</span></li>
  <li><span class="badge badge-unsafe">Skip — unsafe</span></li>
  <li><span class="badge badge-exclude">Depends on your answers</span></li>
</ul>
<nav aria-label="Gear categories"><ul class="jump-links">{"".join(jumps)}</ul></nav>
{"".join(blocks)}
<p class="disclaimer-strip">Quantities show the full range. The quiz uses the low end if you do laundry every 2–3 days, and the high end if you'd rather do it less. <a href="{site_path("/quiz/")}">Take the quiz</a> for a shorter personal list.</p>
{newsletter(compact=True)}
"""
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            website_node(),
            breadcrumb_ld([("/gear/", "Gear list")]),
            {
                "@type": "ItemList",
                "name": "Bump to Baby gear list",
                "itemListOrder": "https://schema.org/ItemListOrderAscending",
                "numberOfItems": len(list_items),
                "itemListElement": list_items,
            },
        ],
    }
    write(ROOT / "gear" / "index.html", page(
        "Baby gear list",
        "The Bump to Baby master list of must-haves, nice-to-haves, what can wait, and what to skip, with example picks and no made-up prices.",
        "/gear/",
        body,
        structured,
        current="/gear/",
    ))


def timeline_index() -> None:
    by_week = {week["id"]: week for week in WEEKS}
    groups = []
    list_items = []
    position = 1
    for title, ids in WEEK_GROUPS:
        rows = []
        for week_id in ids:
            week = by_week[week_id]
            href = site_path(f"/timeline/{week['id']}/")
            label = week_plain_label(week["offset"])
            rows.append(
                f'<li class="week-row" data-week-id="{esc(week["id"])}" data-offset="{week["offset"]}" '
                f'data-week-title="{esc(week["title"])}" data-week-href="{href}">'
                f'<a href="{href}"><span class="week-code">{esc(label)}</span>'
                f'<span class="week-title">{esc(week["title"])}</span>'
                f'<span class="week-buy">Buy now: {esc(week["buyNow"])}</span></a>'
                f'<p class="range-label" data-range hidden></p></li>'
            )
            list_items.append({
                "@type": "ListItem",
                "position": position,
                "name": f"{label}: {week['title']}",
                "description": week["subject"],
                "url": canonical(f"/timeline/{week['id']}/"),
            })
            position += 1
        groups.append(f'<section><h2>{esc(title)}</h2><ol class="timeline-groups">{"".join(rows)}</ol></section>')
    body = f"""
{crumbs([("/timeline/", "Timeline")])}
<p class="eyebrow">32 weeks</p>
<h1>What to buy, week by week</h1>
<p class="lede">From 28 weeks before your due date (about 12 weeks pregnant) through the fourth week after. Each page has its own buy-now line and can-wait line. Enter your due date to highlight the 7-day block you are in.</p>
<form class="due-form panel" data-due-redirect method="get" action="{site_path("/timeline/")}">
  <div class="field">
    <label for="timeline-due">Due date</label>
    <input id="timeline-due" name="due" type="date" required>
  </div>
  <button class="button" type="submit">Show my week</button>
</form>
<div data-timeline-index>
  <div class="panel result-box" data-week-result hidden></div>
  {"".join(groups)}
</div>
{newsletter(compact=True)}
"""
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            website_node(),
            breadcrumb_ld([("/timeline/", "Timeline")]),
            {
                "@type": "ItemList",
                "name": "Week-by-week baby buying timeline",
                "numberOfItems": len(list_items),
                "itemListElement": list_items,
            },
        ],
    }
    write(ROOT / "timeline" / "index.html", page(
        "Week-by-week timeline",
        "32 weeks of what to buy and what can wait, from 28 weeks before your due date through the first month at home.",
        "/timeline/",
        body,
        structured,
        current="/timeline/",
        scripts=["/assets/js/timeline.js", "/assets/js/site.js"],
    ))


def week_pages() -> None:
    valid = {week["id"] for week in WEEKS}
    timeline_dir = ROOT / "timeline"
    if timeline_dir.exists():
        for child in timeline_dir.iterdir():
            if child.is_dir() and child.name not in valid:
                shutil.rmtree(child)
    lookup = item_map()
    for index, week in enumerate(WEEKS):
        label = week_plain_label(week["offset"])
        crumb = f"{label}: {week['title']}"
        path = f"/timeline/{week['id']}/"
        paragraphs = "".join(f"<p>{esc(paragraph)}</p>" for paragraph in week["paragraphs"])
        related = []
        for item_id in week.get("items") or []:
            item = lookup[item_id]
            related.append(
                f'<li><a href="{site_path("/gear/#" + item_id)}">{esc(item["name"])}</a> '
                f'{affiliate_html(item)}</li>'
            )
        extra = []
        for link in week.get("links") or []:
            extra.append(f'<li><a href="{site_path(link["path"])}">{esc(link["label"])}</a></li>')
        related_html = ""
        if related or extra:
            related_html = (
                '<section aria-labelledby="related-heading"><h2 id="related-heading">Gear mentioned this week</h2>'
                f'<ul class="related-list">{"".join(related + extra)}</ul></section>'
            )
        prev_link = ""
        next_link = ""
        if index > 0:
            prev_week = WEEKS[index - 1]
            prev_link = (
                f'<a href="{site_path("/timeline/" + prev_week["id"] + "/")}">'
                f'Previous: {esc(week_plain_label(prev_week["offset"]))}</a>'
            )
        else:
            prev_link = f'<a href="{site_path("/timeline/")}">All weeks</a>'
        if index < len(WEEKS) - 1:
            next_week = WEEKS[index + 1]
            next_link = (
                f'<a href="{site_path("/timeline/" + next_week["id"] + "/")}">'
                f'Next: {esc(week_plain_label(next_week["offset"]))}</a>'
            )
        else:
            next_link = f'<a href="{site_path("/timeline/")}">All weeks</a>'
        description = meta_description(week)
        search_title = f"{week_search_label(week['offset'])}: {week['title']}"
        body = f"""
{crumbs([("/timeline/", "Timeline"), (path, crumb)])}
<article data-week-id="{esc(week["id"])}" data-offset="{week["offset"]}">
  <p class="eyebrow">{esc(week_eyebrow(week["offset"]))}</p>
  <h1>{esc(week["title"])}</h1>
  <p class="dek">{esc(week["subject"])}</p>
  <div class="week-banner" data-week-banner hidden></div>
  <form class="due-form" data-due-redirect method="get" action="{site_path("/timeline/")}">
    <div class="field">
      <label for="week-due">Due date</label>
      <input id="week-due" name="due" type="date">
    </div>
    <button class="button button-secondary" type="submit">Highlight my week</button>
  </form>
  <aside class="buy-box" aria-label="Buy now and can wait">
    <h2 class="buy-now">Buy now</h2>
    <p>{esc(week["buyNow"])}</p>
    <h2 class="wait">Can wait</h2>
    <p>{esc(week["canWait"])}</p>
  </aside>
  <div class="prose">{paragraphs}</div>
  {related_html}
  <nav class="pager" aria-label="Nearby weeks">{prev_link}{next_link}</nav>
</article>
<p class="disclaimer-strip">General information. For safe sleep, car seats, and any medicine, <a href="{site_path("/disclaimer/")}">read the disclaimer</a> and talk with your care team.</p>
{newsletter(compact=True)}
"""
        structured = {
            "@context": "https://schema.org",
            "@graph": [
                website_node(),
                breadcrumb_ld([("/timeline/", "Timeline"), (path, crumb)]),
                {
                    "@type": "Article",
                    "headline": search_title,
                    "description": description,
                    "datePublished": PUBLISHED,
                    "dateModified": PUBLISHED,
                    "author": {"@type": "Organization", "name": NAME, "url": canonical("/")},
                    "publisher": {"@type": "Organization", "name": NAME, "url": canonical("/")},
                    "mainEntityOfPage": canonical(path),
                    "image": OG_IMAGE,
                },
            ],
        }
        write(ROOT / "timeline" / week["id"] / "index.html", page(
            search_title,
            description,
            path,
            body,
            structured,
            og_type="article",
            current="/timeline/",
            scripts=["/assets/js/timeline.js", "/assets/js/site.js"],
            brand_sep=" | ",
        ))


def simple_page(path: str, title: str, description: str, body: str, current: str = "") -> None:
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            website_node(),
            breadcrumb_ld([(path, title)]),
            {"@type": "WebPage", "name": title, "url": canonical(path), "description": description},
        ],
    }
    write(ROOT / path.strip("/") / "index.html", page(title, description, path, crumbs([(path, title)]) + body, structured, current=current))


def newsletter_page() -> None:
    body = f"""
<p class="eyebrow">Email</p>
<h1>Weekly notes for your due date</h1>
<p class="lede">One email a week, matched to your due date. Each note says what to buy now and what can wait, from 28 weeks before the due date through the first month home.</p>
{newsletter()}
"""
    simple_page(
        "/newsletter/",
        "Newsletter",
        "One email a week of buy-now and can-wait notes, keyed to your due date. Signup asks for your email and due date.",
        body,
        current="/newsletter/",
    )


def privacy_page() -> None:
    body = f"""
<p class="eyebrow">Privacy</p>
<h1>Privacy</h1>
<p class="lede">Updated {esc(PUBLISHED)}. Bump to Baby is a static website. It has no accounts.</p>
<div class="prose">
  <h2>What stays in your browser</h2>
  <p>The registry quiz runs on your device. Answers are put in the page address when you see results, so you can refresh that list. They are not sent to us.</p>
  <p>If you enter a due date, the page saves it in this browser under the local storage key <code>btb-due</code>. That lets the timeline highlight your week when you come back. You can clear it by deleting site data for this address in your browser.</p>
  <h2>Email</h2>
  <p>The newsletter signup is a MailerLite embedded form named Bump to Baby Signup. It asks for an email address and a due date. Submitting it sends those two fields to MailerLite, which runs the mailing list. MailerLite's privacy policy applies to that submission. Pages that show the form also load MailerLite's script from <code>assets.mailerlite.com</code>.</p>
  <p>A due date entered on the timeline stays in this browser. That saved date is not sent to MailerLite unless you also submit the newsletter form.</p>
  <h2>Affiliate links</h2>
  <p>Some gear links go to Amazon and include an Associates tag. Amazon handles those visits under its own privacy policy. This site does not receive your Amazon account details. See the <a href="{site_path("/affiliate-disclosure/")}">affiliate disclosure</a>.</p>
  <h2>Hosting</h2>
  <p>GitHub Pages hosts the files and may keep ordinary server logs. This site does not add tracking pixels or advertising cookies of its own.</p>
  <h2>Children</h2>
  <p>The site is written for expecting parents. It is not directed at children, and it does not ask children to create accounts.</p>
  <h2>Contact</h2>
  <p>Questions about this site can go to the <a href="https://github.com/nicolasconnelly-bot/bump-to-baby">GitHub repository</a>.</p>
</div>
"""
    simple_page(
        "/privacy/",
        "Privacy",
        "How the Bump to Baby site handles quiz answers, the local due date, and the MailerLite newsletter signup.",
        body,
    )


def affiliate_page() -> None:
    body = f"""
<p class="eyebrow">Disclosure</p>
<h1>Affiliate disclosure</h1>
<p class="lede">Updated {esc(PUBLISHED)}. This site is an editorial gear list. It does not show prices, star ratings, or customer reviews.</p>
<div class="prose">
  <p>As an Amazon Associate I earn from qualifying purchases.</p>
  <h2>Amazon links</h2>
  <p>Commercial items link to Amazon with Associates tag <code>bumptobaby0d-20</code>. A product-page link is used only when that ASIN was checked against the named product. Other items open an Amazon search for the product name. Links open in a new tab.</p>
  <p>The site owner may earn a commission when someone buys through these links. That commission does not add a fee on this site. Recommendations come from the editorial list, not from who pays a commission.</p>
  <h2>Items with no store link</h2>
  <p>Checking smoke and carbon monoxide detectors is a task, not a store listing, so that item has no product link. Saline drops are a product, but this site does not have a checked product page for them, so that item has no store link. Crib bumpers and inclined sleepers are unsafe for sleep, so this site does not link to them for sale.</p>
  <h2>Example picks</h2>
  <p>Named products are widely sold examples so a list is easier to picture. They are not a promise that a model is current. Check the latest version, the manual, and any recall before you buy.</p>
</div>
"""
    simple_page(
        "/affiliate-disclosure/",
        "Affiliate disclosure",
        "Bump to Baby uses Amazon Associates links with tag bumptobaby0d-20. Example picks are editorial, and this site shows no prices or reviews.",
        body,
    )


def disclaimer_page() -> None:
    body = f"""
<p class="eyebrow">Please read this</p>
<h1>Medical and safety disclaimer</h1>
<p class="lede">Updated {esc(PUBLISHED)}. Bump to Baby is a shopping and planning guide. It is not medical care, not a car-seat inspection, and not dosing advice.</p>
<div class="prose">
  <h2>Not medical advice</h2>
  <p>Nothing here diagnoses, treats, or tells you what your baby needs. Talk with your prenatal clinician and your baby's pediatrician about feeding, illness, medicine, and sleep. If something feels urgent, contact them or emergency services rather than a website.</p>
  <h2>Safe sleep</h2>
  <p>The general notes on this site follow a simple pattern: alone, on the back, on a firm flat mattress in a crib, bassinet, or play yard made for sleep, with nothing else in that space. No bumpers, pillows, quilts, stuffed animals, or sleep positioners. A swaddle or wearable sleep sack is the cover, and swaddling stops when a baby shows signs of rolling. Many families room-share for the first months, with the baby in a separate sleep space. A bouncer or swing is not a sleep space. This is general information. Ask your pediatrician what applies to your baby.</p>
  <h2>Car seats</h2>
  <p>Most hospitals expect a rear-facing car seat for the ride home. Buy it new, or use one only if you know its history, including whether it has been in a crash. Check the expiration date. Have the install checked by a certified child passenger safety technician or a free check through a hospital or fire station. The "inch test" mentioned in week 12 is a general reminder, not a substitute for that check. Airline rules differ; ask the airline before you fly. The National Highway Traffic Safety Administration publishes car seat information at <a href="https://www.nhtsa.gov/vehicle-safety/car-seats-and-booster-seats">nhtsa.gov</a>.</p>
  <h2>Medicine</h2>
  <p>Infant acetaminophen is on the gear list because families are often told to have some on hand. This site does not say whether your baby should have it, and it does not give doses. Ask your pediatrician before you use it. The same is true for saline drops and any other health item named here.</p>
  <h2>Recalls and standards</h2>
  <p>Cribs should meet current safety standards and have fixed sides. Mattresses should be firm and tight-fitting. Anchor dressers to the wall. Check recalls before you buy or reuse gear. The U.S. Consumer Product Safety Commission lists recalls at <a href="https://www.cpsc.gov/Recalls">cpsc.gov/Recalls</a>.</p>
  <h2>Feeding</h2>
  <p>Insurance may cover a breast pump in the United States. Formula choices and breastfeeding problems belong with your clinician or a lactation consultant. Buy one small can of formula first if you are using it. Store-brand formulas sold in the U.S. have to meet FDA standards; that is a regulatory fact, not a ranking of brands.</p>
</div>
"""
    simple_page(
        "/disclaimer/",
        "Medical and safety disclaimer",
        "Bump to Baby is general planning information, not medical, car-seat, or dosing advice. Talk with your clinicians and a certified car seat technician.",
        body,
    )


def not_found() -> None:
    body = f"""
<h1>That page is not here</h1>
<p class="lede">The quiz, the gear list, and the 32-week timeline are all linked below.</p>
<div class="actions">
  <a class="button" href="{site_path("/")}">Home</a>
  <a class="button button-secondary" href="{site_path("/quiz/")}">Quiz</a>
  <a class="button button-secondary" href="{site_path("/timeline/")}">Timeline</a>
</div>
"""
    write(ROOT / "404.html", page(
        "Page not found",
        "That Bump to Baby page is not here. Try the quiz, the gear list, or the week-by-week timeline.",
        "/404.html",
        body,
        robots="noindex",
    ))


def robots() -> None:
    text = f"""User-agent: *
Allow: /

Sitemap: {ORIGIN}/sitemap.xml
"""
    write(ROOT / "robots.txt", text)


def sitemap() -> None:
    paths = ["/", "/quiz/", "/gear/", "/timeline/", "/newsletter/", "/privacy/", "/affiliate-disclosure/", "/disclaimer/"]
    paths.extend(f"/timeline/{week['id']}/" for week in WEEKS)
    urls = []
    for path in paths:
        urls.append(
            "  <url>\n"
            f"    <loc>{esc(canonical(path))}</loc>\n"
            f"    <lastmod>{PUBLISHED}</lastmod>\n"
            "  </url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    write(ROOT / "sitemap.xml", xml)


def llms() -> None:
    lines = [
        f"# {NAME}",
        "",
        "> Free static guide for expecting parents: an 8-question registry quiz, a 32-week buying timeline, and a master gear list. Not medical advice. No prices, ratings, or reviews.",
        "",
        "The quiz runs in the browser. Product links in `data/products.json` go to Amazon "
        "with Associates tag `bumptobaby0d-20`. A product page is used only when that ASIN "
        "was checked against the named product; other items use an Amazon search. "
        "As an Amazon Associate I earn from qualifying purchases. "
        "Safe sleep, car seats, and medicine notes are general. Parents should talk with their clinicians and a certified car seat technician.",
        "",
        "## Start here",
        "",
        f"- [Home]({canonical('/')}): What the site is, a due-date form, and the FAQ.",
        f"- [Registry quiz]({canonical('/quiz/')}): Eight questions that add or remove gear. Results stay on the device.",
        f"- [Gear list]({canonical('/gear/')}): Must-have, nice-to-have, wait, skip, and unsafe items, with example picks.",
        f"- [Timeline]({canonical('/timeline/')}): All 32 weeks. A due date highlights the current 7-day block.",
        f"- [Newsletter]({canonical('/newsletter/')}): MailerLite signup for week-by-week buy-now notes keyed to a due date. Email and due date go to MailerLite.",
        f"- [Disclaimer]({canonical('/disclaimer/')}): Medical, safe-sleep, car-seat, and medicine limits.",
        f"- [Privacy]({canonical('/privacy/')}): No site accounts. Quiz stays on the device. Newsletter signup goes to MailerLite.",
        f"- [Affiliate disclosure]({canonical('/affiliate-disclosure/')}): Amazon Associates links and the commission disclosure.",
        "",
        "## Week-by-week timeline",
        "",
    ]
    for week in WEEKS:
        lines.append(
            f"- [{week_plain_label(week['offset'])}: {week['title']}]({canonical('/timeline/' + week['id'] + '/')}): "
            f"{week['subject']} Buy now: {week['buyNow']} Can wait: {week['canWait']}"
        )
    lines.extend([
        "",
        "## FAQ",
        "",
    ])
    for entry in FAQ:
        lines.append(f"### {entry['question']}")
        lines.append("")
        lines.append(entry["answer"])
        lines.append("")
    lines.append("## Optional")
    lines.append("")
    lines.append(f"- [Machine-readable guide]({canonical('/llms.txt')}): this file.")
    lines.append("")
    write(ROOT / "llms.txt", "\n".join(lines))


def validate() -> None:
    blob = json.dumps(PRODUCTS)
    if "{{AFFILIATE_LINK}}" in blob or PLACEHOLDER:
        raise SystemExit("affiliate placeholder should be empty; each item needs its own link")
    tag = "tag=bumptobaby0d-20"
    for item in PRODUCTS["items"]:
        link = item.get("link", None)
        if link is False:
            if item.get("image"):
                raise SystemExit(f"{item['id']} should not have a product image")
            if item.get("task") and item.get("unsafe"):
                raise SystemExit(f"{item['id']} cannot be both a task and an unsafe product")
            continue
        if item.get("task"):
            raise SystemExit(f"{item['id']} is a task and should not have a store link")
        if not isinstance(link, str) or not link.startswith("https://www.amazon.com/"):
            raise SystemExit(f"{item['id']} needs an Amazon link or link:false")
        if tag not in link:
            raise SystemExit(f"{item['id']} is missing the Associates tag")
        if "/dp/" in link:
            if not re.fullmatch(r"https://www\.amazon\.com/dp/[A-Z0-9]{10}\?tag=bumptobaby0d-20", link):
                raise SystemExit(f"{item['id']} has a malformed product-page link")
        elif not link.startswith("https://www.amazon.com/s?k="):
            raise SystemExit(f"{item['id']} link is neither a product page nor a search")
        image = item.get("image")
        if not image:
            raise SystemExit(f"{item['id']} is linked but has no product image")
        if not re.fullmatch(r"/assets/img/products/[a-z0-9-]+\.webp", image):
            raise SystemExit(f"{item['id']} image is not a local product photo")
        if not (ROOT / image.lstrip("/")).is_file():
            raise SystemExit(f"{item['id']} image file is missing")
        alt = item.get("imageAlt")
        if not isinstance(alt, str) or not alt.strip():
            raise SystemExit(f"{item['id']} image is missing alt text")
    ids = {item["id"] for item in PRODUCTS["items"]}
    if len(ids) != len(PRODUCTS["items"]):
        raise SystemExit("duplicate product ids")
    categories = {category["id"] for category in PRODUCTS["categories"]}
    for item in PRODUCTS["items"]:
        if item["category"] not in categories:
            raise SystemExit(f"unknown category on {item['id']}")
        if item["status"] not in {"must", "nice", "wait", "skip", "exclude"}:
            raise SystemExit(f"bad status on {item['id']}")
    if len(WEEKS) != 32:
        raise SystemExit(f"expected 32 weeks, found {len(WEEKS)}")
    seen = set()
    for week in WEEKS:
        if week["id"] in seen:
            raise SystemExit("duplicate week " + week["id"])
        seen.add(week["id"])
        for item_id in week.get("items") or []:
            if item_id not in ids:
                raise SystemExit(f"{week['id']} references unknown item {item_id}")
        meta_description(week)
        week_search_label(week["offset"])
    if set(WEEK_DESCRIPTIONS) != seen:
        raise SystemExit("search descriptions do not match the week ids")
    grouped = [week_id for _, ids in WEEK_GROUPS for week_id in ids]
    if grouped != [week["id"] for week in WEEKS]:
        raise SystemExit("timeline groups do not match week order")


def main() -> None:
    validate()
    home_page()
    quiz_page()
    gear_page()
    timeline_index()
    week_pages()
    newsletter_page()
    privacy_page()
    affiliate_page()
    disclaimer_page()
    not_found()
    robots()
    sitemap()
    llms()
    print("build ok")


if __name__ == "__main__":
    main()
