/* ==========================================================================
    MEMBERS NAV: keep the current page in view
   ========================================================================== */
/**
 * On phones the members nav is a horizontally scrolling reel, so on a
 * committee page the current link starts off-screen to the right. Scroll
 * the reel (only the reel, not the page) so it's visible.
 */
document.addEventListener("DOMContentLoaded", () => {
  const current = document.querySelector(".members-nav [aria-current='page']");
  const reel = current && current.closest(".members-nav__list");
  if (!reel || reel.scrollWidth <= reel.clientWidth) return;

  reel.scrollLeft = current.offsetLeft - reel.offsetLeft - reel.clientWidth / 2 + current.offsetWidth / 2;
});
