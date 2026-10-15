# Bump to Baby

A free static site for expecting parents: an 8-question registry quiz, a 32-week buying timeline, and a master gear list. It is plain HTML, CSS, and JavaScript. GitHub Pages can serve it from `main` with no build runner and no paid services.

Quiz answers stay in the browser. There is no backend, no account, and no analytics. Product links are the placeholder `{{AFFILIATE_LINK}}` until you swap them.

## Pages

- `/` — home, due-date form, FAQ
- `/quiz/` — personalized must-have list
- `/gear/` — the full list behind the quiz
- `/timeline/` and `/timeline/w-28/` through `/timeline/w-plus-4/` — one indexable page per week
- `/newsletter/` — signup form ready for a MailerLite embed
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

Generated HTML is committed so GitHub Pages does not need a build step. `.nojekyll` is required: without it, Jekyll/Liquid would erase `{{AFFILIATE_LINK}}`.

## Swap affiliate links

In `data/products.json`, replace `{{AFFILIATE_LINK}}` with a full `https://` URL. You can replace the shared placeholder or set a `link` on one item. Use `"link": false` for tasks that should never have a store link (smoke detectors, saline drops).

Items that still use the placeholder show the token as text. They do not link out. Rebuild after you change the file.

## Newsletter

The form is a MailerLite placeholder. Submitting it does not send email. To connect a list, paste your MailerLite embed over the form marked `MAILERLITE EMBED` in `scripts/build.py`, then rebuild. See `/newsletter/` for the same steps.

## Check the site

```bash
python3 scripts/smoke_test.py
```

That rebuilds, checks internal links, titles, meta descriptions, Open Graph tags, JSON-LD, the sitemap, `llms.txt`, and the affiliate placeholder, and opens the quiz in headless Chrome.

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
