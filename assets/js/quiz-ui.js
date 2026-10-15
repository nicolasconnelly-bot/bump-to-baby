(function () {
  "use strict";

  var app = document.querySelector("#quiz-app");
  if (!app || !window.BumpQuiz) return;

  var base = (document.querySelector('meta[name="btb-base"]') || {}).content || "";
  var state = { index: 0, answers: {}, quiz: null, products: null };

  function el(tag, className) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    return node;
  }

  function showError(message) {
    app.innerHTML = "";
    var box = el("p", "callout");
    box.textContent = message;
    app.appendChild(box);
  }

  function optionByValue(question, value) {
    for (var i = 0; i < question.options.length; i += 1) {
      if (question.options[i].value === value) return question.options[i];
    }
    return null;
  }

  function readQuery() {
    var params = new URLSearchParams(location.search);
    if (!state.quiz) return null;
    var answers = {};
    for (var i = 0; i < state.quiz.questions.length; i += 1) {
      var question = state.quiz.questions[i];
      var value = params.get(question.id);
      if (!optionByValue(question, value)) return null;
      answers[question.id] = value;
    }
    return answers;
  }

  function renderQuestion() {
    var questions = state.quiz.questions;
    var question = questions[state.index];
    app.innerHTML = "";

    var progress = el("p", "quiz-progress");
    progress.textContent = "Question " + (state.index + 1) + " of " + questions.length;

    var bar = el("div", "progress");
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-valuemin", "1");
    bar.setAttribute("aria-valuemax", String(questions.length));
    bar.setAttribute("aria-valuenow", String(state.index + 1));
    bar.setAttribute("aria-valuetext", progress.textContent);
    var fill = el("span", "progress-fill");
    fill.style.width = ((state.index + 1) / questions.length * 100) + "%";
    bar.appendChild(fill);

    var form = el("form", "quiz-form");
    form.noValidate = true;
    var fieldset = document.createElement("fieldset");
    var legend = document.createElement("legend");
    legend.textContent = question.prompt;
    fieldset.appendChild(legend);

    question.options.forEach(function (option, optionIndex) {
      var label = el("label", "option");
      var input = document.createElement("input");
      input.type = "radio";
      input.name = "answer";
      input.value = option.value;
      input.id = "option-" + optionIndex;
      if (state.answers[question.id] === option.value) {
        input.checked = true;
        label.classList.add("is-selected");
      }
      input.addEventListener("change", function () {
        fieldset.querySelectorAll(".option").forEach(function (node) {
          node.classList.remove("is-selected");
        });
        label.classList.add("is-selected");
        var alert = form.querySelector("[data-quiz-alert]");
        if (alert) alert.textContent = "";
      });
      var text = el("span", "option-label");
      text.textContent = option.label;
      label.appendChild(input);
      label.appendChild(text);
      fieldset.appendChild(label);
    });

    var alert = el("p", "form-alert");
    alert.setAttribute("data-quiz-alert", "");
    alert.setAttribute("role", "alert");

    var actions = el("div", "quiz-actions");
    if (state.index > 0) {
      var back = el("button", "button button-secondary");
      back.type = "button";
      back.textContent = "Back";
      back.addEventListener("click", function () {
        state.index -= 1;
        renderQuestion();
      });
      actions.appendChild(back);
    }
    var next = el("button", "button");
    next.type = "submit";
    next.textContent = state.index === questions.length - 1 ? "See my list" : "Next";
    actions.appendChild(next);

    form.appendChild(fieldset);
    form.appendChild(alert);
    form.appendChild(actions);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var selected = form.querySelector("input[name=answer]:checked");
      if (!selected) {
        alert.textContent = "Choose an answer to continue.";
        return;
      }
      state.answers[question.id] = selected.value;
      if (state.index === questions.length - 1) {
        var query = new URLSearchParams(state.answers);
        history.pushState(null, "", "?" + query.toString());
        renderResults(state.answers);
        return;
      }
      state.index += 1;
      renderQuestion();
      var legendNode = app.querySelector("legend");
      if (legendNode) legendNode.focus();
    });

    app.appendChild(progress);
    app.appendChild(bar);
    app.appendChild(form);
    legend.tabIndex = -1;
  }

  function productMedia(item) {
    if (item.unsafe || !item.link) return null;
    if (item.image) {
      var img = document.createElement("img");
      img.className = "item-thumb";
      img.src = item.image;
      img.alt = "";
      img.width = 72;
      img.height = 72;
      img.loading = "lazy";
      return img;
    }
    var mark = el("span", "item-placeholder");
    mark.setAttribute("data-category", item.category || "gear");
    mark.setAttribute("aria-hidden", "true");
    return mark;
  }

  function fillCard(card, item, fill) {
    var media = productMedia(item);
    var copy = media ? el("div", "item-copy") : card;
    fill(copy);
    if (media) {
      card.classList.add("has-media");
      var frame = el("div", "item-media");
      frame.appendChild(media);
      card.appendChild(frame);
      card.appendChild(copy);
    }
  }

  function itemCard(item) {
    var card = el("article", "item-card");
    card.id = "result-" + item.id;
    fillCard(card, item, function (copy) {
      var header = el("div", "item-card-head");
      var title = el("h3");
      title.textContent = item.name;
      header.appendChild(title);
      if (item.badges.length) {
        item.badges.forEach(function (badge) {
          var pill = el("p", "badge badge-priority");
          pill.textContent = badge;
          header.appendChild(pill);
        });
      }
      copy.appendChild(header);
      if (item.planLine) {
        var plan = el("p", "plan-line");
        plan.textContent = "Your count: " + item.planLine;
        copy.appendChild(plan);
      }
      if (item.quantityText) {
        var qty = el("p", "plan-line");
        qty.textContent = item.quantityText;
        copy.appendChild(qty);
      }
      if (item.pick) {
        var pick = el("p", "pick");
        pick.textContent = "Example pick: " + item.pick;
        copy.appendChild(pick);
      }
      item.notes.forEach(function (line) {
        var note = el("p", "item-note");
        note.textContent = line;
        copy.appendChild(note);
      });
      copy.appendChild(linkLine(item));
    });
    return card;
  }

  function linkLine(item) {
    var line = el("p", "affiliate");
    if (!item.linkLabel) {
      line.textContent = item.unsafe
        ? "No product link. This item is unsafe for sleep, so it is not for sale here."
        : "No product link. This is a task, not a store listing.";
      return line;
    }
    if (item.linkLabel.indexOf("{{") !== -1) {
      line.appendChild(document.createTextNode("Link placeholder: "));
      var code = el("code");
      code.setAttribute("translate", "no");
      code.textContent = item.linkLabel;
      line.appendChild(code);
      return line;
    }
    var anchor = document.createElement("a");
    anchor.href = item.linkLabel;
    anchor.rel = "sponsored nofollow noopener";
    anchor.target = "_blank";
    anchor.textContent = "Product link for " + item.name;
    line.appendChild(anchor);
    return line;
  }

  function sectionFor(title, intro, items, className) {
    if (!items.length) return null;
    var section = el("section", className || "result-section");
    var heading = el("h2");
    heading.textContent = title;
    section.appendChild(heading);
    if (intro) {
      var lead = el("p");
      lead.textContent = intro;
      section.appendChild(lead);
    }
    state.products.categories.forEach(function (category) {
      var matching = items.filter(function (item) { return item.category === category.id; });
      if (!matching.length) return;
      var block = el("div", "result-category");
      var sub = el("h3");
      sub.textContent = category.name;
      block.appendChild(sub);
      var list = el("div", "card-stack");
      matching.forEach(function (item) { list.appendChild(itemCard(item)); });
      block.appendChild(list);
      section.appendChild(block);
    });
    return section;
  }

  function renderResults(answers) {
    var plan;
    try {
      plan = window.BumpQuiz.buildPlan(answers, state.products, state.quiz);
    } catch (error) {
      showError("Those answers could not build a list. Start the quiz again.");
      return;
    }

    app.innerHTML = "";
    document.title = plan.title + " · Bump to Baby";
    var intro = document.querySelector(".quiz-intro");
    if (intro) intro.hidden = true;

    var summary = el("header", "results-summary");
    var heading = el("h1");
    heading.id = "results-title";
    heading.tabIndex = -1;
    heading.textContent = plan.title;
    var count = el("p", "results-count");
    var noun = plan.mustCount === 1 ? "item" : "items";
    var skipNoun = plan.skipCount === 1 ? "thing" : "things";
    count.textContent = plan.mustCount + " " + noun + ". We've hidden " + plan.skipCount + " " + skipNoun + " you can skip.";
    summary.appendChild(heading);
    summary.appendChild(count);
    plan.banners.forEach(function (banner) {
      var note = el("p", "callout");
      note.textContent = banner;
      summary.appendChild(note);
    });
    var safety = el("p", "callout callout-quiet");
    safety.appendChild(document.createTextNode("General gear guidance only. Safe sleep, car seats, and medicine are not personal advice. "));
    var safetyLink = document.createElement("a");
    safetyLink.href = base + "/disclaimer/";
    safetyLink.textContent = "Read the disclaimer";
    safety.appendChild(safetyLink);
    safety.appendChild(document.createTextNode("."));
    summary.appendChild(safety);

    var actions = el("div", "quiz-actions no-print");
    var retake = el("button", "button button-secondary");
    retake.type = "button";
    retake.textContent = "Retake the quiz";
    retake.addEventListener("click", function () {
      state.index = 0;
      state.answers = {};
      history.pushState(null, "", location.pathname);
      document.title = "Registry quiz · Bump to Baby";
      var intro = document.querySelector(".quiz-intro");
      if (intro) intro.hidden = false;
      renderQuestion();
    });
    var print = el("button", "button button-secondary");
    print.type = "button";
    print.textContent = "Print this list";
    print.addEventListener("click", function () { window.print(); });
    var newsletterJump = document.createElement("a");
    newsletterJump.className = "button";
    newsletterJump.href = "#newsletter";
    newsletterJump.textContent = "Get the week-by-week plan";
    actions.appendChild(newsletterJump);
    actions.appendChild(print);
    actions.appendChild(retake);
    summary.appendChild(actions);
    app.appendChild(summary);

    var must = sectionFor("Must-haves", "Buy or register for these. Example picks match the budget style you chose.", plan.must);
    if (must) app.appendChild(must);

    if (plan.first48) {
      var first = el("section", "result-section");
      var firstHeading = el("h2");
      firstHeading.textContent = plan.first48Title;
      var firstIntro = el("p");
      firstIntro.textContent = plan.first48Intro;
      var list = document.createElement("ul");
      list.className = "check-list";
      plan.first48.forEach(function (line) {
        var item = document.createElement("li");
        item.textContent = line;
        list.appendChild(item);
      });
      first.appendChild(firstHeading);
      first.appendChild(firstIntro);
      first.appendChild(list);
      app.appendChild(first);
    }

    if (plan.owned.length) {
      var owned = el("section", "result-section");
      var ownedHeading = el("h2");
      ownedHeading.textContent = "Check what you already own";
      var ownedIntro = el("p");
      ownedIntro.textContent = "Big gear is off the shopping list because you already have some. Check expiration dates, recalls, and crib standards before you reuse it.";
      owned.appendChild(ownedHeading);
      owned.appendChild(ownedIntro);
      plan.owned.forEach(function (item) {
        var card = el("article", "item-card");
        fillCard(card, item, function (copy) {
          var title = el("h3");
          title.textContent = item.name;
          var note = el("p", "item-note");
          note.textContent = item.ownedNote;
          copy.appendChild(title);
          copy.appendChild(note);
          if (item.pick) {
            var pick = el("p", "pick");
            pick.textContent = "If you replace it, an example pick is " + item.pick + ".";
            copy.appendChild(pick);
          }
        });
        owned.appendChild(card);
      });
      app.appendChild(owned);
    }

    var nice = sectionFor("Nice-to-haves", "Worth it for some families. Fine to leave for gifts or later.", plan.nice);
    if (nice) app.appendChild(nice);
    var wait = sectionFor("Can wait", "Real items, wrong time. The timeline says when they come back.", plan.wait);
    if (wait) app.appendChild(wait);

    if (plan.unsafe.length) {
      var unsafe = el("section", "result-section unsafe-section");
      var unsafeHeading = el("h2");
      unsafeHeading.textContent = "Do not buy these";
      var unsafeIntro = el("p");
      unsafeIntro.textContent = "These are hidden from the must-have list because they are unsafe for sleep, not because they are optional.";
      unsafe.appendChild(unsafeHeading);
      unsafe.appendChild(unsafeIntro);
      plan.unsafe.forEach(function (item) {
        var card = el("article", "item-card");
        var title = el("h3");
        title.textContent = item.name;
        card.appendChild(title);
        item.notes.forEach(function (line) {
          var note = el("p", "item-note");
          note.textContent = line;
          card.appendChild(note);
        });
        unsafe.appendChild(card);
      });
      app.appendChild(unsafe);
    }

    if (plan.hidden.length) {
      var details = document.createElement("details");
      details.className = "skip-details";
      var summary = document.createElement("summary");
      summary.textContent = "Show the " + plan.hidden.length + " other things we hid";
      details.appendChild(summary);
      var hiddenWrap = el("div", "card-stack");
      plan.hidden.forEach(function (item) {
        var card = el("article", "item-card");
        fillCard(card, item, function (copy) {
          var title = el("h3");
          title.textContent = item.name;
          copy.appendChild(title);
          item.notes.forEach(function (line) {
            var note = el("p", "item-note");
            note.textContent = line;
            copy.appendChild(note);
          });
        });
        hiddenWrap.appendChild(card);
      });
      details.appendChild(hiddenWrap);
      app.appendChild(details);
    }

    var closer = el("p", "results-closer");
    closer.textContent = "Want this as a week-by-week plan? Enter your due date and email and we'll tell you what to buy each week, and what can wait.";
    var closerLink = document.createElement("a");
    closerLink.href = "#newsletter";
    closerLink.textContent = " Go to the newsletter signup.";
    closer.appendChild(closerLink);
    app.appendChild(closer);

    heading.focus();
  }

  Promise.all([
    fetch(base + "/data/products.json").then(function (response) {
      if (!response.ok) throw new Error("products");
      return response.json();
    }),
    fetch(base + "/data/quiz.json").then(function (response) {
      if (!response.ok) throw new Error("quiz");
      return response.json();
    })
  ]).then(function (payload) {
    state.products = payload[0];
    state.quiz = payload[1];
    var preset = readQuery();
    if (preset) {
      state.answers = preset;
      renderResults(preset);
      return;
    }
    renderQuestion();
  }).catch(function () {
    showError("The quiz data did not load. You can still read the gear list and the week-by-week timeline.");
  });

  window.addEventListener("popstate", function () {
    if (!state.quiz) return;
    var preset = readQuery();
    if (preset) renderResults(preset);
    else {
      state.index = 0;
      renderQuestion();
    }
  });
})();
