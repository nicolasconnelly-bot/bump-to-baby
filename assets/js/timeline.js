/* Due-date highlighting. Week windows are 7-day blocks from the due date. */
(function (root, factory) {
  var api = factory();
  root.BumpTimeline = api;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { api.mount(document); });
    } else {
      api.mount(document);
    }
  }
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  var STORAGE_KEY = "btb-due";

  function parseISODate(value) {
    var parts = String(value || "").split("-");
    if (parts.length !== 3) return null;
    var year = Number(parts[0]);
    var month = Number(parts[1]);
    var day = Number(parts[2]);
    if (!year || !month || !day) return null;
    var date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
    return date;
  }

  function toISO(date) {
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return date.getFullYear() + "-" + month + "-" + day;
  }

  function todayISO() {
    return toISO(new Date());
  }

  function addDays(iso, days) {
    var date = parseISODate(iso);
    if (!date) return "";
    date.setDate(date.getDate() + days);
    return toISO(date);
  }

  function diffDays(dueISO, today) {
    var due = parseISODate(dueISO);
    var start = parseISODate(today);
    if (!due || !start) return null;
    return Math.round((due.getTime() - start.getTime()) / 86400000);
  }

  function weekForDueDate(dueISO, today) {
    var days = diffDays(dueISO, today || todayISO());
    if (days === null) return null;
    if (days >= 196) {
      return { id: "w-28", early: true, past: false, diffDays: days };
    }
    if (days >= 0) {
      return { id: "w-" + (Math.floor(days / 7) + 1), early: false, past: false, diffDays: days };
    }
    var daysAfter = -days;
    if (daysAfter > 28) {
      return { id: "w-plus-4", early: false, past: true, diffDays: days };
    }
    return { id: "w-plus-" + (Math.floor((daysAfter - 1) / 7) + 1), early: false, past: false, diffDays: days };
  }

  function rangeForOffset(dueISO, offset) {
    var value = Number(offset);
    if (!parseISODate(dueISO) || !value) return null;
    if (value < 0) {
      var weeksBefore = -value;
      return {
        start: addDays(dueISO, -(weeksBefore * 7 - 1)),
        end: addDays(dueISO, -(weeksBefore - 1) * 7)
      };
    }
    return {
      start: addDays(dueISO, (value - 1) * 7 + 1),
      end: addDays(dueISO, value * 7)
    };
  }

  function formatPretty(iso) {
    var date = parseISODate(iso);
    if (!date) return "";
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function codeFromId(id) {
    if (!id) return "";
    if (id.indexOf("w-plus-") === 0) return "W+" + id.slice("w-plus-".length);
    return id.replace("w-", "W-").toUpperCase().replace("W-", "W-");
  }

  function readStoredDue() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "";
    } catch (error) {
      return "";
    }
  }

  function storeDue(value) {
    try {
      if (value) localStorage.setItem(STORAGE_KEY, value);
    } catch (error) {
      /* private mode */
    }
  }

  function basePath() {
    var meta = document.querySelector('meta[name="btb-base"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function mount(doc) {
    var params = new URLSearchParams(location.search);
    var fromQuery = params.get("due") || "";
    var due = parseISODate(fromQuery) ? fromQuery : readStoredDue();
    if (parseISODate(due)) storeDue(due);

    doc.querySelectorAll('input[type="date"][name="due"]').forEach(function (input) {
      if (!input.value && parseISODate(due)) input.value = due;
    });

    var result = parseISODate(due) ? weekForDueDate(due, todayISO()) : null;
    var index = doc.querySelector("[data-timeline-index]");
    if (index) renderIndex(index, due, result);
    var article = doc.querySelector("[data-week-id]");
    if (article) renderWeek(article, due, result);
  }

  function renderIndex(index, due, result) {
    var box = index.querySelector("[data-week-result]");
    if (box && result) {
      var current = index.querySelector('[data-week-id="' + result.id + '"]');
      var title = current ? current.getAttribute("data-week-title") : result.id;
      var href = current ? current.getAttribute("data-week-href") : "#";
      var message;
      if (result.early) {
        message = "You are more than 28 weeks out. Start with W-28. Nothing needs buying yet.";
      } else if (result.past) {
        message = "You are past the last note in this timeline. The final page is still the most recent one.";
      } else {
        message = "This is your week.";
      }
      box.hidden = false;
      box.innerHTML = "";
      var heading = document.createElement("h2");
      heading.textContent = codeFromId(result.id) + ": " + title;
      var paragraph = document.createElement("p");
      paragraph.textContent = message;
      var link = document.createElement("a");
      link.className = "button";
      link.href = href;
      link.textContent = "Read " + codeFromId(result.id);
      box.appendChild(heading);
      box.appendChild(paragraph);
      box.appendChild(link);
      if (current) current.classList.add("is-current");
    }

    if (!parseISODate(due)) return;
    index.querySelectorAll("[data-offset]").forEach(function (row) {
      var range = rangeForOffset(due, row.getAttribute("data-offset"));
      var slot = row.querySelector("[data-range]");
      if (!range || !slot) return;
      slot.hidden = false;
      slot.textContent = formatPretty(range.start) + " – " + formatPretty(range.end);
    });
  }

  function renderWeek(article, due, result) {
    var box = article.querySelector("[data-week-banner]");
    if (!box || !result) return;
    var id = article.getAttribute("data-week-id");
    var offset = article.getAttribute("data-offset");
    var range = rangeForOffset(due, offset);
    box.hidden = false;
    box.innerHTML = "";
    var paragraph = document.createElement("p");
    if (range) {
      paragraph.textContent = "For your due date, this page covers " + formatPretty(range.start) + " through " + formatPretty(range.end) + ". ";
    }
    if (result.id === id && !result.early && !result.past) {
      paragraph.appendChild(document.createTextNode("This is your current week."));
    } else {
      var link = document.createElement("a");
      link.href = basePath() + "/timeline/" + result.id + "/?due=" + encodeURIComponent(due);
      link.textContent = "Your current week is " + codeFromId(result.id);
      paragraph.appendChild(link);
      paragraph.appendChild(document.createTextNode("."));
    }
    box.appendChild(paragraph);
  }

  return {
    parseISODate: parseISODate,
    todayISO: todayISO,
    weekForDueDate: weekForDueDate,
    rangeForOffset: rangeForOffset,
    formatPretty: formatPretty,
    mount: mount,
    storageKey: STORAGE_KEY
  };
});
