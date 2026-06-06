/* ==========================================================================
   INITIALIZATION (The Single Source of Truth)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  // Pull all the 'stops' once the DOM is ready cleanly in one loop
  initContactForms();
  initBackToTop();
  initMobileMenu();
  initGiftAidForm(); // Added safely to the execution pipeline
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
      backToTopButton.setAttribute("tabindex", "0"); // Allow keyboard focus when visible
    } else {
      backToTopButton.classList.remove("is-visible");
      backToTopButton.setAttribute("aria-hidden", "true");
      backToTopButton.setAttribute("tabindex", "-1"); // Strip keyboard focus when hidden

      // If the button currently has focus while hiding, blur it (remove focus)
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

/* ==========================================================================
   GIFT AID VALIDATION
   ========================================================================== */

const initGiftAidForm = () => {
  const form = document.querySelector("#giftaid-form");

  // Safety net: If the user is on a page without the Gift Aid form, exit early
  if (!form) return;

  form.addEventListener("submit", function (event) {
    const postcodeField = document.querySelector("#postcode");
    if (!postcodeField) return;

    // 1. Clean the user data input string
    let cleanedPostcode = postcodeField.value.trim().toUpperCase();

    // 2. Format the local variable layout back inside the field for the user to view
    postcodeField.value = cleanedPostcode;

    // 3. Evaluate logical layout lengths (UK Postcodes run between 5 and 8 characters long)
    if (cleanedPostcode.length < 5 || cleanedPostcode.length > 8) {
      // Halt form submittal processing pipeline immediately
      event.preventDefault();

      // Fire native notification warning focus states
      alert(
        "Please check your input formatting. A valid UK postcode must be between 5 and 8 alphanumeric characters long.",
      );
      postcodeField.focus();

      // Add an explicit inline visibility border for immediate tactile alert correction
      postcodeField.style.borderColor = "#ff4d4d";
    } else {
      // SUCCESS STATE FOR PROTOTYPE TESTING:
      // If validation passes, we stop the reload for now so you can see your success
      event.preventDefault();
      alert(
        "Success! Postcode format is valid. The form is ready for a database integration step next.",
      );
    }
  });
};
