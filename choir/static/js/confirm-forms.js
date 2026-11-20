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

/**
 * Saying what will happen: an element with data-fill-from="<input id>"
 * shows that input's current value as it's typed, so a page can spell out
 * its consequence and its button can name it ("Start Ewelme 2027"). Its
 * own text stays as the fallback while the input is empty, and without
 * JavaScript.
 */
document.querySelectorAll("[data-fill-from]").forEach((target) => {
  const input = document.getElementById(target.dataset.fillFrom);
  if (!input) return;
  const fallback = target.textContent;
  const fill = () => {
    target.textContent = input.value.trim() || fallback;
  };
  input.addEventListener("input", fill);
  fill();
});
