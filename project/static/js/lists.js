/**
 * Lists Module - Native Drag and Drop with Touch Fallback
 *
 * This module handles all list interactions including:
 * - Drag and drop for items (within and across categories)
 * - Drag and drop for categories
 * - Touch fallback for mobile devices
 * - Toggle functionality for completing items
 * - Real-time sync via WebSockets (when available)
 */

(function () {
  "use strict";

  // Configuration - will be set from template
  let config = {
    listId: null,
    csrfToken: null,
    urls: {
      toggleItem: null,
      reorderItems: null,
      reorderCategories: null,
      updateSettings: null,
    },
    completedDisplayMode: "category_section", // inline_bottom, category_section, global_section
  };

  // State for drag operations
  let dragState = {
    draggedElement: null,
    draggedType: null, // 'item' or 'category'
    sourceContainer: null,
    placeholder: null,
    touchStartY: 0,
    touchStartX: 0,
    isTouchDrag: false,
    scrollInterval: null,
  };

  // WebSocket connection (will be set up later)
  let socket = null;

  /**
   * Initialize the lists module
   * @param {Object} options - Configuration options from the template
   */
  function init(options) {
    Object.assign(config, options);

    setupItemDragAndDrop();
    setupCategoryDragAndDrop();
    setupToggleHandlers();
    setupTouchFallback();
  }

  // ============================================
  // ITEM DRAG AND DROP
  // ============================================

  function setupItemDragAndDrop() {
    const items = document.querySelectorAll(
      ".item-list li, .completed-list li"
    );
    const dropZones = document.querySelectorAll(".item-list, .completed-list");

    items.forEach((item) => {
      item.setAttribute("draggable", "true");
      item.addEventListener("dragstart", handleItemDragStart);
      item.addEventListener("dragend", handleItemDragEnd);
    });

    dropZones.forEach((zone) => {
      zone.addEventListener("dragover", handleItemDragOver);
      zone.addEventListener("dragenter", handleItemDragEnter);
      zone.addEventListener("dragleave", handleItemDragLeave);
      zone.addEventListener("drop", handleItemDrop);
    });
  }

  function handleItemDragStart(e) {
    dragState.draggedElement = e.target.closest("li");
    dragState.draggedType = "item";
    dragState.sourceContainer = dragState.draggedElement.parentElement;

    // Set drag data
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", dragState.draggedElement.dataset.id);
    e.dataTransfer.setData(
      "application/x-item-id",
      dragState.draggedElement.dataset.id
    );

    // Add dragging class after a small delay to prevent visual glitch
    requestAnimationFrame(() => {
      dragState.draggedElement.classList.add("is-dragging");
    });

    createPlaceholder(dragState.draggedElement);
  }

  function handleItemDragEnd(e) {
    if (dragState.draggedElement) {
      dragState.draggedElement.classList.remove("is-dragging");
    }
    removePlaceholder();
    removeAllDragOverClasses();
    dragState.draggedElement = null;
    dragState.draggedType = null;
    dragState.sourceContainer = null;
  }

  function handleItemDragOver(e) {
    if (dragState.draggedType !== "item") return;

    e.preventDefault();
    e.dataTransfer.dropEffect = "move";

    const dropZone = e.currentTarget;
    const afterElement = getDragAfterElement(dropZone, e.clientY);

    if (afterElement) {
      dropZone.insertBefore(dragState.placeholder, afterElement);
    } else {
      dropZone.appendChild(dragState.placeholder);
    }
  }

  function handleItemDragEnter(e) {
    if (dragState.draggedType !== "item") return;
    e.preventDefault();
    e.currentTarget.classList.add("drag-over");
  }

  function handleItemDragLeave(e) {
    // Only remove class if actually leaving the container
    if (!e.currentTarget.contains(e.relatedTarget)) {
      e.currentTarget.classList.remove("drag-over");
    }
  }

  function handleItemDrop(e) {
    if (dragState.draggedType !== "item") return;

    e.preventDefault();
    const dropZone = e.currentTarget;
    dropZone.classList.remove("drag-over");

    // Insert the actual element where placeholder is
    if (dragState.placeholder && dragState.placeholder.parentNode) {
      dragState.placeholder.parentNode.insertBefore(
        dragState.draggedElement,
        dragState.placeholder
      );
    }

    removePlaceholder();

    // Send reorder request
    saveItemOrder(dropZone);
  }

  // ============================================
  // CATEGORY DRAG AND DROP
  // ============================================

  function setupCategoryDragAndDrop() {
    const categories = document.querySelectorAll(".category");
    const categoriesContainer = document.getElementById("categories");

    categories.forEach((category) => {
      const header = category.querySelector("h2");
      if (header) {
        header.setAttribute("draggable", "true");
        header.style.cursor = "grab";
        header.addEventListener("dragstart", handleCategoryDragStart);
        header.addEventListener("dragend", handleCategoryDragEnd);
      }
    });

    if (categoriesContainer) {
      categoriesContainer.addEventListener("dragover", handleCategoryDragOver);
      categoriesContainer.addEventListener("drop", handleCategoryDrop);
    }
  }

  function handleCategoryDragStart(e) {
    const category = e.target.closest(".category");
    dragState.draggedElement = category;
    dragState.draggedType = "category";

    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", category.dataset.id);
    e.dataTransfer.setData("application/x-category-id", category.dataset.id);

    requestAnimationFrame(() => {
      category.classList.add("is-dragging");
    });

    createPlaceholder(category);
  }

  function handleCategoryDragEnd(e) {
    if (dragState.draggedElement) {
      dragState.draggedElement.classList.remove("is-dragging");
    }
    removePlaceholder();
    removeAllDragOverClasses();
    dragState.draggedElement = null;
    dragState.draggedType = null;
  }

  function handleCategoryDragOver(e) {
    if (dragState.draggedType !== "category") return;

    e.preventDefault();
    e.dataTransfer.dropEffect = "move";

    const container = e.currentTarget;
    const afterElement = getDragAfterElement(container, e.clientY, ".category");

    if (afterElement) {
      container.insertBefore(dragState.placeholder, afterElement);
    } else {
      container.appendChild(dragState.placeholder);
    }
  }

  function handleCategoryDrop(e) {
    if (dragState.draggedType !== "category") return;

    e.preventDefault();

    if (dragState.placeholder && dragState.placeholder.parentNode) {
      dragState.placeholder.parentNode.insertBefore(
        dragState.draggedElement,
        dragState.placeholder
      );
    }

    removePlaceholder();
    saveCategoryOrder();
  }

  // ============================================
  // TOGGLE FUNCTIONALITY
  // ============================================

  function setupToggleHandlers() {
    document.querySelectorAll(".toggle-item").forEach((checkbox) => {
      checkbox.addEventListener("change", handleToggle);
    });
  }

  function handleToggle(e) {
    const checkbox = e.target;
    const itemId = checkbox.dataset.itemId;
    const listItem = checkbox.closest("li");

    // Optimistic UI update
    listItem.classList.add("is-toggling");

    const url = config.urls.toggleItem.replace("/0", "/" + itemId);

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": config.csrfToken,
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          moveItemToCorrectList(listItem, data.completed);
          if (socket && socket.connected) {
            socket.emit("item_toggled", {
              list_id: config.listId,
              item_id: itemId,
              completed: data.completed,
            });
          }
        } else {
          // Rollback
          checkbox.checked = !checkbox.checked;
          listItem.classList.remove("is-toggling");
        }
      })
      .catch((error) => {
        console.error("Toggle failed:", error);
        checkbox.checked = !checkbox.checked;
        listItem.classList.remove("is-toggling");
      });
  }

  function moveItemToCorrectList(listItem, isCompleted) {
    const categoryDiv = listItem.closest(".category");
    const categoryId = categoryDiv.dataset.id;

    listItem.classList.remove("is-toggling");

    // Add transition class for animation
    listItem.classList.add("is-moving");

    setTimeout(() => {
      let targetList;

      switch (config.completedDisplayMode) {
        case "inline_bottom":
          // Stay in same list, just reorder
          targetList = categoryDiv.querySelector(".item-list");
          if (isCompleted) {
            listItem.classList.add("is-completed");
            targetList.appendChild(listItem);
          } else {
            listItem.classList.remove("is-completed");
            const firstCompleted = targetList.querySelector(".is-completed");
            if (firstCompleted) {
              targetList.insertBefore(listItem, firstCompleted);
            } else {
              targetList.appendChild(listItem);
            }
          }
          break;

        case "global_section":
          // Move to/from global completed section
          if (isCompleted) {
            targetList = document.getElementById("global-completed-list");
            listItem.classList.add("is-completed");
            listItem.dataset.originalCategory = categoryId;
          } else {
            const originalCategoryId =
              listItem.dataset.originalCategory || categoryId;
            targetList = document.getElementById(
              "category-" + originalCategoryId
            );
            listItem.classList.remove("is-completed");
            delete listItem.dataset.originalCategory;
          }
          if (targetList) {
            targetList.appendChild(listItem);
          }
          break;

        case "category_section":
        default:
          // Move between item-list and completed-list within category
          if (isCompleted) {
            targetList = document.getElementById("completed-" + categoryId);
            listItem.classList.add("is-completed");
          } else {
            targetList = document.getElementById("category-" + categoryId);
            listItem.classList.remove("is-completed");
          }
          if (targetList) {
            targetList.appendChild(listItem);
          }
          break;
      }

      listItem.classList.remove("is-moving");

      const checkbox = listItem.querySelector(".toggle-item");
      if (checkbox) {
        checkbox.checked = isCompleted;
      }

      listItem.setAttribute("draggable", "true");
    }, 200);
  }

  // ============================================
  // TOUCH FALLBACK
  // ============================================

  function setupTouchFallback() {
    // Check if device primarily uses touch
    if (!("ontouchstart" in window)) return;

    const items = document.querySelectorAll(
      ".item-list li, .completed-list li"
    );
    const categories = document.querySelectorAll(".category h2");

    items.forEach((item) => {
      item.addEventListener("touchstart", handleTouchStart, { passive: false });
      item.addEventListener("touchmove", handleTouchMove, { passive: false });
      item.addEventListener("touchend", handleTouchEnd);
    });

    categories.forEach((header) => {
      header.addEventListener("touchstart", handleTouchStart, {
        passive: false,
      });
      header.addEventListener("touchmove", handleTouchMove, { passive: false });
      header.addEventListener("touchend", handleTouchEnd);
    });
  }

  function handleTouchStart(e) {
    // Long press to start drag
    const touch = e.touches[0];
    dragState.touchStartX = touch.clientX;
    dragState.touchStartY = touch.clientY;

    const element = e.target.closest("li") || e.target.closest(".category");
    if (!element) return;

    dragState.longPressTimer = setTimeout(() => {
      e.preventDefault();
      startTouchDrag(element, e.target.closest("li") ? "item" : "category");
    }, 300);
  }

  function handleTouchMove(e) {
    if (dragState.longPressTimer) {
      // Cancel long press if moved too much
      const touch = e.touches[0];
      const deltaX = Math.abs(touch.clientX - dragState.touchStartX);
      const deltaY = Math.abs(touch.clientY - dragState.touchStartY);

      if (deltaX > 10 || deltaY > 10) {
        clearTimeout(dragState.longPressTimer);
        dragState.longPressTimer = null;
      }
    }

    if (!dragState.isTouchDrag) return;

    e.preventDefault();

    const touch = e.touches[0];
    moveTouchDrag(touch.clientX, touch.clientY);

    // Auto-scroll when near edges
    handleAutoScroll(touch.clientY);
  }

  function handleTouchEnd(e) {
    if (dragState.longPressTimer) {
      clearTimeout(dragState.longPressTimer);
      dragState.longPressTimer = null;
    }

    if (!dragState.isTouchDrag) return;

    endTouchDrag();
  }

  function startTouchDrag(element, type) {
    dragState.isTouchDrag = true;
    dragState.draggedElement = element;
    dragState.draggedType = type;
    dragState.sourceContainer =
      type === "item" ? element.parentElement : element.parentElement;

    element.classList.add("is-dragging", "is-touch-dragging");
    createPlaceholder(element);

    // Disable scrolling on body
    document.body.style.overflow = "hidden";
  }

  function moveTouchDrag(clientX, clientY) {
    if (!dragState.draggedElement) return;

    // Position the dragged element
    const rect = dragState.draggedElement.getBoundingClientRect();
    dragState.draggedElement.style.position = "fixed";
    dragState.draggedElement.style.left = clientX - rect.width / 2 + "px";
    dragState.draggedElement.style.top = clientY - rect.height / 2 + "px";
    dragState.draggedElement.style.zIndex = "1000";
    dragState.draggedElement.style.pointerEvents = "none";

    // Find drop target
    const elementsBelow = document.elementsFromPoint(clientX, clientY);
    const dropZone = elementsBelow.find((el) => {
      if (dragState.draggedType === "item") {
        return (
          el.classList.contains("item-list") ||
          el.classList.contains("completed-list")
        );
      } else {
        return el.id === "categories";
      }
    });

    if (dropZone) {
      dropZone.classList.add("drag-over");
      const selector = dragState.draggedType === "item" ? "li" : ".category";
      const afterElement = getDragAfterElement(dropZone, clientY, selector);

      if (afterElement) {
        dropZone.insertBefore(dragState.placeholder, afterElement);
      } else {
        dropZone.appendChild(dragState.placeholder);
      }
    }
  }

  function endTouchDrag() {
    if (!dragState.draggedElement) return;

    dragState.draggedElement.style.position = "";
    dragState.draggedElement.style.left = "";
    dragState.draggedElement.style.top = "";
    dragState.draggedElement.style.zIndex = "";
    dragState.draggedElement.style.pointerEvents = "";
    dragState.draggedElement.classList.remove(
      "is-dragging",
      "is-touch-dragging"
    );

    // Insert at placeholder position
    if (dragState.placeholder && dragState.placeholder.parentNode) {
      dragState.placeholder.parentNode.insertBefore(
        dragState.draggedElement,
        dragState.placeholder
      );
    }

    // Save order
    if (dragState.draggedType === "item") {
      const dropZone = dragState.draggedElement.parentElement;
      saveItemOrder(dropZone);
    } else {
      saveCategoryOrder();
    }

    // Cleanup
    removePlaceholder();
    removeAllDragOverClasses();
    document.body.style.overflow = "";

    if (dragState.scrollInterval) {
      clearInterval(dragState.scrollInterval);
      dragState.scrollInterval = null;
    }

    dragState.isTouchDrag = false;
    dragState.draggedElement = null;
    dragState.draggedType = null;
    dragState.sourceContainer = null;
  }

  function handleAutoScroll(clientY) {
    const threshold = 50;
    const scrollSpeed = 10;

    if (dragState.scrollInterval) {
      clearInterval(dragState.scrollInterval);
      dragState.scrollInterval = null;
    }

    if (clientY < threshold) {
      dragState.scrollInterval = setInterval(() => {
        window.scrollBy(0, -scrollSpeed);
      }, 16);
    } else if (clientY > window.innerHeight - threshold) {
      dragState.scrollInterval = setInterval(() => {
        window.scrollBy(0, scrollSpeed);
      }, 16);
    }
  }

  // ============================================
  // HELPER FUNCTIONS
  // ============================================

  function createPlaceholder(element) {
    removePlaceholder();

    dragState.placeholder = document.createElement(element.tagName);
    dragState.placeholder.classList.add("drag-placeholder");
    dragState.placeholder.style.height = element.offsetHeight + "px";
    dragState.placeholder.style.margin = getComputedStyle(element).margin;

    element.parentNode.insertBefore(dragState.placeholder, element.nextSibling);
  }

  function removePlaceholder() {
    if (dragState.placeholder && dragState.placeholder.parentNode) {
      dragState.placeholder.parentNode.removeChild(dragState.placeholder);
    }
    dragState.placeholder = null;
  }

  function removeAllDragOverClasses() {
    document.querySelectorAll(".drag-over").forEach((el) => {
      el.classList.remove("drag-over");
    });
  }

  function getDragAfterElement(container, y, selector = "li") {
    const draggableElements = [
      ...container.querySelectorAll(
        `${selector}:not(.is-dragging):not(.drag-placeholder)`
      ),
    ];

    return draggableElements.reduce(
      (closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;

        if (offset < 0 && offset > closest.offset) {
          return { offset: offset, element: child };
        } else {
          return closest;
        }
      },
      { offset: Number.NEGATIVE_INFINITY }
    ).element;
  }

  // ============================================
  // API CALLS
  // ============================================

  function saveItemOrder(dropZone) {
    const items = Array.from(dropZone.children)
      .filter(
        (el) =>
          el.tagName === "LI" && !el.classList.contains("drag-placeholder")
      )
      .map((li, index) => {
        // Parse category ID from the list ID (format: "category-{id}" or "completed-{id}")
        const listId = dropZone.id;
        const categoryId = listId
          .replace("category-", "")
          .replace("completed-", "");

        return {
          id: parseInt(li.dataset.id),
          ordering: index + 1,
          category_id: parseInt(categoryId),
        };
      });

    fetch(config.urls.reorderItems, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": config.csrfToken,
      },
      body: JSON.stringify({ items: items }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success && socket && socket.connected) {
          socket.emit("items_reordered", {
            list_id: config.listId,
            items: items,
          });
        }
      })
      .catch((error) => {
        console.error("Failed to save item order:", error);
        // Could implement rollback here
      });
  }

  function saveCategoryOrder() {
    const categories = Array.from(document.querySelectorAll(".category"))
      .filter((el) => !el.classList.contains("drag-placeholder"))
      .map((div, index) => ({
        id: parseInt(div.dataset.id),
        ordering: index + 1,
      }));

    fetch(config.urls.reorderCategories, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": config.csrfToken,
      },
      body: JSON.stringify({ categories: categories }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success && socket && socket.connected) {
          socket.emit("categories_reordered", {
            list_id: config.listId,
            categories: categories,
          });
        }
      })
      .catch((error) => {
        console.error("Failed to save category order:", error);
      });
  }

  // ============================================
  // WEBSOCKET INTEGRATION
  // ============================================

  function initWebSocket() {
    if (typeof io === "undefined") {
      console.warn("Socket.IO not loaded, real-time sync disabled");
      return;
    }

    socket = io();

    socket.on("connect", () => {
      console.log("Connected to WebSocket");
      socket.emit("join_list", { list_id: config.listId });
    });

    socket.on("item_toggled", (data) => {
      if (data.list_id !== config.listId) return;
      handleRemoteItemToggle(data.item_id, data.completed);
    });

    socket.on("items_reordered", (data) => {
      if (data.list_id !== config.listId) return;
      handleRemoteItemsReorder(data.items);
    });

    socket.on("categories_reordered", (data) => {
      if (data.list_id !== config.listId) return;
      handleRemoteCategoriesReorder(data.categories);
    });

    socket.on("item_added", (data) => {
      if (data.list_id !== config.listId) return;
      handleRemoteItemAdded(data);
    });

    socket.on("category_added", (data) => {
      if (data.list_id !== config.listId) return;
      handleRemoteCategoryAdded(data);
    });

    socket.on("settings_updated", (data) => {
      if (data.list_id !== config.listId) return;
      handleRemoteSettingsUpdate(data);
    });

    socket.on("disconnect", () => {
      console.log("Disconnected from WebSocket");
    });
  }

  function handleRemoteItemToggle(itemId, completed) {
    const listItem = document.querySelector(`li[data-id="${itemId}"]`);
    if (!listItem) return;

    moveItemToCorrectList(listItem, completed);
  }

  function handleRemoteItemsReorder(items) {
    items.forEach((itemData) => {
      const item = document.querySelector(`li[data-id="${itemData.id}"]`);
      if (!item) return;

      const targetList =
        document.getElementById("category-" + itemData.category_id) ||
        document.getElementById("completed-" + itemData.category_id);
      if (targetList && item.parentElement !== targetList) {
        targetList.appendChild(item);
      }
    });

    // Reorder within lists
    const lists = document.querySelectorAll(".item-list, .completed-list");
    lists.forEach((list) => {
      const children = Array.from(list.children)
        .filter((el) => el.tagName === "LI")
        .sort((a, b) => {
          const aData = items.find((i) => i.id === parseInt(a.dataset.id));
          const bData = items.find((i) => i.id === parseInt(b.dataset.id));
          return (aData?.ordering || 0) - (bData?.ordering || 0);
        });

      children.forEach((child) => list.appendChild(child));
    });
  }

  function handleRemoteCategoriesReorder(categories) {
    const container = document.getElementById("categories");
    if (!container) return;

    categories
      .sort((a, b) => a.ordering - b.ordering)
      .forEach((catData) => {
        const category = document.querySelector(
          `.category[data-id="${catData.id}"]`
        );
        if (category) {
          container.appendChild(category);
        }
      });
  }

  function handleRemoteItemAdded(data) {
    // Reload the page to get the new item - or implement dynamic insertion
    location.reload();
  }

  function handleRemoteCategoryAdded(data) {
    location.reload();
  }

  function handleRemoteSettingsUpdate(data) {
    if (data.completed_display_mode) {
      config.completedDisplayMode = data.completed_display_mode;
    }
  }

  // ============================================
  // PUBLIC API
  // ============================================

  window.ListsModule = {
    init: init,
    initWebSocket: initWebSocket,
    setCompletedDisplayMode: function (mode) {
      config.completedDisplayMode = mode;
    },
  };
})();
