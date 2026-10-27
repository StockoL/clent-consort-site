/* ==========================================================================
    MEMBERS NAV: current page in view, and the committee panel on phones
   ========================================================================== */
/**
 * On phones the members nav is a horizontally scrolling reel of the member
 * links, ending in a "Committee" button that opens the committee links as
 * a grid underneath (_members_nav.html). This script:
 *   - marks the nav data-js, which lets the CSS hide the panel until opened
 *     (without JavaScript the grid simply shows under the reel);
 *   - shows the button, labelled with the committee page you're on
 *     ("Committee: Financials") and highlighted when you're on one;
 *   - opens and closes the panel, closing it on Escape or a tap outside;
 *   - scrolls the reel so the current member link is in view.
 * On desktop the panel is part of the sidebar and the button is hidden.
 */
document.addEventListener("DOMContentLoaded", () => {
  const nav = document.querySelector(".members-nav");
  if (!nav) return;

  const reel = nav.querySelector(".members-nav__list");
  const toggle = nav.querySelector("[data-committee-toggle]");
  const panel = nav.querySelector("[data-committee-panel]");

  if (toggle && panel) {
    nav.dataset.js = "";
    toggle.hidden = false;

    const currentCommitteeLink = panel.querySelector("[aria-current='page']");
    if (currentCommitteeLink) {
      // The link's own text, without the inbox count badge
      const name = currentCommitteeLink.firstChild.textContent.trim();
      toggle.querySelector("[data-committee-label]").textContent = `Committee: ${name}`;
      toggle.classList.add("is-current");
    }

    const setOpen = (open) => {
      toggle.setAttribute("aria-expanded", open);
      if (open) {
        panel.dataset.open = "";
      } else {
        delete panel.dataset.open;
      }
    };

    toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));

    document.addEventListener("click", (event) => {
      if (toggle.getAttribute("aria-expanded") === "true" && !nav.contains(event.target)) {
        setOpen(false);
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });
  }

  // Keep the current link (or the Committee button standing in for it) in
  // view in the reel - only the reel scrolls, not the page.
  const current = reel && (reel.querySelector("[aria-current='page']") || reel.querySelector(".is-current"));
  if (current && reel.scrollWidth > reel.clientWidth) {
    reel.scrollLeft = current.offsetLeft - reel.offsetLeft - reel.clientWidth / 2 + current.offsetWidth / 2;
  }
});
