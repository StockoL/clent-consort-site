/* ==========================================================================
    MEMBER RSVP & AVAILABILITY (member Schedule and Looking Ahead pages)
   ========================================================================== */
/**
 * Saves a member's choice as soon as they change a select, without a page
 * reload:
 *   - select.rsvp-toggle[data-attendance-id]   -> POST /rsvp/<id>/
 *   - select.poll-response-toggle[data-poll-id] -> POST /members/polling/<id>/respond/
 * The CSRF token comes from the page's #csrf_token_input.
 */

const RSVP_STATUS_CLASSES = {
  ATTENDING: "rsvp-attending",
  ABSENT: "rsvp-absent",
  PENDING: "rsvp-pending",
};

async function postJson(url, payload) {
  const csrfToken = document.getElementById("csrf_token_input").value;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function saveRsvp(select) {
  const newStatus = select.value;
  try {
    const result = await postJson(`/rsvp/${select.dataset.attendanceId}/`, {
      status: newStatus,
    });

    if (result.success) {
      // Recolour the select to match the saved status
      Object.values(RSVP_STATUS_CLASSES).forEach((cls) => select.classList.remove(cls));
      select.classList.add(RSVP_STATUS_CLASSES[newStatus]);
    } else {
      alert("Error updating RSVP. Please try again.");
    }
  } catch (error) {
    console.error("Fetch error:", error);
    alert("Network error. Could not connect to the server.");
  }
}

async function savePollResponse(select) {
  const newResponse = select.value;
  if (!newResponse) return;

  try {
    const result = await postJson(`/members/polling/${select.dataset.pollId}/respond/`, {
      response: newResponse,
    });
    if (!result.success) {
      alert("Error saving your response. Please try again.");
    }
  } catch (error) {
    console.error("Fetch error:", error);
    alert("Network error. Could not connect to the server.");
  }
}

document.addEventListener("change", (event) => {
  const select = event.target;
  if (select.matches(".rsvp-toggle[data-attendance-id]")) {
    saveRsvp(select);
  } else if (select.matches(".poll-response-toggle[data-poll-id]")) {
    savePollResponse(select);
  }
});
