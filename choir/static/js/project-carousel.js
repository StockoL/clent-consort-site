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

  // Background videos (Build Order Phase 10). The markup has no autoplay
  // and preload="none", so nothing downloads until played. Wider screens
  // without reduced motion start them as before; on phones, or with
  // reduced motion, each slide shows its poster and a play button.
  const manualPlay = window.matchMedia("(prefers-reduced-motion: reduce), (max-width: 45rem)");

  const setPlayLabel = (button, playing) => {
    button.querySelector("[data-rhythm-icon]").textContent = playing ? "❚❚" : "▶";
    button.querySelector("[data-rhythm-label]").textContent = playing ? "Pause video" : "Play video";
  };

  const setUpVideos = () => {
    slides.forEach((slide) => {
      const video = slide.querySelector("video");
      const button = slide.querySelector("[data-rhythm-play]");
      if (!video) return;
      if (manualPlay.matches) {
        video.pause();
        if (button) {
          button.hidden = false;
          setPlayLabel(button, false);
        }
      } else {
        if (button) button.hidden = true;
        video.play().catch(() => {});
      }
    });
  };

  carousel.addEventListener("click", (event) => {
    const button = event.target.closest("[data-rhythm-play]");
    if (!button) return;
    const video = button.closest(".rhythm-slide").querySelector("video");
    if (video.paused) {
      video.play().catch(() => {});
      setPlayLabel(button, true);
    } else {
      video.pause();
      setPlayLabel(button, false);
    }
  });

  manualPlay.addEventListener("change", setUpVideos);
  setUpVideos();
};

document.addEventListener("DOMContentLoaded", initProjectCarousel);
