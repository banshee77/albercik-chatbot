// ALBERTOS public website — progressive-enhancement JS
// (feature 005-public-club-website, research.md §1/§2/§8).
//
// Everything here is an enhancement over already-working, server-rendered
// HTML: the mobile menu is plain links even if this file fails to load,
// and the filter forms already work as full-page-reload <form method="get">
// submissions without any of this running (FR-008, SC-008).

(function () {
  "use strict";

  function setUpMobileNav() {
    var toggle = document.getElementById("nav-toggle");
    var nav = document.getElementById("primary-nav");
    if (!toggle || !nav) {
      return;
    }
    toggle.addEventListener("click", function () {
      var isOpen = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  function setUpRevealOnScroll() {
    if (!("IntersectionObserver" in window)) {
      return;
    }
    var targets = document.querySelectorAll("[data-reveal]");
    if (!targets.length) {
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    targets.forEach(function (el) {
      observer.observe(el);
    });
  }

  // Progressive enhancement for a server-rendered filter <form
  // method="get">: intercept submit, fetch the same URL, and swap the
  // named result fragment in place instead of a full navigation. Falls
  // back to the plain form submission (already fully working) on any
  // error.
  function enhanceFilterForm(formId, resultsId) {
    var form = document.getElementById(formId);
    var results = document.getElementById(resultsId);
    if (!form || !results) {
      return;
    }
    form.addEventListener("submit", function (event) {
      var params = new URLSearchParams(new FormData(form));
      var url = form.getAttribute("action") + "?" + params.toString();
      event.preventDefault();
      fetch(url, { headers: { "X-Requested-With": "fetch" } })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("bad response");
          }
          return response.text();
        })
        .then(function (html) {
          var parser = new DOMParser();
          var doc = parser.parseFromString(html, "text/html");
          var next = doc.getElementById(resultsId);
          if (next) {
            results.replaceWith(next);
            window.history.pushState({}, "", url);
          } else {
            form.submit();
          }
        })
        .catch(function () {
          form.submit();
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setUpMobileNav();
    setUpRevealOnScroll();
    enhanceFilterForm("schedule-filter-form", "schedule-results");
    enhanceFilterForm("news-filter-form", "news-results");
  });
})();
