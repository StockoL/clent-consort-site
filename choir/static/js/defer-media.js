/* ==========================================================================
    DEFERRED MEDIA (About page)
   ========================================================================== */
/**
 * Loads media below the first screen only as the visitor scrolls near it,
 * so it doesn't compete with the page's banner for a phone's connection.
 * A video's poster image and an iframe load straight away however far down
 * the page they are (Chrome starts "lazy" iframes early on slow
 * connections), and on About they held up the first paint by about a
 * second in Lighthouse's phone test.
 *
 * - data-defer-poster on a <video> becomes its poster.
 * - data-defer-src on an <iframe> becomes its src, and the iframe is
 *   unhidden. Third-party embeds then set no cookies until they're near.
 * - Inside a [data-defer-group], everything loads together once the group
 *   is near. Use one for slides off to the side of a sideways-scrolling
 *   strip, which never count as near on their own, and around a hidden
 *   iframe, which can't be seen to come near until it's shown.
 *
 * Without JavaScript the posters stay blank and the page's <noscript>
 * fallbacks (a plain link) take the iframes' place.
 */
(() => {
  const deferred = document.querySelectorAll("[data-defer-src], [data-defer-poster]");
  if (!deferred.length) return;

  const load = (element) => {
    if (element.dataset.deferPoster) {
      element.poster = element.dataset.deferPoster;
      delete element.dataset.deferPoster;
    }
    if (element.dataset.deferSrc) {
      element.src = element.dataset.deferSrc;
      element.hidden = false;
      delete element.dataset.deferSrc;
    }
  };

  if (!("IntersectionObserver" in window)) {
    deferred.forEach(load);
    return;
  }

  // What to watch: each group, and each deferred element outside a group
  const watched = new Set();
  deferred.forEach((element) => watched.add(element.closest("[data-defer-group]") || element));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const target = entry.target;
        if (target.matches("[data-defer-group]")) {
          target.querySelectorAll("[data-defer-src], [data-defer-poster]").forEach(load);
        } else {
          load(target);
        }
        observer.unobserve(target);
      });
    },
    // A little ahead of the visitor, so it's there by the time they arrive
    { rootMargin: "300px 0px" },
  );
  watched.forEach((element) => observer.observe(element));
})();
