"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
let failures = 0;

function assert(condition, message) {
  if (!condition) {
    failures += 1;
    console.error("FAIL:", message);
  }
}

function load(file, exportName) {
  const context = { console };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, file), "utf8"), context);
  return context[exportName];
}

const products = JSON.parse(fs.readFileSync(path.join(root, "data/products.json"), "utf8"));
const quiz = JSON.parse(fs.readFileSync(path.join(root, "data/quiz.json"), "utf8"));
const weeks = JSON.parse(fs.readFileSync(path.join(root, "data/weeks.json"), "utf8"));
const BumpQuiz = load("assets/js/quiz-engine.js", "BumpQuiz");
const BumpTimeline = load("assets/js/timeline.js", "BumpTimeline");

assert(products.affiliatePlaceholder == null, "shared affiliate placeholder is unused");
assert(!JSON.stringify(products).includes("{{AFFILIATE_LINK}}"), "placeholder token is gone");
products.items.forEach((item) => {
  if (item.link === false) {
    assert(!item.image, "unlinked item has no product image: " + item.id);
    return;
  }
  assert(typeof item.link === "string" && item.link.indexOf("tag=bumptobaby0d-20") !== -1, "associates tag on " + item.id);
  if (!item.image) return;
  const asin = (String(item.link).match(/\/dp\/([A-Z0-9]{10})/) || [])[1];
  assert(item.image === "https://m.media-amazon.com/images/P/" + asin + ".01._SL160_.jpg", "thumbnail matches ASIN for " + item.id);
});
const sheetsItem = products.items.find((item) => item.id === "sheets");
assert(sheetsItem.link === "https://www.amazon.com/dp/B09CGM51D1?tag=bumptobaby0d-20", "fitted sheets use the verified Burt's Bees page");
assert(sheetsItem.image === "https://m.media-amazon.com/images/P/B09CGM51D1.01._SL160_.jpg", "fitted sheets have a catalog thumbnail");

const ids = new Set();
products.items.forEach((item) => {
  assert(!ids.has(item.id), "duplicate id " + item.id);
  ids.add(item.id);
  assert(products.categories.some((category) => category.id === item.category), "category for " + item.id);
});

weeks.weeks.forEach((week) => {
  (week.items || []).forEach((id) => {
    assert(ids.has(id), week.id + " references unknown item " + id);
  });
});

function plan(answers) {
  return BumpQuiz.buildPlan(answers, products, quiz);
}

function has(list, id) {
  return list.some((item) => item.id === id);
}

const small = plan({
  tier: "budget",
  space: "small",
  feed: "breast",
  season: "winter",
  move: "car",
  first: "yes",
  care: "home",
  laundry: "normal"
});

assert(has(small.must, "mini-crib"), "small space includes mini crib");
assert(has(small.must, "bassinet"), "small space includes bassinet");
assert(has(small.must, "play-yard"), "small space includes play yard");
assert(!has(small.must, "crib"), "full crib is not a must in a small space");
assert(has(small.skip, "crib"), "full crib is listed as a skip when swapped");
assert(has(small.must, "pump"), "breastfeeding includes a pump");
assert(!has(small.must, "formula") && !has(small.skip, "formula"), "formula is not on an exclusive breastfeeding list");
assert(has(small.must, "humidifier"), "winter humidifier is a must");
assert(has(small.must, "car-seat-cover"), "winter car seat cover is a must");
assert(!has(small.must, "fan"), "winter list does not add a fan");
assert(has(small.nice, "carrier"), "car-only carrier stays nice-to-have");
assert(has(small.must, "stroller"), "car travel system stroller is a must");
assert(small.must.find((item) => item.id === "bottles").planLine === "2–4 small bottles", "breast bottle count");
assert(small.must.find((item) => item.id === "clothing-0-3").quantityText.indexOf("7 bodysuits") === 0, "normal laundry uses the low end");
assert(small.first48 && small.first48.length === 6, "first baby gets the 48-hour list");
assert(small.owned.length === 0, "first baby does not get the owned-gear list");
assert(has(small.unsafe, "bumpers") && has(small.unsafe, "inclined-sleepers"), "unsafe sleep items stay visible as skips");
assert(small.must.find((item) => item.id === "stroller").notes.indexOf(quiz.secondhandNote) !== -1, "budget note on big gear");
assert(small.must.find((item) => item.id === "car-seat").linkLabel === "https://www.amazon.com/dp/B09Q9H828S?tag=bumptobaby0d-20", "verified car seat link");
assert(small.must.find((item) => item.id === "sheets").image === "https://m.media-amazon.com/images/P/B09CGM51D1.01._SL160_.jpg", "quiz keeps the sheets thumbnail");
assert(!small.unsafe.find((item) => item.id === "bumpers").image, "unsafe items are not given a product photo");
assert(small.must.find((item) => item.id === "detectors").linkLabel === null, "detectors have no product link");
assert(small.unsafe.find((item) => item.id === "bumpers").linkLabel === null, "unsafe bumpers are not linked for sale");
assert(small.title === "Your Must-Have List (Budget · Small space · Breastfeeding)", "results title");
assert(small.mustCount === small.must.length && small.skipCount === small.skip.length, "counts match lists");

const reuse = plan({
  tier: "premium",
  space: "nursery",
  feed: "formula",
  season: "summer",
  move: "walk",
  first: "no",
  care: "out",
  laundry: "low"
});

assert(!has(reuse.must, "crib"), "existing gear hides the crib from must-haves");
assert(has(reuse.owned, "crib"), "existing gear asks you to check the crib");
assert(has(reuse.owned, "carrier"), "walker carrier is checked, not re-bought, when gear exists");
assert(has(reuse.skip, "pump"), "formula removes the pump");
assert(has(reuse.must, "formula"), "formula is a must");
assert(reuse.must.find((item) => item.id === "bottles").planLine === "6–8 bottles", "formula bottle count");
assert(has(reuse.must, "labels") && has(reuse.must, "cooler-bag"), "daycare extras");
assert(!has(reuse.must, "pump-bag"), "no pump bag without breastfeeding");
assert(has(reuse.must, "sun-shade") && has(reuse.must, "fan"), "summer shade and fan");
assert(!has(reuse.must, "humidifier"), "summer humidifier stays off the must list");
assert(has(reuse.must, "monitor"), "nursery monitor stays a must even when big gear is hidden");
assert(reuse.must.find((item) => item.id === "clothing-0-3").quantityText.indexOf("10 bodysuits") === 0, "low laundry uses the high end");
assert(reuse.first48 === null, "later baby does not get the first-48 list");
assert(reuse.nice.find((item) => item.id === "glider") === undefined, "glider is big and moves to the owned list");
assert(has(reuse.owned, "glider"), "glider is in the owned list");
assert(reuse.owned.find((item) => item.id === "glider").badges.indexOf("Nice-to-have+") !== -1, "nursery glider is nice-to-have+");

const traveler = plan({
  tier: "mid",
  space: "multilevel",
  feed: "combo",
  season: "fall",
  move: "travel",
  first: "yes",
  care: "out",
  laundry: "normal"
});

assert(has(traveler.must, "pump") && has(traveler.must, "formula"), "combo keeps breast and formula basics");
assert(has(traveler.must, "nursing-pillow"), "combo includes the nursing pillow");
assert(traveler.must.find((item) => item.id === "bottles").planLine === "4–6 bottles", "combo bottle count");
assert(has(traveler.must, "pump-bag") && has(traveler.must, "pump-parts"), "pumping daycare extras");
assert(has(traveler.must, "second-station"), "second diaper station");
assert(has(traveler.must, "monitor"), "multi-level monitor");
assert(traveler.wait.find((item) => item.id === "gates").notes.some((line) => line.indexOf("second set") !== -1), "second gate set");
assert(has(traveler.must, "play-yard") && has(traveler.must, "compact-stroller"), "travel crib and compact stroller");
assert(has(traveler.must, "humidifier") && has(traveler.must, "car-seat-cover"), "fall warmth items");
assert(traveler.first48 && traveler.first48.length === 6, "traveler first-48 list");

const mix = plan({
  tier: "mid",
  space: "nursery",
  feed: "breast",
  season: "spring",
  move: "mix",
  first: "yes",
  care: "home",
  laundry: "normal"
});

assert(has(mix.must, "carrier") && has(mix.must, "stroller") && has(mix.must, "crib"), "mix keeps carrier, stroller, crib");
assert(has(mix.must, "fan") && has(mix.must, "sun-shade"), "spring fan and shade");
assert(!has(mix.must, "formula"), "breastfeeding does not require formula");
assert(mix.nice.find((item) => item.id === "glider").badges.indexOf("Nice-to-have+") !== -1, "glider priority");

function expectWeek(due, today, id, flags) {
  const result = BumpTimeline.weekForDueDate(due, today);
  assert(result && result.id === id, due + " on " + today + " should be " + id + " but was " + (result && result.id));
  if (flags && flags.early) assert(result.early, id + " early flag");
  if (flags && flags.past) assert(result.past, id + " past flag");
  if (flags && flags.current) assert(!result.early && !result.past, id + " should be the current window");
}

expectWeek("2026-10-14", "2026-10-14", "w-1", { current: true });
expectWeek("2026-10-14", "2026-10-08", "w-1", { current: true });
expectWeek("2026-10-14", "2026-10-07", "w-2", { current: true });
expectWeek("2026-10-14", "2026-04-02", "w-28", { current: true });
expectWeek("2026-10-14", "2026-04-01", "w-28", { early: true });
expectWeek("2026-10-14", "2026-10-15", "w-plus-1", { current: true });
expectWeek("2026-10-14", "2026-10-21", "w-plus-1", { current: true });
expectWeek("2026-10-14", "2026-10-22", "w-plus-2", { current: true });
expectWeek("2026-10-14", "2026-11-11", "w-plus-4", { current: true });
expectWeek("2026-10-14", "2026-11-12", "w-plus-4", { past: true });

const dueRange = BumpTimeline.rangeForOffset("2026-10-14", -1);
assert(dueRange.start === "2026-10-08" && dueRange.end === "2026-10-14", "W-1 date range");
const earlyRange = BumpTimeline.rangeForOffset("2026-10-14", -28);
assert(earlyRange.start === "2026-04-02" && earlyRange.end === "2026-04-08", "W-28 date range");
const homeRange = BumpTimeline.rangeForOffset("2026-10-14", 1);
assert(homeRange.start === "2026-10-15" && homeRange.end === "2026-10-21", "W+1 date range");

assert(BumpTimeline.weekForDueDate("nope", "2026-10-14") === null, "invalid due date");

if (failures) {
  console.error(failures + " logic test(s) failed");
  process.exit(1);
}
console.log("logic tests passed");
