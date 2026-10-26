/* ==========================================================================
    MEMBER RSVP & AVAILABILITY (member Schedule and Looking Ahead pages)
   ========================================================================== */
/**
 * Saves a member's choice as soon as they change a select, without a page
 * reload:
 *   - select.rsvp-toggle[data-attendance-id]   -> POST /rsvp/<id>/
 *   - select.poll-response-toggle[data-poll-id] -> POST /members/polling/<id>/respond/
 *     (with the poll's note, input[data-poll-notes], which also saves when
 *     it loses focus)
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

/**
 * A poll answer is saved with its note (input[data-poll-notes]) whenever
 * either changes: the select on change, the note when it loses focus. A
 * note can't be saved before an answer is chosen, since the server stores
 * them together.
 */
async function savePollResponse(pollId) {
  const select = document.querySelector(`.poll-response-toggle[data-poll-id="${pollId}"]`);
  const notesInput = document.querySelector(`[data-poll-notes="${pollId}"]`);
  const status = document.getElementById(`poll-notes-status-${pollId}`);

  if (!select.value) {
    if (notesInput && notesInput.value.trim() && status) {
      status.textContent = "Choose your availability and your note will be saved with it.";
    }
    return;
  }

  const payload = { response: select.value };
  if (notesInput) payload.notes = notesInput.value;

  try {
    const result = await postJson(`/members/polling/${pollId}/respond/`, payload);
    if (!result.success) {
      alert("Error saving your response. Please try again.");
      return;
    }
    if (notesInput) notesInput.dataset.saved = notesInput.value;
    if (status) status.textContent = "Saved.";
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
    savePollResponse(select.dataset.pollId);
  }
});

document.addEventListener("focusout", (event) => {
  const input = event.target;
  if (!input.matches || !input.matches("[data-poll-notes]")) return;

  // Only save when the note actually changed since it was last saved
  const lastSaved = input.dataset.saved ?? input.defaultValue;
  if (input.value !== lastSaved) {
    savePollResponse(input.dataset.pollNotes);
  }
});
