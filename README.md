# Bump to Baby

A free static site for expecting parents: an 8-question registry quiz, a 32-week buying timeline, and a master gear list. It is plain HTML, CSS, and JavaScript. GitHub Pages can serve it from `main` with no build runner and no paid services.

Quiz answers stay in the browser. There is no backend, no account, and no analytics. Product links go to Amazon with Associates tag `bumptobaby0d-20`.

## Pages

- `/` — home, due-date form, FAQ
- `/quiz/` — personalized must-have list
- `/gear/` — the full list behind the quiz
- `/timeline/` and `/timeline/w-28/` through `/timeline/w-plus-4/` — one indexable page per week
- `/newsletter/` — MailerLite signup for the weekly notes
- `/disclaimer/`, `/privacy/`, `/affiliate-disclosure/`

## Edit content

| File | What it controls |
| --- | --- |
| `data/products.json` | Categories, must / nice / wait / skip, example picks, affiliate links |
| `data/quiz.json` | The eight questions and the first-48-hours list |
| `data/weeks.json` | The 32 weekly notes |
| `data/faq.json` | Home FAQ copy and FAQPage schema |
| `data/site.json` | Site name, URL, and base path |

After any edit, rebuild:

```bash
python3 scripts/build.py
```

Generated HTML is committed so GitHub Pages does not need a build step. `.nojekyll` keeps GitHub Pages from running Jekyll on these files.

## Affiliate links

Each item in `data/products.json` has its own `link`. A `https://www.amazon.com/dp/<ASIN>?tag=bumptobaby0d-20` URL is used when that ASIN was checked against the named product. A search URL is only for an item that does not have a checked product page. Use `"link": false` for a real task (also set `"task": true`), for a product that has no checked page, and for unsafe sleep items that should not be offered for sale. Product photos are local WebP files in `assets/img/products/`, about 400 pixels wide, with `imageAlt` set. Do not hotlink images. Rebuild after you change a link or a photo.

## Newsletter

The signup is the MailerLite embedded form `nv7GCt` (account `2715249`). Pages that include it load the MailerLite universal script in the document head. The form asks for an email and a due date and submits them to MailerLite.

## Check the site

```bash
python3 scripts/smoke_test.py
```

That rebuilds, checks internal links, titles, meta descriptions, Open Graph tags, JSON-LD, the sitemap, `llms.txt`, and the Amazon affiliate links, and opens the quiz in headless Chrome.

Preview locally with the GitHub Pages base path:

```bash
python3 scripts/serve.py
```

Then open `http://127.0.0.1:8765/bump-to-baby/`.

## GitHub Pages

1. On GitHub, open **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Choose branch **main** and folder **/ (root)**, then save.
4. Wait until the deployment finishes. The site is `https://nicolasconnelly-bot.github.io/bump-to-baby/`.

## Safety

Gear, sleep, car-seat, and medicine notes are general planning information. They are not personal medical advice, not a car-seat inspection, and not dosing instructions. The disclaimer page says so in full.
