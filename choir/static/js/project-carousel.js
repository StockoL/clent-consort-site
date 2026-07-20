/* ==========================================================================
    ABOUT PAGE PROJECT RHYTHM SWIPE NAV
   ========================================================================== */

const initProjectCarousel = () => {
  const carousel = document.querySelector("#project-carousel");
  if (!carousel) return;

  const scrollContainer = carousel.querySelector(".project-rhythm-scroll");
  const navButtons = carousel.querySelectorAll(".nav-link");
  const slides = carousel.querySelectorAll(".rhythm-slide");

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      const targetSlide = document.getElementById(targetId);

      if (targetSlide && scrollContainer) {
        scrollContainer.scrollTo({
          left: targetSlide.offsetLeft,
          behavior: "smooth",
        });
      }
    });
  });

  const observerOptions = {
    root: scrollContainer,
    threshold: 0.6,
  };

  const slideObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const activeId = entry.target.id;

        navButtons.forEach((btn) => {
          const matches = btn.getAttribute("data-target") === activeId;
          btn.classList.toggle("is-active", matches);
        });
      }
    });
  }, observerOptions);

  slides.forEach((slide) => slideObserver.observe(slide));

  const checkMobileViewport = () => {
    const isMobile = window.innerWidth < 640;
    navButtons.forEach((btn) => {
      btn.classList.toggle("is-dot-mode", isMobile);
    });
  };

  window.addEventListener("resize", checkMobileViewport);
  checkMobileViewport();
};

document.addEventListener("DOMContentLoaded", initProjectCarousel);
