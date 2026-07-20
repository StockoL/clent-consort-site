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

  backToTopButton.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
};

document.addEventListener("DOMContentLoaded", initBackToTop);
