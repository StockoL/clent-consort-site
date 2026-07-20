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
      postcodeField.style.borderColor = "var(--colors-danger-text)";
    } else {
      event.preventDefault();
      alert(
        "Success! Postcode format is valid. The form is ready for a database integration step next.",
      );
    }
  });
};

document.addEventListener("DOMContentLoaded", initGiftAidForm);
