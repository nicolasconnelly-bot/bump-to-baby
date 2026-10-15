/* Client-side registry rules. Edit copy in data/quiz.json and data/products.json. */
(function (root, factory) {
  root.BumpQuiz = factory();
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  var TIER_LABEL = { budget: "Budget", mid: "Middle", premium: "Premium" };
  var SPACE_LABEL = { small: "Small space", nursery: "Nursery", multilevel: "Multi-level" };
  var FEED_LABEL = { breast: "Breastfeeding", formula: "Formula", combo: "Combo" };

  function cloneItem(item) {
    return {
      id: item.id,
      name: item.name,
      category: item.category,
      status: item.status,
      origin: item.origin || "master",
      big: !!item.big,
      caution: !!item.caution,
      unsafe: !!item.unsafe,
      link: item.link,
      image: item.image || "",
      picks: item.picks || {},
      quantities: item.quantities || null,
      notes: item.note ? [item.note] : [],
      ownedNote: item.ownedNote || "Check recalls and the condition before you reuse it.",
      badges: [],
      quantityText: "",
      planLine: "",
      pick: "",
      linkLabel: null
    };
  }

  function byId(items) {
    var map = {};
    items.forEach(function (item) {
      map[item.id] = item;
    });
    return map;
  }

  function mustExist(map, id) {
    if (!map[id]) {
      throw new Error("Unknown product id: " + id);
    }
    return map[id];
  }

  function setStatus(map, id, status) {
    mustExist(map, id).status = status;
  }

  function addNote(map, id, text) {
    if (text) mustExist(map, id).notes.push(text);
  }

  function addBadge(map, id, text) {
    mustExist(map, id).badges.push(text);
  }

  function pickFor(item, tier) {
    var picks = item.picks || {};
    return picks[tier] || picks.mid || picks.budget || picks.premium || "";
  }

  function quantityText(item, laundry) {
    if (!item.quantities || !item.quantities.length) return "";
    var useHigh = laundry === "low";
    return item.quantities.map(function (part) {
      var count = useHigh ? part.high : part.low;
      return count + " " + part.item;
    }).join(", ");
  }

  function resolveLink(item, products) {
    if (item.link === false) return null;
    if (typeof item.link === "string" && item.link) return item.link;
    return products.affiliatePlaceholder;
  }

  function validate(answers) {
    var allowed = {
      tier: ["budget", "mid", "premium"],
      space: ["small", "nursery", "multilevel"],
      feed: ["breast", "formula", "combo"],
      season: ["spring", "summer", "fall", "winter"],
      move: ["car", "walk", "mix", "travel"],
      first: ["yes", "no"],
      care: ["out", "home"],
      laundry: ["low", "normal"]
    };
    Object.keys(allowed).forEach(function (key) {
      if (allowed[key].indexOf(answers[key]) === -1) {
        throw new Error("Unexpected answer for " + key);
      }
    });
  }

  function buildPlan(answers, products, quiz) {
    validate(answers);
    var items = products.items.map(cloneItem);
    var map = byId(items);
    var tier = answers.tier;
    var space = answers.space;
    var feed = answers.feed;
    var season = answers.season;
    var move = answers.move;
    var care = answers.care;
    var cold = season === "fall" || season === "winter";
    var warm = season === "spring" || season === "summer";
    var nursing = feed === "breast" || feed === "combo";

    if (space === "small") {
      setStatus(map, "crib", "skip");
      addNote(map, "crib", "Swapped out for a small room: use a bassinet plus a mini or compact crib, and a play yard as the main sleep space.");
      setStatus(map, "mini-crib", "must");
      setStatus(map, "bassinet", "must");
      addNote(map, "bassinet", "This is the first-months sleep space beside your bed.");
      setStatus(map, "play-yard", "must");
      addNote(map, "play-yard", "In a small home, treat the play yard as a main sleep space. Use only the firm mattress made for that model.");
      addNote(map, "changing-pad", "Skip a standalone changing table. Use this pad on a dresser or another stable surface.");
      addNote(map, "dresser", "Optional in a small home if you already have a stable surface for the changing pad.");
      addNote(map, "mattress", "Get the firm mattress sized for the mini crib you are using. Same tight-fit rule.");
    } else if (space === "nursery") {
      setStatus(map, "crib", "must");
      setStatus(map, "mini-crib", "exclude");
      addNote(map, "crib", "A full-size crib fits a dedicated nursery. Many babies still start in a bassinet in your room.");
      addBadge(map, "dresser", "Nice-to-have+");
      addNote(map, "dresser", "For a nursery, prioritize a dresser with a changing topper.");
      addBadge(map, "glider", "Nice-to-have+");
      addNote(map, "glider", "Moved up for a nursery. A chair you already like is still fine.");
      setStatus(map, "monitor", "must");
      addNote(map, "monitor", "Moved up to must-have because the nursery may be in another room.");
    } else {
      setStatus(map, "crib", "must");
      setStatus(map, "mini-crib", "exclude");
      setStatus(map, "second-station", "must");
      addNote(map, "gates", "Get a second set of baby gates for the other level. You will need them by about 6 months.");
      setStatus(map, "monitor", "must");
      addNote(map, "monitor", "Moved up to must-have in a multi-level home.");
    }

    var pumpItems = ["pump", "manual-pump", "nursing-bras", "nipple-cream", "breast-pads", "milk-bags", "nursing-pillow"];
    if (nursing) {
      setStatus(map, "pump", "must");
      setStatus(map, "nursing-bras", "must");
      setStatus(map, "nipple-cream", "must");
      setStatus(map, "breast-pads", "must");
      setStatus(map, "milk-bags", "must");
      setStatus(map, "nursing-pillow", "must");
      setStatus(map, "manual-pump", "nice");
    } else {
      pumpItems.forEach(function (id) {
        setStatus(map, id, "skip");
        addNote(map, id, "Left off because you are planning to use formula.");
      });
    }

    if (feed === "breast") {
      map.bottles.planLine = "2–4 small bottles";
      addNote(map, "bottles", "Your count: 2–4 small bottles for later.");
      setStatus(map, "formula", "exclude");
      setStatus(map, "formula-pitcher", "exclude");
    } else if (feed === "formula") {
      map.bottles.planLine = "6–8 bottles";
      addNote(map, "bottles", "Your count: 6–8 bottles.");
      setStatus(map, "formula", "must");
      addNote(map, "formula", "Buy one small can first.");
      setStatus(map, "formula-pitcher", "nice");
    } else {
      map.bottles.planLine = "4–6 bottles";
      addNote(map, "bottles", "Your count: 4–6 bottles.");
      setStatus(map, "formula", "must");
      addNote(map, "formula", "One small can as a backup is enough while you see how feeding goes.");
      setStatus(map, "formula-pitcher", "exclude");
    }
    setStatus(map, "bottles", "must");

    if (cold) {
      addNote(map, "clothing-0-3", "Cold-season baby: favor footed sleepers, and include the hats in this count.");
      addNote(map, "sleep-sacks", "Choose a warmer TOG.");
      setStatus(map, "car-seat-cover", "must");
      setStatus(map, "humidifier", "must");
      setStatus(map, "sun-shade", "exclude");
      setStatus(map, "fan", "exclude");
    } else {
      addNote(map, "clothing-0-3", "Warm-season baby: favor short-sleeve bodysuits and a lighter sleep sack.");
      addNote(map, "sleep-sacks", "Choose a light TOG.");
      setStatus(map, "sun-shade", "must");
      setStatus(map, "fan", "must");
      setStatus(map, "car-seat-cover", "exclude");
    }

    if (move === "car") {
      addNote(map, "car-seat", "Pair it with a compatible stroller. That travel system is the must-have setup.");
      addNote(map, "stroller", "Choose one that works with your infant car seat.");
    } else if (move === "walk") {
      setStatus(map, "carrier", "must");
      addNote(map, "carrier", "Moved up to must-have because you are mostly on foot or transit.");
      addNote(map, "stroller", "Prioritize good suspension and a large basket.");
      addNote(map, "car-seat", "You still need a car seat for the ride home from the hospital, even if you mostly walk or take transit. Ask the hospital what they require.");
    } else if (move === "mix") {
      setStatus(map, "carrier", "must");
      addNote(map, "carrier", "Must-have alongside the travel system.");
      addNote(map, "stroller", "Travel system for the car, carrier for the rest.");
    } else {
      setStatus(map, "compact-stroller", "must");
      setStatus(map, "play-yard", "must");
      addNote(map, "compact-stroller", "Added because you travel or fly often.");
      addNote(map, "play-yard", "Added as your travel crib. Ask the airline about car seat rules before you fly.");
      addNote(map, "car-seat", "Ask the airline what they allow before you fly with a car seat.");
    }

    if (care === "out") {
      addNote(map, "bottles", "Add extras that can stay at daycare.");
      setStatus(map, "labels", "must");
      setStatus(map, "cooler-bag", "must");
      if (nursing) {
        setStatus(map, "pump-bag", "must");
        setStatus(map, "pump-parts", "must");
      }
    }

    items.forEach(function (item) {
      item.quantityText = quantityText(item, answers.laundry);
      if (item.quantityText) {
        item.notes.push(answers.laundry === "low"
          ? "Quantities are the high end of the range, because you want to do laundry less often."
          : "Quantities are the low end of the range, for laundry every 2–3 days.");
      }
      if (item.caution && item.status !== "exclude" && item.status !== "skip") {
        item.notes.push("Buy new, or only from someone whose history you trust.");
      }
      if (tier === "budget" && item.big && (item.status === "must" || item.status === "nice" || item.status === "wait")) {
        item.notes.push(quiz.secondhandNote);
      }
      item.pick = pickFor(item, tier);
      item.linkLabel = resolveLink(item, products);
    });

    var owned = [];
    if (answers.first === "no") {
      items.forEach(function (item) {
        if (item.big && (item.status === "must" || item.status === "nice" || item.status === "wait")) {
          owned.push(item);
          item.status = "owned";
        }
      });
    }

    function group(status) {
      return items.filter(function (item) { return item.status === status; });
    }

    var mustItems = group("must");
    var skipItems = group("skip");
    var banners = [];
    if (tier === "budget") banners.push(quiz.secondhandNote);
    if (warm) banners.push("Sunscreen isn't recommended before 6 months, so stick to shade and clothing.");
    if (cold) banners.push("For cold weather, use a cover that goes over the car seat rather than a bulky snowsuit under the harness.");
    if (space === "small") banners.push("Small-space plan: a bassinet, a mini or compact crib, and a play yard. Skip the standalone changing table.");

    return {
      title: "Your Must-Have List (" + TIER_LABEL[tier] + " · " + SPACE_LABEL[space] + " · " + FEED_LABEL[feed] + ")",
      mustCount: mustItems.length,
      skipCount: skipItems.length,
      must: mustItems,
      nice: group("nice"),
      wait: group("wait"),
      skip: skipItems,
      unsafe: skipItems.filter(function (item) { return item.unsafe; }),
      hidden: skipItems.filter(function (item) { return !item.unsafe; }),
      owned: owned,
      first48: answers.first === "yes" ? quiz.first48.slice() : null,
      first48Title: quiz.first48Title,
      first48Intro: quiz.first48Intro,
      banners: banners
    };
  }

  return {
    buildPlan: buildPlan,
    pickFor: pickFor,
    labels: { tier: TIER_LABEL, space: SPACE_LABEL, feed: FEED_LABEL }
  };
});
