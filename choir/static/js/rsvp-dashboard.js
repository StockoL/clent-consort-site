/* ==========================================================================
    COMMITTEE RSVP DASHBOARD
   ========================================================================== */
/**
 * Everything on committee_rsvps.html, wired by data attributes and event
 * delegation (no inline handlers):
 *   - [data-master-view="events|stats"]  switches between the two panels
 *   - select[data-project-select]        reloads the page for that project
 *   - select[data-event-select]          shows that event's lists
 *   - [data-rsvp-tab="<status>"]         switches lists within one event
 *   - select[data-rsvp-override]         saves an RSVP override and moves
 *                                        the singer to their new list
 * Panels and lists are shown and hidden with the hidden attribute.
 */

const RSVP_STATUSES = ["attending", "absent", "pending"];
const RSVP_TAB_LABELS = { attending: "Attend", absent: "Absent", pending: "Pending" };
const RSVP_ICONS = { attending: "✅", absent: "❌", pending: "⏳" };
const RSVP_EMPTY_MESSAGES = {
  attending: "No attendees confirmed yet.",
  absent: "No members have marked absent.",
  pending: "Everyone has responded. Great job!",
};

function switchMasterView(view) {
  document.getElementById("panel-events").hidden = view !== "events";
  document.getElementById("panel-stats").hidden = view !== "stats";

  document.querySelectorAll("[data-master-view]").forEach((button) => {
    const isActive = button.dataset.masterView === view;
    button.setAttribute("data-variant", isActive ? "primary" : "outline");
    button.setAttribute("aria-pressed", isActive);
  });
}

function switchEvent(eventId) {
  document.querySelectorAll(".event-wrapper").forEach((wrapper) => {
    wrapper.hidden = wrapper.id !== "event-wrapper-" + eventId;
  });
}

function switchTab(eventId, targetStatus) {
  RSVP_STATUSES.forEach((status) => {
    const list = document.getElementById(`list-${eventId}-${status}`);
    const tab = document.getElementById(`btn-${eventId}-${status}`);
    if (list) list.hidden = status !== targetStatus;
    if (tab) {
      tab.classList.toggle("active", status === targetStatus);
      tab.setAttribute("aria-pressed", status === targetStatus);
    }
  });
}

function updateLiveCounts(eventId) {
  RSVP_STATUSES.forEach((status) => {
    const container = document.getElementById(`list-${eventId}-${status}`);
    const ul = container.querySelector("ul");
    const count = ul ? ul.querySelectorAll("li").length : 0;

    const tab = document.getElementById(`btn-${eventId}-${status}`);
    if (tab) {
      tab.textContent = `${RSVP_TAB_LABELS[status]} (${count})`;
    }

    // A list that just emptied shows its empty message instead
    if (count === 0 && ul) {
      ul.remove();
      const p = document.createElement("p");
      p.className = "text-muted text-small text-center";
      p.textContent = RSVP_EMPTY_MESSAGES[status];
      container.appendChild(p);
    }
  });
}

async function overrideRsvp(select) {
  const eventId = select.dataset.eventId;
  const newStatus = select.value.toLowerCase();
  const listItem = select.closest("li");
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

  select.dataset.state = "saving";

  try {
    const response = await fetch(`/members/committee/rsvps/${select.dataset.attendanceId}/override/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ status: select.value }),
    });
    const data = await response.json();

    if (!data.success) {
      delete select.dataset.state;
      alert("Failed to update RSVP. Please refresh and try again.");
      return;
    }

    // Brief "saved" flash
    select.dataset.state = "saved";
    setTimeout(() => delete select.dataset.state, 1000);

    // Move the singer into the target list, creating it if it was empty
    const targetContainer = document.getElementById(`list-${eventId}-${newStatus}`);
    let targetUl = targetContainer.querySelector("ul");
    if (!targetUl) {
      const emptyMessage = targetContainer.querySelector("p");
      if (emptyMessage) emptyMessage.remove();
      targetUl = document.createElement("ul");
      targetUl.className = "rsvp-list text-small";
      targetContainer.appendChild(targetUl);
    }
    targetUl.appendChild(listItem);

    listItem.dataset.rsvp = newStatus;
    listItem.querySelector(".rsvp-list__icon").textContent = RSVP_ICONS[newStatus];

    updateLiveCounts(eventId);
  } catch (error) {
    console.error("Error updating RSVP:", error);
    delete select.dataset.state;
    alert("A network error occurred. Please try again.");
  }
}

document.addEventListener("click", (event) => {
  const masterButton = event.target.closest("[data-master-view]");
  if (masterButton) {
    switchMasterView(masterButton.dataset.masterView);
    return;
  }

  const tab = event.target.closest("[data-rsvp-tab]");
  if (tab) {
    switchTab(tab.dataset.eventId, tab.dataset.rsvpTab);
  }
});

document.addEventListener("change", (event) => {
  const select = event.target;
  if (select.matches("[data-project-select]")) {
    window.location.href = "?project=" + select.value;
  } else if (select.matches("[data-event-select]")) {
    switchEvent(select.value);
  } else if (select.matches("[data-rsvp-override]")) {
    overrideRsvp(select);
  }
});
