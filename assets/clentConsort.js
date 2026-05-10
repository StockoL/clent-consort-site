/* ==========================================================================
   INITIALIZATION
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  // Pull all the 'stops' once the DOM is ready
  initContactForms();
  initBackToTop();
  initMobileMenu();
});

/* ==========================================================================
   CONTACT FORM HANDLER
   ========================================================================== */

const initContactForms = () => {
  const contactForms = document.querySelectorAll(
    ".contact-form-container form",
  );

  contactForms.forEach((form) => {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const container = this.closest(".contact-form-container");
      const isAudition = this.querySelector("#name-audition") !== null;
      const successTitle = isAudition
        ? "Application Received!"
        : "Message Sent!";
      const successBody = isAudition
        ? "Thank you for applying. Our musical director will review your experience and be in touch regarding audition slots."
        : "Thank you for reaching out. We will get back to you shortly regarding your enquiry.";

      container.innerHTML = `
                <div class="box invert l-stack" style="border-color: #4caf50; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center;" role="alert">
                  <h2 style="color: #4caf50;">${successTitle}</h2>
                  <p>${successBody}</p>
                  <div style="margin-top: var(--s1);">
                    <a href="index.html" class="cta-button">Return Home</a>
                  </div>
                </div>
            `;

      window.scrollTo({
        top: container.offsetTop - 100,
        behavior: "smooth",
      });
    });
  });
};

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
    } else {
      backToTopButton.classList.remove("is-visible");
      backToTopButton.setAttribute("aria-hidden", "true");
    }
  });

  backToTopButton.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
};

/* ==========================================================================
   MOBILE MENU TOGGLE
   ========================================================================== */

const initMobileMenu = () => {
  const toggle = document.querySelector(".menu-toggle");
  if (!toggle) return;

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", !isOpen);
  });
};
