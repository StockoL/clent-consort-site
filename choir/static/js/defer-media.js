/* ==========================================================================
    DEFERRED MEDIA (About page)
   ========================================================================== */
/**
 * Loads images and embeds below the first screen only as the visitor
 * scrolls near them, so they don't compete with the page's banner for a
 * phone's connection. loading="lazy" isn't enough: Chrome starts lazy
 * images and iframes well before they're near (on About it fetched the
 * carousel's stills with the page).
 *
 * Inside a [data-defer-group], each element's data-defer-src becomes its
 * src, and it's unhidden if it was hidden, once the group is within 300px
 * of the screen. The group is what's watched: slides off to the side of
 * a sideways-scrolling strip never count as near on their own, and a
 * hidden iframe can't be seen to come near. A third-party embed then sets
 * no cookies until it's needed. Without JavaScript, the page's <noscript>
 * fallbacks (the stills themselves, a plain link) take their place.
 */
(() => {
  const groups = document.querySelectorAll("[data-defer-group]");
  if (!groups.length) return;

  const load = (group) => {
    group.querySelectorAll("[data-defer-src]").forEach((element) => {
      element.src = element.dataset.deferSrc;
      element.hidden = false;
      delete element.dataset.deferSrc;
    });
  };

  if (!("IntersectionObserver" in window)) {
    groups.forEach(load);
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        load(entry.target);
        observer.unobserve(entry.target);
      });
    },
    // A little ahead of the visitor, so it's there by the time they arrive
    { rootMargin: "300px 0px" },
  );
  groups.forEach((group) => observer.observe(group));
})();
