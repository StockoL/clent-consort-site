/**
 * LooseLeaf UI - Behaviors Engine
 * Handles DOM interactivity via global event delegation.
 * Maps directly to CUBE CSS Block state hooks (data-state, aria-expanded).
 */

document.addEventListener("click", (event) => {
  const target = event.target;

  // ---------------------------------------------------------------------------
  // 1. ACCORDION BLOCK (Toggle Panel)
  // ---------------------------------------------------------------------------
  const accordionTrigger = target.closest(".accordion__trigger");
  if (accordionTrigger) {
    const isExpanded =
      accordionTrigger.getAttribute("aria-expanded") === "true";
    const panel = accordionTrigger.nextElementSibling;

    // Toggle ARIA state on button
    accordionTrigger.setAttribute("aria-expanded", !isExpanded);

    // Toggle CUBE data-state on the target panel
    if (panel && panel.classList.contains("accordion__panel")) {
      panel.setAttribute("data-state", isExpanded ? "closed" : "open");
    }
    return;
  }

  // ---------------------------------------------------------------------------
  // 2. DROPDOWN BLOCK (Toggle Menu)
  // ---------------------------------------------------------------------------
  const dropdownTrigger = target.closest('[data-toggle="dropdown"]');
  if (dropdownTrigger) {
    const wrapper = dropdownTrigger.closest(".dropdown-wrapper");
    if (wrapper) {
      const currentState = wrapper.getAttribute("data-state");
      const newState = currentState === "open" ? "closed" : "open";

      wrapper.setAttribute("data-state", newState);
      dropdownTrigger.setAttribute("aria-expanded", newState === "open");
    }
    return;
  }

  // Close open dropdowns when clicking outside
  if (!target.closest(".dropdown-wrapper")) {
    document
      .querySelectorAll('.dropdown-wrapper[data-state="open"]')
      .forEach((wrapper) => {
        wrapper.setAttribute("data-state", "closed");
        const trigger = wrapper.querySelector('[data-toggle="dropdown"]');
        if (trigger) trigger.setAttribute("aria-expanded", "false");
      });
  }

  // ---------------------------------------------------------------------------
  // 3. NAVBAR BLOCK (Mobile Menu Toggle)
  // ---------------------------------------------------------------------------
  const navToggle = target.closest(".navbar__toggle");
  if (navToggle) {
    const navbar = navToggle.closest(".navbar");
    const menu = navbar ? navbar.querySelector(".navbar__menu") : null;

    if (menu) {
      const isExpanded = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", !isExpanded);
      menu.setAttribute("data-state", isExpanded ? "closed" : "open");
    }
    return;
  }

  // ---------------------------------------------------------------------------
  // 4. MODAL & OFFCANVAS (Native Dialog Triggers)
  // ---------------------------------------------------------------------------
  const dialogTrigger = target.closest("[data-open-dialog]");
  if (dialogTrigger) {
    const dialogId = dialogTrigger.getAttribute("data-open-dialog");
    const dialogElement = document.getElementById(dialogId);

    if (dialogElement && typeof dialogElement.showModal === "function") {
      dialogElement.showModal();
    }
    return;
  }

  const dialogClose = target.closest("[data-close-dialog]");
  if (dialogClose) {
    const dialogElement = dialogClose.closest("dialog");
    if (dialogElement && typeof dialogElement.close === "function") {
      dialogElement.close();
    }
    return;
  }

  // ---------------------------------------------------------------------------
  // 5. ALERT BLOCK (Dismiss Alert)
  // ---------------------------------------------------------------------------
  const alertClose = target.closest(".alert__close");
  if (alertClose) {
    const alertBlock = alertClose.closest(".alert");
    if (alertBlock) {
      // Trigger CSS transition before removing from DOM
      alertBlock.setAttribute("data-state", "removing");
      alertBlock.addEventListener("transitionend", () => alertBlock.remove(), {
        once: true,
      });
    }
  }
});

// ---------------------------------------------------------------------------
// BACKDROP CLICK TO CLOSE (Modals & Offcanvas Drawers)
// ---------------------------------------------------------------------------
document.addEventListener("click", (event) => {
  if (event.target.tagName === "DIALOG") {
    const dialog = event.target;
    const rect = dialog.getBoundingClientRect();

    // Check if click was outside the dialog bounding box (on the ::backdrop)
    const isInDialog =
      rect.top <= event.clientY &&
      event.clientY <= rect.top + rect.height &&
      rect.left <= event.clientX &&
      event.clientX <= rect.left + rect.width;

    if (!isInDialog) {
      dialog.close();
    }
  }
});

// ---------------------------------------------------------------------------
// GLOBAL ESCAPE KEY HANDLER (Closes Open Dropdowns & Menus)
// ---------------------------------------------------------------------------
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    // Close any open dropdowns
    document
      .querySelectorAll('.dropdown-wrapper[data-state="open"]')
      .forEach((wrapper) => {
        wrapper.setAttribute("data-state", "closed");
        const trigger = wrapper.querySelector('[data-toggle="dropdown"]');
        if (trigger) trigger.setAttribute("aria-expanded", "false");
      });

    // Close mobile navbar if expanded
    document
      .querySelectorAll('.navbar__menu[data-state="open"]')
      .forEach((menu) => {
        menu.setAttribute("data-state", "closed");
        const toggle = menu
          .closest(".navbar")
          ?.querySelector(".navbar__toggle");
        if (toggle) toggle.setAttribute("aria-expanded", "false");
      });
  }
});

// ---------------------------------------------------------------------------
// UTILITY: CLIPBOARD COPY
// ---------------------------------------------------------------------------
document.addEventListener("click", async (event) => {
  const copyTrigger = event.target.closest("[data-copy]");
  if (!copyTrigger) return;

  const textToCopy = copyTrigger.getAttribute("data-copy");

  try {
    await navigator.clipboard.writeText(textToCopy);

    // Provide visual feedback hook for CSS
    copyTrigger.setAttribute("data-state", "copied");

    // Reset state after 2 seconds
    setTimeout(() => {
      copyTrigger.removeAttribute("data-state");
    }, 2000);
  } catch (err) {
    console.error("Failed to copy text: ", err);
  }
});

// ---------------------------------------------------------------------------
// UTILITY: MOTION-SAFE SMOOTH SCROLLING
// ---------------------------------------------------------------------------
document.addEventListener("click", (event) => {
  const scrollTrigger = event.target.closest('a[href^="#"]:not([href="#"])');
  if (!scrollTrigger) return;

  const targetId = scrollTrigger.getAttribute("href").substring(1);
  const targetElement = document.getElementById(targetId);

  if (targetElement) {
    event.preventDefault();

    // Respect user reduced motion preferences
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    targetElement.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
      block: "start",
    });

    // Set focus to the target for keyboard users
    targetElement.focus({ preventScroll: true });
  }
});
