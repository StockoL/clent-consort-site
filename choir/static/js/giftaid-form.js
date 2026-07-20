/* ==========================================================================
   GIFT AID VALIDATION
   ========================================================================== */

const initGiftAidForm = () => {
  const form = document.querySelector("#giftaid-form");

  if (!form) return;

  form.addEventListener("submit", function (event) {
    // Django's default widget ID is id_postcode (id_<field_name>), not
    // postcode - this selector never matched, so the check below never
    // actually ran in either direction (blocking or not).
    const postcodeField = document.querySelector("#id_postcode");
    if (!postcodeField) return;

    let cleanedPostcode = postcodeField.value.trim().toUpperCase();
    postcodeField.value = cleanedPostcode;

    if (cleanedPostcode.length < 5 || cleanedPostcode.length > 8) {
      // Only ever block submission on the genuinely invalid path - this
      // used to call preventDefault() unconditionally, including here on
      // the *valid* path with a placeholder "ready for a database
      // integration step next" alert, which silently discarded every
      // real submission instead of ever reaching the Django view.
      event.preventDefault();
      alert(
        "Please check your input formatting. A valid UK postcode must be between 5 and 8 alphanumeric characters long.",
      );
      postcodeField.focus();
      postcodeField.style.borderColor = "var(--colors-danger-text)";
    }
  });
};

document.addEventListener("DOMContentLoaded", initGiftAidForm);
