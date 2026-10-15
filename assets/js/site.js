(function () {
  "use strict";

  var toggle = document.querySelector(".nav-toggle");
  var nav = document.querySelector("#site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      nav.classList.toggle("is-open", !open);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        toggle.setAttribute("aria-expanded", "false");
        nav.classList.remove("is-open");
        toggle.focus();
      }
    });
  }

  function storeDue(value) {
    try {
      if (value) localStorage.setItem("btb-due", value);
    } catch (error) {
      /* ignore quota or private mode */
    }
  }

  function readDue() {
    try {
      return localStorage.getItem("btb-due") || "";
    } catch (error) {
      return "";
    }
  }

  var saved = readDue();
  document.querySelectorAll('input[type="date"][name="due"]').forEach(function (input) {
    if (!input.value && saved) input.value = saved;
  });

  document.querySelectorAll("[data-due-redirect]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var due = form.querySelector('input[type="date"][name="due"]');
      if (due && due.value) storeDue(due.value);
    });
  });
})();
