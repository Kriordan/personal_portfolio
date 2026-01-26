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
    const doneUrl = config.doneUrl || "/learning/";
    const toastEl = document.getElementById("flashcard-toast");
    const summaryEl = document.getElementById("review-summary");
    const summaryTextEl = document.getElementById("review-summary-text");
    const summaryDoneEl = document.getElementById("review-summary-done");

    let currentIndex = 0;
    let cardStart = performance.now();
    let completedCount = 0;
    let isSubmitting = false;
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const updateProgress = () => {
      if (progressEl) {
        progressEl.textContent = `Card ${currentIndex + 1} of ${cards.length}`;
      }
    };

    const lockActions = () => {
      actionsEl?.classList.add("is-disabled");
    };

    const unlockActions = () => {
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

      questionEl.textContent = card.question;
      answerEl.textContent = card.answer;
      noteTitleEl.textContent = card.note_title ? `From ${card.note_title}` : "";
      updateProgress();
      cardStart = performance.now();
    };

    const sendRating = async (cardId, rating) => {
      if (!rateUrlWithDebug) return;
      const responseMs = Math.max(0, Math.round(performance.now() - cardStart));
      try {
        const response = await fetch(rateUrlWithDebug, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            card_id: cardId,
            rating,
            response_ms: responseMs,
            session_id: sessionId,
          }),
        });
        if (!response.ok) {
          return null;
        }
        return response.json();
      } catch (error) {
        console.error("Failed to rate card", error);
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

    actionsEl?.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-rating]");
      if (!button || actionsEl.classList.contains("is-disabled") || isSubmitting) {
        return;
      }
      const rating = Number(button.dataset.rating);
      const card = cards[currentIndex];
      if (!card) return;

      isSubmitting = true;
      lockActions();

      sendRating(card.card_id, rating).then((data) => {
        isSubmitting = false;
        if (data?.next_review_display) {
          showToast(data.next_review_display);
        }
        if (data?.debug) {
          console.log("Scheduler debug", data.debug);
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
          return;
        }
        renderCard();
      });
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
        const rating = ratingMap[event.code];
        const card = cards[currentIndex];
        isSubmitting = true;
        lockActions();
        sendRating(card.card_id, rating).then((data) => {
          isSubmitting = false;
          if (data?.next_review_display) {
            showToast(data.next_review_display);
          }
          if (data?.debug) {
            console.log("Scheduler debug", data.debug);
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
            return;
          }
          renderCard();
        });
      }
    });

    summaryDoneEl?.addEventListener("click", () => {
      window.location.href = doneUrl;
    });

    renderCard();
  };

  setupFlipCards();
  equalizeCardHeights();
  setupReviewSession();

  // Re-equalize on window resize
  let resizeTimeout;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(equalizeCardHeights, 150);
  });
})();
