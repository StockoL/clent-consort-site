/* ==========================================================================
   BACK TO TOP FUNCTIONALITY
   ========================================================================== */

const initBackToTop = () => {
  const backToTopButton = document.querySelector("#backToTop");
  if (!backToTopButton) return;

  window.addEventListener("scroll", () => {
    if (window.scrollY > 300) {
      backToTopButton.classList.add("is-visible");
      backToTopButton.setAttribute("aria-hidden", "false");
      backToTopButton.setAttribute("tabindex", "0");
    } else {
      backToTopButton.classList.remove("is-visible");
      backToTopButton.setAttribute("aria-hidden", "true");
      backToTopButton.setAttribute("tabindex", "-1");

      if (document.activeElement === backToTopButton) {
        backToTopButton.blur();
      }
    }
  });

  // Hide once the footer (which has its own "Top" link) scrolls into
  // view, so the two controls don't overlap/duplicate at the page end.
  const footer = document.querySelector("footer");
  if (footer && "IntersectionObserver" in window) {
    const footerObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        backToTopButton.classList.toggle("is-near-footer", entry.isIntersecting);
      });
    });
    footerObserver.observe(footer);
  }

  backToTopButton.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
};

document.addEventListener("DOMContentLoaded", initBackToTop);
