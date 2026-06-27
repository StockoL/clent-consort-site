/* ==========================================================================
   INITIALIZATION (The Single Source of Truth)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  // Pull all the 'stops' once the DOM is ready cleanly in one loop
  initBackToTop();
  initMobileMenu();
  initGiftAidForm();
  initProjectCarousel();
});

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

/* ==========================================================================
   NAVIGATION MENU TOGGLE (Mobile Responsiveness)
   ========================================================================== */

const initMobileMenu = () => {
  const menuToggle = document.querySelector(".menu-toggle");
  const navList = document.getElementById("nav-list");

  if (!menuToggle || !navList) return;

  const toggleMenu = () => {
    const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", !isExpanded);
    navList.classList.toggle("is-open");
  };

  menuToggle.addEventListener("click", toggleMenu);

  document.addEventListener("click", (event) => {
    const isClickInsideMenu = navList.contains(event.target);
    const isClickOnToggle = menuToggle.contains(event.target);
    const isMenuOpen = navList.classList.contains("is-open");

    if (!isClickInsideMenu && !isClickOnToggle && isMenuOpen) {
      toggleMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navList.classList.contains("is-open")) {
      toggleMenu();
    }
  });
};

/* ==========================================================================
   GIFT AID VALIDATION
   ========================================================================== */

const initGiftAidForm = () => {
  const form = document.querySelector("#giftaid-form");

  if (!form) return;

  form.addEventListener("submit", function (event) {
    const postcodeField = document.querySelector("#postcode");
    if (!postcodeField) return;

    let cleanedPostcode = postcodeField.value.trim().toUpperCase();
    postcodeField.value = cleanedPostcode;

    if (cleanedPostcode.length < 5 || cleanedPostcode.length > 8) {
      event.preventDefault();
      alert(
        "Please check your input formatting. A valid UK postcode must be between 5 and 8 alphanumeric characters long.",
      );
      postcodeField.focus();
      postcodeField.style.borderColor = "#ff4d4d";
    } else {
      event.preventDefault();
      alert(
        "Success! Postcode format is valid. The form is ready for a database integration step next.",
      );
    }
  });
};

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

/* ==========================================================================
    RSVP DASHBOARD TAB SWITCHER
   ========================================================================== */
/**
 * Toggles the visibility of attendance lists and updates the active state styling of the buttons.
 *
 * @param {string|number} eventId - The unique database ID of the event section.
 * @param {string} targetTab - The target tab to display ('attending', 'absent', 'pending').
 */
function switchTab(eventId, targetTab) {
  // 1. Hide all lists for this specific event
  const lists = document.querySelectorAll(".rsvp-list-" + eventId);
  lists.forEach((list) => (list.style.display = "none"));

  // 2. Remove the solid "active" styling from all buttons for this event
  const buttons = document.querySelectorAll(".rsvp-btn-" + eventId);
  buttons.forEach((btn) => {
    btn.classList.remove("cta-button");
    btn.classList.add("cta-button-outline");
  });

  // 3. Show the target list
  const targetList = document.getElementById(
    "list-" + eventId + "-" + targetTab,
  );
  if (targetList) {
    targetList.style.display = "block";
  }

  // 4. Add the solid "active" styling to the clicked button
  const activeBtn = document.getElementById("btn-" + eventId + "-" + targetTab);
  if (activeBtn) {
    activeBtn.classList.remove("cta-button-outline");
    activeBtn.classList.add("cta-button");
  }
}
