/* ==========================================================================
    PROJECT TAB SWITCHER (member Schedule & Repertoire pages)
   ========================================================================== */
/**
 * Instantly switches the visible project panel and updates the active
 * state styling of the tab buttons, without a page reload.
 *
 * @param {string|number} projectId - The database ID of the Project to show.
 */
function switchProjectTab(projectId) {
  document.querySelectorAll(".project-panel").forEach((panel) => {
    panel.style.display = "none";
  });

  document.querySelectorAll(".project-tab").forEach((tab) => {
    tab.classList.remove("active");
  });

  const targetPanel = document.getElementById("project-panel-" + projectId);
  if (targetPanel) {
    targetPanel.style.display = "block";
  }

  const targetTab = document.getElementById("project-tab-" + projectId);
  if (targetTab) {
    targetTab.classList.add("active");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const requestedProjectId = new URLSearchParams(window.location.search).get(
    "project",
  );

  if (requestedProjectId && document.getElementById("project-panel-" + requestedProjectId)) {
    switchProjectTab(requestedProjectId);
  }
});
