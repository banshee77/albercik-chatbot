// ALBERTOS public website — chat widget
// (feature 006-public-chat-widget, research.md / contracts/
// chat-widget-client-contract.md).
//
// Progressive enhancement over the static, JS-gated launcher/panel markup
// already sent by base.html: without this script the launcher stays
// display:none (site.css's `.js`-scoped rules) and the panel stays
// [hidden] — there is nothing dead-but-visible left behind if this file
// fails to load. Every message is inserted with `.textContent`, never
// `.innerHTML` — the assistant's answer text is always treated as
// untrusted content (FR-021/FR-022). Retrieval source metadata (present
// in the backend's response for future admin/observability tooling) is
// never rendered by this public widget for any outcome (feature
// 007-conversational-chat-ux, User Story 5).

(function () {
  "use strict";

  var STORAGE_KEY = "albertos-chat-history";
  var MAX_STORED_MESSAGES = 200;

  var launcher = document.getElementById("chat-launcher");
  var panel = document.getElementById("chat-panel");
  var closeButton = document.getElementById("chat-close");
  var messagesEl = document.getElementById("chat-messages");
  var statusEl = document.getElementById("chat-status");
  var form = document.getElementById("chat-form");
  var input = document.getElementById("chat-input");
  var sendButton = document.getElementById("chat-send");

  if (!launcher || !panel || !closeButton || !messagesEl || !statusEl || !form || !input || !sendButton) {
    return;
  }

  // --- sessionStorage-backed history (data-model.md's ChatSession shape) ---
  // A read/parse/write failure (corrupted content, a private-browsing
  // quota error) is always treated as "start with an empty session," never
  // a fatal error for the rest of the page.

  function loadHistory() {
    try {
      var raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (!raw) {
        return [];
      }
      var parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed;
    } catch (error) {
      return [];
    }
  }

  function saveHistory(history) {
    try {
      var trimmed = history.slice(-MAX_STORED_MESSAGES);
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    } catch (error) {
      // Storage unavailable/full — the visible conversation still works
      // for the rest of this page load, it just won't survive navigation.
    }
  }

  var history = loadHistory();

  // --- Rendering (textContent only — never innerHTML, FR-021/FR-022) ---

  function renderMessage(role, text) {
    var wrapper = document.createElement("div");
    wrapper.className = "chat-message chat-message--" + role;

    var textEl = document.createElement("p");
    textEl.textContent = text;
    wrapper.appendChild(textEl);

    // Decorative "Asystent Albertos" avatar, assistant messages only
    // (feature 007-conversational-chat-ux, User Story 4). A CSS
    // background-image on a plain <span> — never an <img> — so a failed
    // asset load degrades to the CSS rule's own background-color, never a
    // broken-image glyph; aria-hidden keeps it out of the accessibility
    // tree, since the message text alone already conveys who is speaking.
    var appended = wrapper;
    if (role === "assistant") {
      var avatarEl = document.createElement("span");
      avatarEl.className = "chat-avatar";
      avatarEl.setAttribute("aria-hidden", "true");

      var row = document.createElement("div");
      row.className = "chat-message-row";
      row.appendChild(avatarEl);
      row.appendChild(wrapper);
      appended = row;
    }

    messagesEl.appendChild(appended);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return wrapper;
  }

  function appendAndPersist(role, text) {
    renderMessage(role, text);
    history.push({ role: role, text: text });
    saveHistory(history);
  }

  history.forEach(function (entry) {
    renderMessage(entry.role, entry.text);
  });

  // --- Open / close, with WAI-ARIA "Dialog (Modal)" focus management
  // (research.md §5; FR-030/FR-031) ---

  var panelTitle = document.getElementById("chat-panel-title");

  function getFocusableElements() {
    var selector = 'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';
    return Array.prototype.slice.call(panel.querySelectorAll(selector));
  }

  function openPanel() {
    panel.hidden = false;
    panel.classList.add("is-open");
    launcher.setAttribute("aria-expanded", "true");
    if (panelTitle) {
      panelTitle.focus();
    } else {
      input.focus();
    }
  }

  function closePanel() {
    panel.hidden = true;
    panel.classList.remove("is-open");
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  }

  launcher.addEventListener("click", function () {
    if (panel.hidden) {
      openPanel();
    } else {
      closePanel();
    }
  });

  closeButton.addEventListener("click", closePanel);

  panel.addEventListener("keydown", function (event) {
    if (event.key === "Escape" || event.key === "Esc") {
      closePanel();
      return;
    }

    if (event.key !== "Tab") {
      return;
    }

    // Focus trap: Tab/Shift+Tab wraps within the panel's focusable
    // elements while it is open, so keyboard focus never silently
    // escapes to the page underneath.
    var focusable = getFocusableElements();
    if (focusable.length === 0) {
      return;
    }
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  // --- Ask a question ---
  // Every submission is sent to the existing chat endpoint as an
  // independent question — the only field ever sent is `question` (FR-007/
  // FR-008; contracts/chat-widget-client-contract.md). This switch grows
  // across User Stories 2-3 to cover insufficient_information/out_of_scope
  // (US2) and 429/503/network/malformed-response fallbacks (US3).

  var CHAT_ENDPOINT = "/api/v1/chat";
  var requestInFlight = false;

  function setBusy(busy) {
    requestInFlight = busy;
    sendButton.disabled = busy;
    input.disabled = busy;
  }

  function isChatResponseShape(body) {
    return (
      !!body && typeof body.outcome === "string" && typeof body.answer === "string"
    );
  }

  // A single shared fallback, per FR-018a (Clarifications, 2026-08-19):
  // a malformed/unparseable body, a network failure, and any HTTP status
  // this feature has no specific handling for (200/429/503) all reach
  // this one function — no backend-internal limit (e.g. the configured
  // max question length behind a hypothetical 422) is ever hardcoded
  // client-side to try to avoid triggering it.
  var GENERIC_FALLBACK_MESSAGE = "Coś poszło nie tak. Spróbuj zadać pytanie ponownie za chwilę.";
  var RATE_LIMIT_MESSAGE = "Zbyt wiele pytań w krótkim czasie. Spróbuj ponownie za chwilę.";

  function showFallbackMessage() {
    appendAndPersist("assistant", GENERIC_FALLBACK_MESSAGE);
  }

  function parseRetryAfterSeconds(response) {
    var raw = response.headers.get("Retry-After");
    var seconds = parseInt(raw, 10);
    return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
  }

  function showRateLimitMessage(response) {
    var retryAfterSeconds = parseRetryAfterSeconds(response);
    var message =
      retryAfterSeconds !== null
        ? "Zbyt wiele pytań w krótkim czasie. Spróbuj ponownie za około " +
          retryAfterSeconds +
          " s."
        : RATE_LIMIT_MESSAGE;
    appendAndPersist("assistant", message);
  }

  function handleResponse(response, body) {
    if (response.status === 200 && isChatResponseShape(body)) {
      if (body.outcome === "grounded") {
        appendAndPersist("assistant", body.answer);
        return;
      }
      if (body.outcome === "insufficient_information" || body.outcome === "out_of_scope") {
        appendAndPersist("assistant", body.answer);
        return;
      }
      if (body.outcome === "small_talk") {
        // Deterministic small-talk reply, answered server-side without a
        // retrieval/LLM call (feature 007). Explicit branch required —
        // otherwise this outcome would fall to the generic fallback below.
        appendAndPersist("assistant", body.answer);
        return;
      }
      if (body.outcome === "unavailable") {
        // Not produced by the current backend (which always pairs
        // "unavailable" with a 503), handled defensively all the same.
        appendAndPersist("assistant", body.answer);
        return;
      }
      showFallbackMessage();
      return;
    }

    if (response.status === 429) {
      showRateLimitMessage(response);
      return;
    }

    if (response.status === 503 && isChatResponseShape(body)) {
      // The backend's own 503 body already carries a safe, friendly,
      // Polish "unavailable" answer — reused directly rather than
      // duplicating a second client-authored string (research.md §1).
      appendAndPersist("assistant", body.answer);
      return;
    }

    // A malformed 200/503 body, or any other HTTP status entirely
    // (400/404/413/a hypothetical 422/500/...): the single shared
    // fallback (FR-018a).
    showFallbackMessage();
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var question = input.value.trim();
    if (!question || requestInFlight) {
      return;
    }

    appendAndPersist("user", question);
    input.value = "";
    setBusy(true);
    statusEl.textContent = "Asystent Albertos pisze odpowiedź…";

    fetch(CHAT_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return null;
          })
          .then(function (body) {
            handleResponse(response, body);
          });
      })
      .catch(function () {
        // The fetch itself rejected — a network failure, no response was
        // ever received (FR-018).
        showFallbackMessage();
      })
      .finally(function () {
        statusEl.textContent = "";
        setBusy(false);
      });
  });
})();
