/* ==========================================================================
    CONFIRM BEFORE SUBMIT (committee delete buttons)
   ========================================================================== */
/**
 * A form with data-confirm="Question?" asks before it submits, and stays
 * put if the answer is no. A submit button can carry its own data-confirm
 * instead, for forms where only one of several buttons is destructive
 * (the inbox's "Delete as spam").
 */
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form");
  if (!form) return;

  const button = event.submitter;
  const question = (button && button.dataset.confirm) || form.dataset.confirm;
  if (question && !window.confirm(question)) {
    event.preventDefault();
  }
});
