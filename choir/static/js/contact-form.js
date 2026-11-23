/* ==========================================================================
    CONTACT FORM (the public Contact page, Build Order Phase 16)
   ========================================================================== */
/**
 * One form whose Subject decides what it asks for. On load and whenever
 * Subject changes, the group that doesn't apply ([data-contact-group]:
 * "enquiry" for the message, "join" for voice type and experience) is
 * hidden and its fields disabled, so they're neither sent nor checked;
 * whatever was typed in them stays, for switching back. "required" moves
 * between Message and Voice Type, the notes that explain the groups
 * without JavaScript ([data-contact-note]) go, and the button names what
 * it does. Focus stays on Subject; the fields that change come after it.
 * The server checks the same rules (forms.ContactForm).
 */
(() => {
  const form = document.querySelector("[data-contact-form]");
  if (!form) return;
  const subject = form.querySelector('[name="subject"]');
  const message = form.querySelector('[name="message"]');
  const voicePart = form.querySelector('[name="voice_part"]');
  const button = form.querySelector("[data-contact-submit]");

  function apply() {
    const joining = subject.value === "join";
    form.querySelectorAll("[data-contact-group]").forEach((group) => {
      const shown = (group.dataset.contactGroup === "join") === joining;
      group.hidden = !shown;
      group.querySelectorAll("input, select, textarea").forEach((field) => {
        field.disabled = !shown;
      });
    });
    form.querySelectorAll("[data-contact-note]").forEach((note) => {
      note.hidden = true;
    });
    message.required = !joining;
    voicePart.required = joining;
    button.textContent = joining ? "Register Your Interest" : "Send Message";
  }

  subject.addEventListener("change", apply);
  apply();
})();
