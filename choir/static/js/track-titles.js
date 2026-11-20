// Track titles on the committee's upload form (Build Order Phase 14b).
// When files are chosen, lists each with a title box filled in with the
// title suggested from its name (from the server, the same rule the
// upload uses), and hides the single Track title field. The boxes are
// sent as file_title_<n> for the nth file. If the suggestions can't be
// fetched, the single field stays, and the server suggests on upload.
(() => {
  const list = document.querySelector("[data-track-titles]");
  if (!list) return;
  const form = list.closest("form");
  const input = form.querySelector('input[type="file"]');
  const single = form.querySelector("[data-track-title-single]");
  const rows = list.querySelector("[data-track-title-list]");
  let request = 0;

  function showSingle() {
    rows.replaceChildren();
    list.hidden = true;
    single.hidden = false;
  }

  async function suggest() {
    const files = [...input.files];
    const mine = ++request;
    if (!files.length) {
      showSingle();
      return;
    }
    const url = new URL(list.dataset.url, window.location.href);
    files.forEach((file) => url.searchParams.append("name", file.name));
    let titles;
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(response.statusText);
      titles = (await response.json()).titles;
    } catch {
      if (mine === request) showSingle();
      return;
    }
    if (mine !== request) return; // the files changed while waiting

    rows.replaceChildren();
    files.forEach((file, n) => {
      const group = document.createElement("div");
      group.className = "form-group flow flow--small";
      const label = document.createElement("label");
      label.className = "form-label text-small";
      label.htmlFor = `file-title-${n}`;
      label.textContent = `Track title for ${file.name}`;
      const box = document.createElement("input");
      box.type = "text";
      box.className = "form-control";
      box.id = `file-title-${n}`;
      box.name = `file_title_${n}`;
      box.maxLength = 60;
      box.placeholder = "Whole piece";
      box.value = titles[n] || "";
      group.append(label, box);
      rows.append(group);
    });
    single.hidden = true;
    list.hidden = false;
  }

  input.addEventListener("change", suggest);
  if (input.files.length) suggest();
})();
