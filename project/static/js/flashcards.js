(() => {
  const readJsonScript = (id) => {
    const script = document.getElementById(id);
    if (!script) return null;
    try {
      return JSON.parse(script.textContent);
    } catch (error) {
      console.error("Invalid JSON in", id, error);
      return null;
    }
  };

  const setupFlipCards = () => {
    document.querySelectorAll("[data-flip-card]").forEach((card) => {
      card.addEventListener("click", (event) => {
        if (event.target.closest("button")) {
          return;
        }
        card.classList.toggle("is-flipped");
      });
    });
  };

  const equalizeCardHeights = () => {
    const grids = document.querySelectorAll(".flashcard-grid");
    grids.forEach((grid) => {
      const cards = grid.querySelectorAll(".flashcard");
      if (!cards.length) return;

      // Reset heights first to measure natural content height
      cards.forEach((card) => {
        const inner = card.querySelector(".flashcard-inner");
        const front = card.querySelector(".flashcard-front");
        const back = card.querySelector(".flashcard-back");
        if (inner) inner.style.height = "";
        if (front) front.style.height = "";
        if (back) {
          back.style.height = "";
          back.style.position = "";
        }
      });

      // Measure the tallest content (both front and back)
      let maxHeight = 0;
      cards.forEach((card) => {
        const front = card.querySelector(".flashcard-front");
        const back = card.querySelector(".flashcard-back");

        // Temporarily show back to measure it
        if (back) {
          back.style.position = "static";
          back.style.transform = "none";
        }

        const frontHeight = front ? front.offsetHeight : 0;
        const backHeight = back ? back.offsetHeight : 0;
        maxHeight = Math.max(maxHeight, frontHeight, backHeight);

        // Restore back positioning
        if (back) {
          back.style.position = "";
          back.style.transform = "";
        }
      });

      // Apply uniform height to all cards
      cards.forEach((card) => {
        const inner = card.querySelector(".flashcard-inner");
        const back = card.querySelector(".flashcard-back");
        if (inner) inner.style.height = `${maxHeight}px`;
        if (back) {
          back.style.height = `${maxHeight}px`;
          back.style.position = "absolute";
        }
      });
    });
  };

  const adjustSingleCardHeight = (card) => {
    if (!card) return;
    const inner = card.querySelector(".flashcard-inner");
    const front = card.querySelector(".flashcard-front");
    const back = card.querySelector(".flashcard-back");
    if (!inner || !front || !back) return;

    inner.style.height = "";
    back.style.height = "";
    back.style.position = "static";
    back.style.transform = "none";

    const frontHeight = front.offsetHeight;
    const backHeight = back.offsetHeight;
    const maxHeight = Math.max(frontHeight, backHeight);

    inner.style.height = `${maxHeight}px`;
    back.style.height = `${maxHeight}px`;
    back.style.position = "absolute";
    back.style.transform = "";
  };

  const escapeHtml = (value) =>
    String(value).replace(/[&<>"']/g, (char) => {
      const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      };
      return map[char] || char;
    });

  const renderMultiline = (el, value) => {
    if (!el) return;
    const safe = escapeHtml(value || "");
    el.innerHTML = safe.replace(/\n/g, "<br>");
  };

  const parseMarkdown = (value) => {
    if (!window.marked || typeof window.marked.parse !== "function") {
      return null;
    }
    return window.marked.parse(value || "", { breaks: true });
  };

  const sanitizeHtml = (html) => {
    if (window.DOMPurify && typeof window.DOMPurify.sanitize === "function") {
      return window.DOMPurify.sanitize(html);
    }
    return null;
  };

  const renderMarkdown = (el, value) => {
    if (!el) return;
    const html = parseMarkdown(value);
    if (!html) {
      renderMultiline(el, value);
      return;
    }
    const safeHtml = sanitizeHtml(html);
    if (safeHtml === null) {
      console.warn("DOMPurify not available; falling back to plain text.");
      renderMultiline(el, value);
      return;
    }
    el.innerHTML = safeHtml;
  };

  const normalizeMarkdown = (value) => {
    const text = String(value || "");
    const lines = text.replace(/\r\n/g, "\n").split("\n");
    while (lines.length && lines[0].trim() === "") lines.shift();
    while (lines.length && lines[lines.length - 1].trim() === "") lines.pop();
    if (!lines.length) return "";
    const indents = lines
      .filter((line) => line.trim() !== "")
      .map((line) => (line.match(/^ */) || [""])[0].length);
    const minIndent = Math.min(...indents);
    if (!minIndent) return lines.join("\n");
    return lines.map((line) => line.slice(minIndent)).join("\n");
  };

  const ensureCodeFence = (value) => {
    const trimmed = normalizeMarkdown(value).trim();
    if (!trimmed) return "```\n```";
    if (trimmed.includes("```")) return trimmed;
    return `\`\`\`\n${trimmed}\n\`\`\``;
  };

  const formatCodeDiffMarkdown = (value) => {
    const trimmed = String(value || "").trim();
    const match = trimmed.match(/^Before:\n([\s\S]*?)\n\nAfter:\n([\s\S]*)$/);
    if (!match) {
      return ensureCodeFence(trimmed);
    }
    const before = match[1].trim();
    const after = match[2].trim();
    return `**Before**\n${ensureCodeFence(before)}\n\n**After**\n${ensureCodeFence(after)}`;
  };

  const formatResponseMarkdown = (card, response) => {
    if (!card || !response) return response || "";
    if (card.type === "command") {
      return ensureCodeFence(response);
    }
    if (card.type === "code_diff") {
      return formatCodeDiffMarkdown(response);
    }
    return response;
  };

  const renderMarkdownBlocks = () => {
    document.querySelectorAll("[data-markdown]").forEach((el) => {
      const raw = normalizeMarkdown(el.textContent || "");
      const cardType = el.dataset.cardType;
      const cardSide = el.dataset.cardSide;
      const isCodeResponse =
        cardSide === "response" &&
        (cardType === "command" || cardType === "code_diff");
      const value = isCodeResponse
        ? formatResponseMarkdown({ type: cardType }, raw)
        : raw;
      renderMarkdown(el, value);
    });
  };

  const setupReviewSession = () => {
    const reviewCard = document.querySelector("[data-review-card]");
    if (!reviewCard) return;

    const cards = readJsonScript("review-cards-data") || [];
    const config = readJsonScript("review-config-data") || {};
    if (!cards.length) return;

    const questionEl = document.getElementById("card-question");
    const answerEl = document.getElementById("card-answer");
    const noteTitleEl = document.getElementById("card-note-title");
    const progressEl = document.getElementById("review-progress");
    const actionsEl = document.getElementById("flashcard-actions");
    const rateUrl = config.rateUrl;
    const toastEl = document.getElementById("flashcard-toast");
    const summaryEl = document.getElementById("review-summary");
    const summaryTextEl = document.getElementById("review-summary-text");
    const summaryStatsEl = document.getElementById("review-summary-stats");
    const summaryWeakEl = document.getElementById("review-summary-weak");

    let currentIndex = 0;
    let cardStart = performance.now();
    let completedCount = 0;
    let lapseCount = 0;
    let graduatedCount = 0;
    const tagLapses = {};
    let isSubmitting = false;
    let pendingAttempt = null;
    let staleQueue = false;
    const saveError = document.getElementById("review-save-error");
    const saveRetry = document.getElementById("review-save-retry");
    const reloadLink = document.getElementById("review-reload");
    const sessionId = crypto.randomUUID();

    const updateProgress = () => {
      if (progressEl) {
        progressEl.textContent = `Card ${currentIndex + 1} of ${cards.length}`;
      }
    };

    const lockActions = () => {
      actionsEl?.classList.add("is-disabled");
    };

    const unlockActions = () => {
      if (isSubmitting || pendingAttempt || staleQueue) return;
      actionsEl?.classList.remove("is-disabled");
    };

    const showToast = (message) => {
      if (!toastEl || !message) return;
      toastEl.textContent = message;
      toastEl.classList.add("is-visible");
      window.setTimeout(() => toastEl.classList.remove("is-visible"), 2000);
    };

    const buildRateUrl = () => {
      if (!rateUrl) return null;
      const params = new URLSearchParams(window.location.search);
      if (params.get("debug") !== "1") {
        return rateUrl;
      }
      const separator = rateUrl.includes("?") ? "&" : "?";
      return `${rateUrl}${separator}debug=1`;
    };

    const rateUrlWithDebug = buildRateUrl();

    const renderCard = () => {
      const card = cards[currentIndex];
      if (!card) return;

      reviewCard.classList.remove("is-flipped");
      lockActions();

      const prompt = normalizeMarkdown(card.prompt ?? card.question ?? "");
      const response = normalizeMarkdown(card.response ?? card.answer ?? "");
      renderMarkdown(questionEl, prompt);
      const responseMarkdown = formatResponseMarkdown(card, response);
      renderMarkdown(answerEl, responseMarkdown);
      noteTitleEl.textContent = card.note_title
        ? `From ${card.note_title}`
        : "";
      updateProgress();
      cardStart = performance.now();
      requestAnimationFrame(() => adjustSingleCardHeight(reviewCard));
    };

    const sendRating = async (cardId, rating) => {
      if (!rateUrlWithDebug) return;
      if (!pendingAttempt) {
        pendingAttempt = {
          card_id: cardId, rating,
          response_ms: Math.min(86400000, Math.max(0, Math.round(performance.now() - cardStart))),
          session_id: sessionId, request_id: crypto.randomUUID(),
          expected_revision: cards[currentIndex].progress_revision,
        };
      }
      if (saveError) saveError.hidden = true;
      if (saveRetry) saveRetry.hidden = true;
      try {
        const response = await fetch(rateUrlWithDebug, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(pendingAttempt),
          signal: AbortSignal.timeout(30000),
        });
        if (!response.ok) {
          if ([400, 401, 403, 404, 409].includes(response.status)) {
            staleQueue = true;
            pendingAttempt = null;
            if (saveError) {
              saveError.textContent = response.status === 409
                ? "This card changed elsewhere. Load a fresh queue."
                : "This rating could not be saved. Sign in if needed and load a fresh queue.";
              saveError.hidden = false;
            }
            if (reloadLink) reloadLink.hidden = false;
            return null;
          }
          throw new Error("Rating confirmation unavailable");
        }
        const result = await response.json();
        pendingAttempt = null;
        return result;
      } catch {
        // A missing response is not a failed write. Check the durable receipt,
        // then allow only an explicit replay of the identical attempt.
        try {
          const status = await fetch(config.receiptUrl.replace("REQUEST_ID", pendingAttempt.request_id), {
            cache: "no-store", signal: AbortSignal.timeout(10000),
          });
          if (status.ok) {
            const { receipt } = await status.json();
            if (receipt) {
              pendingAttempt = null;
              return receipt;
            }
          }
        } catch { /* Keep the attempted payload frozen. */ }
        if (saveError) {
          saveError.textContent = "Save confirmation is unavailable. Retry the same rating when connected; it will only be applied once.";
          saveError.hidden = false;
        }
        if (saveRetry) saveRetry.hidden = false;
          return null;
      }
    };

    reviewCard.addEventListener("click", () => {
      if (reviewCard.classList.contains("is-flipped")) {
        unlockActions();
      } else {
        lockActions();
      }
    });

    const submitRating = (rating) => {
      if (isSubmitting || staleQueue) return;
      const card = cards[currentIndex];
      if (!card) return;

      isSubmitting = true;
      lockActions();

      sendRating(card.card_id, rating).then((data) => {
        isSubmitting = false;
        if (!data) return;
        if (data?.next_review_display) {
          showToast(data.next_review_display);
          if (data.next_review_display.startsWith("Graduated:")) {
            graduatedCount += 1;
          }
        }
        if (data?.debug) {
          console.log("Scheduler debug", data.debug);
        }
        if (data.rating === 0) {
          lapseCount += 1;
          const tags = card.tags || [];
          tags.forEach((tag) => {
            tagLapses[tag] = (tagLapses[tag] || 0) + 1;
          });
        }
        completedCount += 1;
        currentIndex += 1;
        if (currentIndex >= cards.length) {
          reviewCard.setAttribute("hidden", "true");
          actionsEl?.setAttribute("hidden", "true");
          if (summaryEl) {
            summaryEl.hidden = false;
          }
          if (summaryTextEl) {
            summaryTextEl.textContent = `You reviewed ${completedCount} card${completedCount === 1 ? "" : "s"}.`;
          }
          if (summaryStatsEl) {
            summaryStatsEl.textContent = `Reviewed: ${completedCount} | Lapses: ${lapseCount} | Graduated: ${graduatedCount}`;
          }
          if (summaryWeakEl) {
            const sortedTags = Object.entries(tagLapses)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 3)
              .map(([tag]) => tag);
            summaryWeakEl.textContent = sortedTags.length
              ? `Weak areas: ${sortedTags.join(", ")}`
              : "Weak areas: None yet";
          }
          return;
        }
        renderCard();
      });
    };

    saveRetry?.addEventListener("click", () => {
      if (pendingAttempt) submitRating(pendingAttempt.rating);
    });
    actionsEl?.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-rating]");
      if (!button || actionsEl.classList.contains("is-disabled")) return;
      submitRating(Number(button.dataset.rating));
    });

    document.addEventListener("keydown", (event) => {
      const isTyping =
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement;
      if (isTyping) return;

      if (event.code === "Space") {
        event.preventDefault();
        reviewCard.classList.toggle("is-flipped");
        if (reviewCard.classList.contains("is-flipped")) {
          unlockActions();
        } else {
          lockActions();
        }
      }

      const ratingMap = {
        Digit1: 0,
        Digit2: 3,
        Digit3: 4,
        Digit4: 5,
      };

      if (
        ratingMap[event.code] !== undefined &&
        !actionsEl.classList.contains("is-disabled") &&
        !isSubmitting
      ) {
        submitRating(ratingMap[event.code]);
      }
    });

    renderCard();
  };

  const setupNoteViewer = () => {
    const viewer = document.querySelector("[data-note-viewer]");
    if (!viewer) return;

    const cards = readJsonScript("note-cards-data") || [];
    if (!cards.length) return;

    const questionEl = document.getElementById("note-card-question");
    const answerEl = document.getElementById("note-card-answer");
    const progressEl = document.getElementById("note-progress");
    const prevButton = viewer.querySelector('[data-nav="prev"]');
    const nextButton = viewer.querySelector('[data-nav="next"]');
    const cardEl = viewer.querySelector(".flashcard");

    let currentIndex = 0;

    const renderNoteCard = () => {
      const card = cards[currentIndex];
      if (!card) return;
      cardEl?.classList.remove("is-flipped");

      const prompt = normalizeMarkdown(card.prompt ?? card.question ?? "");
      const response = normalizeMarkdown(card.response ?? card.answer ?? "");
      renderMarkdown(questionEl, prompt);
      const responseMarkdown = formatResponseMarkdown(card, response);
      renderMarkdown(answerEl, responseMarkdown);

      if (progressEl) {
        progressEl.textContent = `${currentIndex + 1} / ${cards.length}`;
      }
      requestAnimationFrame(() => adjustSingleCardHeight(cardEl));
    };

    const goPrev = () => {
      currentIndex = (currentIndex - 1 + cards.length) % cards.length;
      renderNoteCard();
    };

    const goNext = () => {
      currentIndex = (currentIndex + 1) % cards.length;
      renderNoteCard();
    };

    prevButton?.addEventListener("click", (event) => {
      event.preventDefault();
      goPrev();
    });

    nextButton?.addEventListener("click", (event) => {
      event.preventDefault();
      goNext();
    });

    document.addEventListener("keydown", (event) => {
      const isTyping =
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement;
      if (isTyping) return;

      if (event.code === "ArrowLeft") {
        event.preventDefault();
        goPrev();
      }

      if (event.code === "ArrowRight") {
        event.preventDefault();
        goNext();
      }
    });

    renderNoteCard();
  };

  renderMarkdownBlocks();
  setupFlipCards();
  equalizeCardHeights();
  setupReviewSession();
  setupNoteViewer();

  // Re-equalize on window resize
  let resizeTimeout;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      equalizeCardHeights();
      adjustSingleCardHeight(document.querySelector("[data-review-card]"));
      adjustSingleCardHeight(
        document.querySelector("[data-note-viewer] .flashcard"),
      );
    }, 150);
  });
})();
