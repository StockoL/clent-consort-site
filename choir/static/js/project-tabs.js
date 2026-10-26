/* ==========================================================================
    PROJECT TAB SWITCHER (member Schedule & Repertoire pages)
   ========================================================================== */
/**
 * Shows one project's panel at a time when more than one project is
 * ACTIVE. Tabs are buttons with data-project-tab="<project id>"; panels
 * have id="project-panel-<project id>" and are hidden with the hidden
 * attribute. A ?project=<id> query string opens that project's tab.
 */
function switchProjectTab(projectId) {
  document.querySelectorAll(".project-panel").forEach((panel) => {
    panel.hidden = panel.id !== "project-panel-" + projectId;
  });

  document.querySelectorAll("[data-project-tab]").forEach((tab) => {
    const isActive = tab.dataset.projectTab === String(projectId);
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-pressed", isActive);
  });
}

document.addEventListener("click", (event) => {
  const tab = event.target.closest("[data-project-tab]");
  if (tab) {
    switchProjectTab(tab.dataset.projectTab);
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const requestedProjectId = new URLSearchParams(window.location.search).get(
    "project",
  );

  if (requestedProjectId && document.getElementById("project-panel-" + requestedProjectId)) {
    switchProjectTab(requestedProjectId);
  }
});
