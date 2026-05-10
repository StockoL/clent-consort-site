/*  ===================================================================
  CONTACT FORM HANDLER
  This script handles the submission of both the general contact form and the audition application form.
  Since we don't have a backend to process the form submissions, we prevent the default form submission behavior and instead display a success message directly on the page.
    ==================================================================
  */
// 1. Grab ALL forms on the page
const contactForms = document.querySelectorAll(".contact-form-container form");

contactForms.forEach((form) => {
  form.addEventListener("submit", function (e) {
    // 2. Stop the 405 error for this specific form
    e.preventDefault();

    // 3. Find the container (the box) so we can replace its content
    const container = this.closest(".contact-form-container");

    // 4. Determine which message to show based on the form content
    // We check if it's the audition form or the general one
    const isAudition = this.querySelector("#name-audition") !== null;
    const successTitle = isAudition ? "Application Received!" : "Message Sent!";
    const successBody = isAudition
      ? "Thank you for applying. Our musical director will review your experience and be in touch regarding audition slots."
      : "Thank you for reaching out. We will get back to you shortly regarding your enquiry.";
    // 5. Replace the form with a success message
    container.innerHTML = `
        <div class="box invert l-stack" style="border-color: #4caf50; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center; role="alert">
          <h2 style="color: #4caf50;">${successTitle}</h2>
          <p>${successBody}</p>
          <div style="margin-top: var(--s1);">
            <a href="index.html" class="cta-button">Return Home</a>
          </div>
        </div>
      `;

    // 6. Smooth scroll to the success message
    window.scrollTo({
      top: container.offsetTop - 100,
      behavior: "smooth",
    });
  });
});

/* ==========================================================================
  BACK TO TOP FUNCTIONALITY
  ========================================================================== 
*/

const initBackToTop = () => {
  const backToTopButton = document.querySelector("#backToTop");

  if (!backToTopButton) return; // Guard clause: avoid errors if button is missing

  // Toggle visibility based on scroll position
  window.addEventListener("scroll", () => {
    if (window.scrollY > 300) {
      backToTopButton.classList.add("is-visible");
      backToTopButton.setAttribute("aria-hidden", "false");
    } else {
      backToTopButton.classList.remove("is-visible");
      backToTopButton.setAttribute("aria-hidden", "true");
    }
  });

  // Smooth scroll logic
  backToTopButton.addEventListener("click", () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  });
};

// Initialize when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", initBackToTop);
