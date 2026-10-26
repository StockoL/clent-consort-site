/* ==========================================================================
    SELECT ALL (committee inbox)
   ========================================================================== */
/**
 * input[data-select-all="<form id>"] ticks or unticks every items checkbox
 * that belongs to that form (by its form="<form id>" attribute), and
 * reflects their state back: ticked when all are, mixed when some are.
 */
const itemsFor = (formId) =>
  document.querySelectorAll(`input[type="checkbox"][name="items"][form="${formId}"]`);

document.addEventListener("change", (event) => {
  const target = event.target;

  if (target.matches("[data-select-all]")) {
    itemsFor(target.dataset.selectAll).forEach((box) => {
      box.checked = target.checked;
    });
    return;
  }

  if (target.matches('input[name="items"][form]')) {
    const formId = target.getAttribute("form");
    const toggle = document.querySelector(`[data-select-all="${formId}"]`);
    if (!toggle) return;
    const boxes = [...itemsFor(formId)];
    const ticked = boxes.filter((box) => box.checked).length;
    toggle.checked = ticked === boxes.length;
    toggle.indeterminate = ticked > 0 && ticked < boxes.length;
  }
});
