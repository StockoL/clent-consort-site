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

  // 2. Remove the 'active' class from all buttons for this event
  const buttons = document.querySelectorAll(".rsvp-btn-" + eventId);
  buttons.forEach((btn) => btn.classList.remove("active"));

  // 3. Show the target list
  const targetList = document.getElementById(
    "list-" + eventId + "-" + targetTab,
  );
  if (targetList) {
    targetList.style.display = "block";
  }

  // 4. Add the 'active' class to the clicked button
  const activeBtn = document.getElementById("btn-" + eventId + "-" + targetTab);
  if (activeBtn) {
    activeBtn.classList.add("active");
  }
}

/**
 * RSVP Dashboard: Master View Switcher
 * Toggles between the Event Logistics card and the Member Overview table.
 * * @param {string} view - The requested view ('events' or 'stats')
 */
function switchMasterView(view) {
  // Toggle Panels
  document.getElementById("panel-events").style.display =
    view === "events" ? "block" : "none";
  document.getElementById("panel-stats").style.display =
    view === "stats" ? "block" : "none";

  // Toggle Button Styles
  const btnEvents = document.getElementById("master-btn-events");
  const btnStats = document.getElementById("master-btn-stats");

  if (view === "events") {
    btnEvents.className = "cta-button btn-small";
    btnStats.className = "cta-button-outline btn-small";
  } else {
    btnEvents.className = "cta-button-outline btn-small";
    btnStats.className = "cta-button btn-small";
  }
}

/**
 * RSVP Dashboard: Event Switcher
 * Swaps the visible event data within the single card structure based on the dropdown selection.
 * * @param {string} eventId - The database ID of the selected event
 */
function switchEvent(eventId) {
  // Hide all event wrappers
  const wrappers = document.querySelectorAll(".event-wrapper");
  wrappers.forEach((wrapper) => (wrapper.style.display = "none"));

  // Show the selected event wrapper (if one is selected)
  if (eventId) {
    const targetWrapper = document.getElementById("event-wrapper-" + eventId);
    if (targetWrapper) {
      targetWrapper.style.display = "block";
    }
  }
}
