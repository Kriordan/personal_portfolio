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

    let currentIndex = 0;

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

    const renderCard = () => {
      const card = cards[currentIndex];
      if (!card) return;

      reviewCard.classList.remove("is-flipped");
      lockActions();

      questionEl.textContent = card.question;
      answerEl.textContent = card.answer;
      noteTitleEl.textContent = card.note_title ? `From ${card.note_title}` : "";
      updateProgress();
    };

    const sendRating = async (cardId, rating) => {
      if (!rateUrl) return;
      try {
        await fetch(rateUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ card_id: cardId, rating }),
        });
      } catch (error) {
        console.error("Failed to rate card", error);
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
      if (!button || actionsEl.classList.contains("is-disabled")) {
        return;
      }
      const rating = Number(button.dataset.rating);
      const card = cards[currentIndex];
      if (!card) return;

      sendRating(card.card_id, rating);

      currentIndex += 1;
      if (currentIndex >= cards.length) {
        window.location.reload();
        return;
      }
      renderCard();
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

      if (ratingMap[event.code] !== undefined && !actionsEl.classList.contains("is-disabled")) {
        const rating = ratingMap[event.code];
        const card = cards[currentIndex];
        sendRating(card.card_id, rating);
        currentIndex += 1;
        if (currentIndex >= cards.length) {
          window.location.reload();
          return;
        }
        renderCard();
      }
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
