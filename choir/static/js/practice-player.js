/* ==========================================================================
    PRACTICE PLAYER (voice-part hub; Build Order Phases 7, 12 and 14a)
   ========================================================================== */
/**
 * Loop a passage, slow it down without changing pitch, and hear any note.
 * See docs/LEARNING_HUB_PLAYER.md for the design.
 *
 * - A Piece drop-down chooses among the project's pieces; the Score button
 *   opens the chosen piece's PDF, and only that piece's Downloads & links
 *   show below the player. A piece with no audio says so, and keeps its
 *   score and downloads.
 * - A piece's tracks come in groups (movements, such as a Magnificat and a
 *   Nunc Dimittis) shown as tabs, and within a group as part buttons
 *   ("Alto 1", "Full choir"). The server labels both so that no row holds
 *   two buttons with the same label. Changing part keeps the place, loop
 *   and speed, since a group's tracks share a timeline.
 * - Playback is a media element (pitch-preserving playbackRate, streams
 *   from S3, keeps playing with the screen locked) wrapped by wavesurfer.js
 *   for the waveform and the loop region, whose edges carry A and B flags.
 *   Without the file's data (no CORS) it falls back to a flat bar of the
 *   right length, and everything else works the same.
 * - The loop switch: on, playback never leaves the markers plus the
 *   lead-in (checked every animation frame; timeupdate is too coarse) and
 *   goes round again at B. Off, the markers stay put but playback ignores
 *   them and plays straight through.
 * - The marker cards show each marker's time and, where known, its bar,
 *   and move it by half a second or to the playhead. Reset loop puts the
 *   markers back at the start and end.
 * - The lead-in offers 1 bar and 2 bars when the piece has bar timings
 *   from its score data, 2 seconds and off.
 * - Each track remembers position, speed, loop, lead-in and section in
 *   localStorage, and each piece the track last used.
 * - Presigned track URLs expire; on a load error the player fetches fresh
 *   ones from the page's refreshUrl (if it has one) once and resumes.
 * - Sections (Learning Hub P2) mostly belong to the piece, so every part's
 *   track shares them; a track can also have its own, and can opt out of
 *   the piece's (pieceSections: false). Tapping one sets the markers to it.
 * - "My note" plays the loaded track's part's next note from the playhead,
 *   playing or paused, from the score data's timeline (noteTimes). Without
 *   score data it plays the starting note of the chosen section (or the
 *   piece's first).
 * - On the committee's piece page, [data-player-section] buttons loop a
 *   section, and [data-player-capture] buttons copy the playhead's time
 *   into the input named by data-player-capture. Both start hidden with
 *   data-player-show, and appear once the player has started.
 *
 * Data comes from the #player-data JSON block:
 *   { tracks: [{id, name, piece, pieceId, composer, part, voicePart, pieceSections,
 *               url, group, groupLabel, partLabel}],
 *     pieces: [{id, label, score, bars: [[seconds, bar]]}],
 *     sections: {pieceId or "track:<id>": [{id, label, bars, start, end, published, notes: {part: "E4,G4"}}]},
 *     noteTimes: {pieceId: {part: [[seconds, "E4,G4"]]}},
 *     voicePart, refreshUrl, storageKey, startPiece, startTrack,
 *     scoreStart, scoreSeconds, audioOffsetMs }
 */
(() => {
  const dataBlock = document.getElementById("player-data");
  const panel = document.querySelector("[data-player]");
  if (!dataBlock || !panel || !window.WaveSurfer || !window.WaveSurfer.Regions) return;

  const data = JSON.parse(dataBlock.textContent);
  let tracks = data.tracks || [];
  const pieces = data.pieces || [];
  if (!pieces.length) return;
  const sectionsByPiece = data.sections || {}; // by piece id, and "track:<id>" for one track's own
  const noteTimes = data.noteTimes || {}; // by piece id, then part: [[seconds, pitches]]

  const $ = (selector) => panel.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);
  const bar = document.querySelector("[data-player-bar]");

  // Lead-in setting: "bar" or "2bar" (from the piece's bar timings; 2
  // seconds without), or a number of seconds
  const FALLBACK_LEAD_IN = 2; // seconds
  const MIN_LOOP = 0.5; // seconds
  const NUDGE = 0.5; // seconds, the marker cards' − and +
  const LAST_TRACK_KEY = `cc-player:last:${data.storageKey}`;
  const LAST_PIECE_KEY = `cc-player:last-piece:${data.storageKey}`;
  const pieceTrackKey = (pieceId, group = null) =>
    `cc-player:piece:${data.storageKey}:${pieceId}${group === null ? "" : `:${group}`}`;

  // ---------------------------------------------------------------- storage
  const store = {
    get(key) {
      try {
        return JSON.parse(localStorage.getItem(key));
      } catch {
        return null;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch {
        // Private browsing or storage full: memory is a nicety, not required
      }
    },
  };

  const trackKey = (id) => `cc-player:track:${id}`;

  // ------------------------------------------------------------ formatting
  const formatTime = (seconds) => {
    if (!Number.isFinite(seconds)) return "0:00";
    const whole = Math.max(0, Math.floor(seconds));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  };

  // To the tenth of a second, for the marker cards: 64.25 -> "1:04.3"
  const formatTenths = (seconds) => {
    const tenths = Math.round(Math.max(0, seconds) * 10);
    const minutes = Math.floor(tenths / 600);
    const rest = (tenths - minutes * 600) / 10;
    return `${minutes}:${rest.toFixed(1).padStart(4, "0")}`;
  };

  // To the millisecond, as the section form takes it: 64.2 -> "1:04.200"
  const formatPrecise = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    return `${minutes}:${(seconds - minutes * 60).toFixed(3).padStart(6, "0")}`;
  };

  // ------------------------------------------------------------ the player
  const audio = document.createElement("audio");
  audio.preload = "metadata";
  audio.preservesPitch = true;
  audio.mozPreservesPitch = true;
  audio.webkitPreservesPitch = true;

  const waveHost = $("[data-player-wave]");
  const waveHeight = () => (panel.clientWidth >= 720 ? 110 : 80);
  const wavesurfer = WaveSurfer.create({
    container: waveHost,
    media: audio,
    height: waveHeight(),
    waveColor: "rgba(255, 255, 255, 0.35)",
    progressColor: "#c9a45e",
    cursorColor: "#ffffff",
    barWidth: 2,
    barGap: 1,
    barRadius: 2,
    normalize: true,
    dragToSeek: true,
  });
  const regions = wavesurfer.registerPlugin(WaveSurfer.Regions.create());

  let currentPiece = null; // the chosen piece
  let current = null; // the loaded track
  let activeSection = null; // id of the section last tapped, if any
  let loopRegion = null;
  let loopOn = false;
  let leadIn = "2";
  let pendingState = null; // restored once the track is ready
  let triedFallback = false;
  let triedRefresh = false;
  let lastSaved = 0;

  const pieceById = (id) => pieces.find((piece) => piece.id === id);
  const pieceTracks = (pieceId) => tracks.filter((track) => track.pieceId === pieceId);

  // ----------------------------------------------------------- persistence
  function currentState() {
    return {
      t: audio.currentTime,
      rate: audio.playbackRate,
      a: loopRegion ? loopRegion.start : null,
      b: loopRegion ? loopRegion.end : null,
      loop: loopOn,
      lead: leadIn,
      sec: activeSection,
    };
  }

  function saveState() {
    if (!current) return;
    store.set(trackKey(current.id), currentState());
  }

  // ------------------------------------------------------------ bar timings
  // The loaded track's bars from its piece's score data, [[seconds, bar]]:
  // none for a track with its own timing
  const trackBars = () =>
    current && current.pieceSections !== false ? (pieceById(current.pieceId) || {}).bars || [] : [];

  // The index of the bar a time falls in (a hair's grace for one exactly
  // on a bar line), or -1 before the first
  function barIndexAt(seconds, bars = trackBars()) {
    let index = -1;
    bars.forEach(([start], i) => {
      if (start <= seconds + 0.05) index = i;
    });
    return index;
  }

  // ------------------------------------------------------------- loop region
  function setLoopRegion(start, end) {
    const duration = wavesurfer.getDuration();
    start = Math.max(0, Math.min(start, duration - MIN_LOOP));
    end = Math.min(duration, Math.max(end, start + MIN_LOOP));
    if (loopRegion) {
      loopRegion.setOptions({ start, end });
    } else {
      loopRegion = regions.addRegion({ id: "loop", start, end, drag: true, resize: true });
      addFlags(loopRegion);
    }
    showLoopStyle();
    showMarkers();
  }

  // The A and B flags ride on the region's resize handles, so dragging a
  // flag drags its edge. Styled from the page through ::part()
  // (blocks/practice-player.css), since the waveform is in a shadow root.
  function addFlags(region) {
    if (!region.element) return;
    [
      ["left", "A"],
      ["right", "B"],
    ].forEach(([side, letter]) => {
      const handle = region.element.querySelector(`[part~="region-handle-${side}"]`);
      if (!handle) return;
      const flag = document.createElement("span");
      flag.setAttribute("part", `marker-flag marker-flag-${letter.toLowerCase()}`);
      flag.textContent = letter;
      handle.append(flag);
    });
  }

  function showLoopStyle() {
    waveHost.dataset.loop = loopOn ? "on" : "off";
    if (loopRegion) loopRegion.setOptions({ color: loopOn ? "rgba(201, 164, 94, 0.25)" : "rgba(0, 0, 0, 0)" });
  }

  function setLoop(on) {
    loopOn = on;
    $$("[data-player-loop]").forEach((button) => {
      button.setAttribute("aria-checked", String(on));
      const word = button.querySelector("[data-loop-word]");
      if (word) word.textContent = on ? "On" : "Off";
    });
    showLoopStyle();
    saveState();
  }

  // The lead-in in seconds before marker A, when the loop is on: one or
  // two bars back from the bar A is in (to the bar's start), or a set
  // number of seconds. Bar lead-ins without bar timings, or from the first
  // bar, are 2 seconds.
  function leadInSeconds() {
    if (!loopOn || !loopRegion) return 0;
    if (leadIn === "bar" || leadIn === "2bar") {
      const bars = trackBars();
      const index = barIndexAt(loopRegion.start, bars) - (leadIn === "2bar" ? 2 : 1);
      return bars.length && index >= 0 ? loopRegion.start - bars[index][0] : FALLBACK_LEAD_IN;
    }
    return Number(leadIn) || 0;
  }
  const rangeStart = () => Math.max(0, loopRegion.start - leadInSeconds());

  // With the loop on, playback never leaves the markers (plus the lead-in):
  // at B it goes back round, and anywhere outside the range - after a
  // seek, or the markers being moved past the playhead - it jumps to the
  // start. Checked every frame; timeupdate is too coarse. With the loop
  // off it plays through.
  function keepInRange() {
    if (loopOn && loopRegion && !audio.paused) {
      const time = audio.currentTime;
      if (time >= loopRegion.end - 0.02 || time < rangeStart() - 0.05) {
        audio.currentTime = rangeStart();
      }
    }
    requestAnimationFrame(keepInRange);
  }

  // A click on the waveform outside the range while looping goes straight
  // to the range's start, rather than being corrected a frame later
  wavesurfer.on("interaction", (newTime) => {
    if (!loopOn || !loopRegion || audio.paused) return;
    if (newTime < rangeStart() - 0.05 || newTime >= loopRegion.end - 0.02) {
      wavesurfer.setTime(rangeStart());
    }
  });

  // Pressing play from outside the range while looping starts at its start
  audio.addEventListener("play", () => {
    if (!loopOn || !loopRegion) return;
    const time = audio.currentTime;
    if (time < rangeStart() - 0.05 || time >= loopRegion.end - 0.02) {
      audio.currentTime = rangeStart();
    }
  });

  // ------------------------------------------------------------ marker cards
  // A marker's bar, when it can be said: the chosen section's own first
  // and last bars while the markers sit on it, otherwise the bar it falls
  // in from the score data ("end of bar" for B exactly on a bar line)
  function markerBar(which) {
    const section = findSection(activeSection);
    if (section && !sectionEdited(section) && section.bars) {
      const [first, last = first] = section.bars.split(/[–-]/);
      return which === "a" ? `bar ${first}` : `end of bar ${last}`;
    }
    const bars = trackBars();
    if (!bars.length || !loopRegion) return "";
    const time = which === "a" ? loopRegion.start : loopRegion.end;
    const index = barIndexAt(time, bars);
    if (index < 0) return "";
    if (which === "b" && index > 0 && Math.abs(bars[index][0] - time) <= 0.05) return `end of bar ${bars[index - 1][1]}`;
    return `bar ${bars[index][1]}`;
  }

  function showMarkers() {
    if (!loopRegion) return;
    panel.querySelectorAll("[data-marker]").forEach((card) => {
      const which = card.dataset.marker;
      card.querySelector("[data-marker-time]").textContent = formatTenths(which === "a" ? loopRegion.start : loopRegion.end);
      card.querySelector("[data-marker-bar]").textContent = markerBar(which);
    });
    markSections();
  }

  // Moves marker A or B to a time, keeping A before B by MIN_LOOP. Set to
  // now at A past B keeps the rest of the track; at B before A runs from
  // the beginning (as Loop start and Loop end used to).
  function moveMarker(which, time, { fromPlayhead = false } = {}) {
    if (!loopRegion) return;
    const duration = wavesurfer.getDuration();
    if (which === "a") {
      const end = fromPlayhead && time >= loopRegion.end - MIN_LOOP ? duration : loopRegion.end;
      setLoopRegion(Math.min(time, end - MIN_LOOP), end);
    } else {
      const start = fromPlayhead && time <= loopRegion.start + MIN_LOOP ? 0 : loopRegion.start;
      setLoopRegion(start, Math.max(time, start + MIN_LOOP));
    }
    saveState();
  }

  function resetLoop() {
    activeSection = null;
    setLoopRegion(0, wavesurfer.getDuration());
    saveState();
  }

  // ----------------------------------------------------------------- speed
  function setSpeed(percent) {
    const rate = Math.min(110, Math.max(50, percent)) / 100;
    // The default rate survives the browser resetting playbackRate when
    // the media source changes (wavesurfer swaps in the decoded file).
    audio.defaultPlaybackRate = rate;
    wavesurfer.setPlaybackRate(rate, true);
    $("[data-player-speed]").value = Math.round(rate * 100);
    $("[data-player-speed-out]").textContent = `${Math.round(rate * 100)}%`;
  }

  // ---------------------------------------------------------------- lead-in
  // Bar lead-ins are offered only when the track has bar timings
  function showLeadInChoices() {
    const select = $("[data-player-lead-in]");
    const choices = trackBars().length
      ? [["bar", "1 bar"], ["2bar", "2 bars"], ["2", "2 seconds"], ["0", "Off"]]
      : [["2", "2 seconds"], ["0", "Off"]];
    select.replaceChildren(
      ...choices.map(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        return option;
      }),
    );
    if (!choices.some(([value]) => value === leadIn)) leadIn = choices[0][0];
    select.value = leadIn;
  }

  // ----------------------------------------------------------------- pieces
  function buildPieceChoices() {
    const select = $("[data-player-piece-select]");
    select.replaceChildren(
      ...pieces.map((piece) => {
        const option = document.createElement("option");
        option.value = piece.id;
        option.textContent = piece.label;
        return option;
      }),
    );
  }

  // Chooses a piece: its score button, its downloads, and its track (the
  // given one, the one last used for it, or its first). A piece with no
  // audio keeps its score and downloads, and says it has no tracks.
  function choosePiece(pieceId, { trackId = null, autoplay = false } = {}) {
    const piece = pieceById(pieceId) || pieces[0];
    currentPiece = piece;
    store.set(LAST_PIECE_KEY, piece.id);
    $("[data-player-piece-select]").value = String(piece.id);

    const score = $("[data-player-score]");
    score.hidden = !piece.score;
    if (piece.score) score.href = piece.score;

    document.querySelectorAll("[data-downloads-piece]").forEach((block) => {
      block.hidden = Number(block.dataset.downloadsPiece) !== piece.id;
    });

    const available = pieceTracks(piece.id);
    const empty = available.length === 0;
    $("[data-player-empty]").hidden = !empty;
    panel.querySelectorAll("[data-player-needs-track]").forEach((element) => {
      element.hidden = empty;
    });
    if (empty) {
      if (current) saveState();
      wavesurfer.pause();
      current = null;
      loopRegion = null;
      regions.clearRegions();
      renderGroups();
      renderParts();
      renderSections();
      showNoteButton();
      document.querySelectorAll("[data-player-name]").forEach((el) => {
        el.textContent = piece.label;
      });
      return;
    }

    const remembered = store.get(pieceTrackKey(piece.id));
    const id = [trackId, remembered].find((candidate) => available.some((t) => t.id === candidate)) ?? available[0].id;
    loadTrack(id, { autoplay });
  }

  // ------------------------------------------------------- groups and parts
  // The groups (movements) of the chosen piece's tracks, in order
  function pieceGroups() {
    const groups = [];
    pieceTracks(current ? current.pieceId : -1).forEach((track) => {
      if (!groups.some((g) => g.key === track.group)) groups.push({ key: track.group, label: track.groupLabel });
    });
    return groups;
  }

  const groupTracks = () =>
    current ? pieceTracks(current.pieceId).filter((track) => track.group === current.group) : [];

  function renderButtons(container, items, isCurrent, dataName) {
    container.replaceChildren();
    container.hidden = items.length < 2;
    if (container.hidden) return;
    items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button btn-small";
      const pressed = isCurrent(item);
      button.dataset.variant = pressed ? "primary" : "outline";
      button.dataset[dataName] = item.value;
      button.setAttribute("aria-pressed", String(pressed));
      button.textContent = item.label;
      container.append(button);
    });
  }

  function renderGroups() {
    const groups = current ? pieceGroups() : [];
    renderButtons(
      $("[data-player-groups]"),
      groups.map((g) => ({ value: g.key, label: g.label })),
      (item) => current && item.value === current.group,
      "playerGroup",
    );
  }

  function renderParts() {
    renderButtons(
      $("[data-player-parts]"),
      groupTracks().map((t) => ({ value: t.id, label: t.partLabel })),
      (item) => current && item.value === current.id,
      "playerPart",
    );
  }

  // Another movement: its own timeline, so its own saved place
  function chooseGroup(key) {
    if (!current || key === current.group) return;
    const candidates = pieceTracks(current.pieceId).filter((track) => track.group === key);
    if (!candidates.length) return;
    const remembered = store.get(pieceTrackKey(current.pieceId, key));
    const id = candidates.some((t) => t.id === remembered) ? remembered : candidates[0].id;
    loadTrack(id, { autoplay: !audio.paused });
  }

  // Another part of the same movement: same timeline, so keep the place
  function switchPart(id) {
    if (!current || id === current.id) return;
    loadTrack(id, { carry: currentState(), autoplay: !audio.paused });
  }

  // ------------------------------------------------------------- loading
  // carry: a state to start from instead of the track's saved one (a part
  // switch keeps the place, loop and speed, since the tracks share a
  // timeline).
  function loadTrack(id, { autoplay = false, force = false, carry = null } = {}) {
    const track = tracks.find((t) => t.id === id);
    if (!track) return;

    // Already loaded: just play it. Reloading would restore the saved
    // settings over anything changed since. (force: a fresh URL.)
    if (!force && current && current.id === id && !pendingState) {
      if (autoplay) wavesurfer.play().catch(() => {});
      return;
    }

    if (current) saveState();

    current = track;
    triedFallback = false;
    triedRefresh = false;
    loopRegion = null;
    regions.clearRegions();
    pendingState = { ...(carry || store.get(trackKey(id)) || {}), autoplay };
    activeSection = trackSections().some((s) => s.id === pendingState.sec) ? pendingState.sec : null;
    store.set(LAST_TRACK_KEY, id);
    store.set(pieceTrackKey(track.pieceId), id);
    store.set(pieceTrackKey(track.pieceId, track.group), id);

    document.querySelectorAll("[data-player-name]").forEach((el) => {
      el.textContent = track.name;
    });
    $("[data-player-fallback]").hidden = true;
    renderGroups();
    renderParts();
    renderSections();
    showNoteButton();
    showLeadInChoices();

    wavesurfer.load(track.url).catch(() => {
      // Reported through the "error" event below
    });
  }

  // No waveform data (usually no CORS rule on the S3 bucket): load a flat
  // bar of the right length so the loop region and seeking still work.
  function loadWithoutWaveform() {
    triedFallback = true;
    $("[data-player-fallback]").hidden = false;
    const probe = document.createElement("audio");
    probe.preload = "metadata";
    probe.addEventListener(
      "loadedmetadata",
      () => {
        const flat = new Float32Array(512).fill(0.35);
        wavesurfer.load(current.url, [flat], probe.duration).catch(() => {});
      },
      { once: true },
    );
    probe.addEventListener("error", refreshUrls, { once: true });
    probe.src = current.url;
  }

  // Presigned URLs expire: fetch fresh ones once, then reload this track
  // where it was.
  async function refreshUrls() {
    if (triedRefresh || !current || !data.refreshUrl) return;
    triedRefresh = true;
    const resumeAt = audio.currentTime || (store.get(trackKey(current.id)) || {}).t || 0;
    try {
      const response = await fetch(data.refreshUrl, { credentials: "same-origin" });
      if (!response.ok) return;
      tracks = (await response.json()).tracks;
      const fresh = tracks.find((t) => t.id === current.id);
      if (!fresh) return;
      saveState();
      loadTrack(current.id, { force: true });
      pendingState.t = resumeAt;
      triedRefresh = true; // don't loop if the fresh URL fails too
    } catch {
      // Offline: nothing more to try
    }
  }

  wavesurfer.on("error", () => {
    if (!current) return;
    if (!triedFallback) {
      loadWithoutWaveform();
    } else {
      refreshUrls();
    }
  });

  // Where the sound starts and stops in the decoded track, in seconds:
  // the first and last 20 ms windows within 50 dB of its loudest. Null
  // without real audio data (the plain-bar fallback has none).
  function soundBounds() {
    const audioData = triedFallback ? null : wavesurfer.getDecodedData();
    if (!audioData) return null;
    const samples = audioData.getChannelData(0);
    const size = Math.max(1, Math.round(audioData.sampleRate * 0.02));
    const levels = [];
    for (let start = 0; start < samples.length; start += size) {
      let sum = 0;
      const stop = Math.min(start + size, samples.length);
      for (let i = start; i < stop; i += 1) sum += samples[i] * samples[i];
      levels.push(sum / (stop - start));
    }
    const threshold = Math.max(...levels) * 1e-5; // 50 dB below the peak
    const first = levels.findIndex((level) => level > threshold);
    if (first < 0) return null;
    const last = levels.length - 1 - [...levels].reverse().findIndex((level) => level > threshold);
    return { start: (first * size) / audioData.sampleRate, end: ((last + 1) * size) / audioData.sampleRate };
  }

  // On the committee's piece page: does the music in the loaded track
  // start and stop when the score data says it does? Silence after the
  // music doesn't matter. The same shift at both ends needs an audio
  // offset; different shifts mean different exports or tempos.
  function showAlignment(duration) {
    const note = document.querySelector("[data-score-alignment]");
    if (!note || !Number.isFinite(data.scoreSeconds) || !current) return;
    const seconds = (value) => `${value.toFixed(1)} seconds`;
    const bounds = Number.isFinite(data.scoreStart) ? soundBounds() : null;
    let message;
    if (!bounds) {
      // No audio to measure: compare lengths, which silence can upset
      const gap = duration - data.scoreSeconds;
      message = `"${current.name}" lasts ${formatTime(duration)}, and the score data's music ${formatTime(data.scoreSeconds)}.`;
      message += Math.abs(gap) < 2 ? " They match." : ` Play a section to check it lines up: silence at either end of the track would explain a difference of ${seconds(Math.abs(gap))}.`;
    } else {
      const startGap = bounds.start - data.scoreStart;
      const endGap = bounds.end - data.scoreSeconds;
      message = `In "${current.name}" the music runs from ${formatPrecise(bounds.start)} to ${formatPrecise(bounds.end)}; in the score data, from ${formatPrecise(data.scoreStart)} to ${formatPrecise(data.scoreSeconds)}.`;
      if (Math.abs(endGap - startGap) > 1.5) {
        message += ` The two drift ${seconds(Math.abs(endGap - startGap))} apart over the piece, so they're probably from different exports or tempos: export the score data and tracks again from the same version.`;
      } else if (Math.abs(startGap) <= 0.25) {
        message += " They line up." + (duration - bounds.end > 2 ? " The silence after the music doesn't matter." : "");
      } else {
        // The offset the track needs, from the score data's own timing (a
        // difference of a quarter of a second or less needs none)
        const needed = startGap + (Number(data.audioOffsetMs) || 0) / 1000;
        const offset = Math.abs(needed) <= 0.25 ? 0 : Math.round(needed * 100) * 10;
        message += ` The track's music starts ${seconds(Math.abs(startGap))} ${startGap > 0 ? "later" : "earlier"}: set the audio offset to ${offset} and import again.`;
      }
    }
    note.textContent = message;
    note.hidden = false;
  }

  wavesurfer.on("ready", (duration) => {
    const state = pendingState || {};
    pendingState = null;

    // The track's saved lead-in (one saved as the number 0 stays off), or
    // the default: 1 bar where the piece has bar timings, 2 seconds if not.
    // showLeadInChoices swaps a choice the track can't offer for its first.
    if (state.lead === 0 || state.lead === "0") leadIn = "0";
    else if (typeof state.lead === "string") leadIn = state.lead;
    else leadIn = trackBars().length ? "bar" : "2";
    showLeadInChoices();
    setLoop(Boolean(state.loop));
    setLoopRegion(Number.isFinite(state.a) ? state.a : 0, Number.isFinite(state.b) ? state.b : duration);
    setSpeed(Number.isFinite(state.rate) ? state.rate * 100 : 100);
    if (Number.isFinite(state.t) && state.t < duration) wavesurfer.setTime(state.t);

    showAlignment(duration);
    $("[data-player-duration]").textContent = formatTime(duration);
    $("[data-player-time]").textContent = formatTime(audio.currentTime);
    if (state.autoplay) wavesurfer.play().catch(() => {});
  });

  wavesurfer.on("timeupdate", (time) => {
    $("[data-player-time]").textContent = formatTime(time);
    // Remember the position every few seconds while playing
    if (Math.abs(time - lastSaved) > 3) {
      lastSaved = time;
      saveState();
    }
  });

  const showPlaying = (playing) => {
    $$("[data-player-toggle]").forEach((button) => {
      button.setAttribute("aria-label", playing ? "Pause" : "Play");
      const icon = button.querySelector("[data-player-toggle-icon]");
      const text = button.querySelector("[data-player-toggle-text]");
      if (icon) icon.textContent = playing ? "❚❚" : "▶";
      if (text) text.textContent = playing ? " Pause" : " Play";
    });
  };
  wavesurfer.on("play", () => showPlaying(true));
  wavesurfer.on("pause", () => {
    showPlaying(false);
    saveState();
  });

  regions.on("region-updated", () => {
    showMarkers();
    saveState();
  });

  // The waveform's height follows the player's width
  if ("ResizeObserver" in window) {
    let height = waveHeight();
    new ResizeObserver(() => {
      if (waveHeight() !== height) {
        height = waveHeight();
        wavesurfer.setOptions({ height });
      }
    }).observe(panel);
  }

  // ------------------------------------------------------------ note finder
  const NOTE_NAMES = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
  const SPOKEN = ["C", "C sharp", "D", "D sharp", "E", "F", "F sharp", "G", "G sharp", "A", "A sharp", "B"];
  let audioContext = null;

  function playNote(midi) {
    // Created on the first tap, which is what iOS needs to allow sound
    audioContext = audioContext || new (window.AudioContext || window.webkitAudioContext)();
    const now = audioContext.currentTime;
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = "triangle";
    oscillator.frequency.value = 440 * 2 ** ((midi - 69) / 12);
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.4, now + 0.02);
    gain.gain.setValueAtTime(0.4, now + 0.7);
    gain.gain.linearRampToValueAtTime(0, now + 0.9);
    oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.95);
  }

  function buildKeyboard() {
    const keyboard = $("[data-player-keyboard]");
    for (let midi = 48; midi <= 84; midi += 1) {
      const pitchClass = midi % 12;
      if (NOTE_NAMES[pitchClass].includes("♯")) continue; // added with its white key
      const octave = Math.floor(midi / 12) - 1;
      const slot = document.createElement("div");
      slot.className = "player-keyboard__slot";

      const white = document.createElement("button");
      white.type = "button";
      white.className = "player-keyboard__white";
      white.dataset.midi = midi;
      white.textContent = `${NOTE_NAMES[pitchClass]}${octave}`;
      white.setAttribute("aria-label", `${SPOKEN[pitchClass]} ${octave}`);
      slot.appendChild(white);

      const sharp = midi + 1;
      if (sharp <= 84 && NOTE_NAMES[sharp % 12].includes("♯")) {
        const black = document.createElement("button");
        black.type = "button";
        black.className = "player-keyboard__black";
        black.dataset.midi = sharp;
        black.setAttribute("aria-label", `${SPOKEN[sharp % 12]} ${octave}`);
        slot.appendChild(black);
      }
      keyboard.appendChild(slot);
    }
    keyboard.addEventListener("click", (event) => {
      const key = event.target.closest("[data-midi]");
      if (key) playNote(Number(key.dataset.midi));
    });
  }

  // "F#4" -> 66; null for anything that isn't a pitch
  const PITCH_CLASSES = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  function midiFor(pitch) {
    const match = /^([A-G])(#|b)?(\d)$/.exec(pitch.trim());
    if (!match) return null;
    const shift = match[2] === "#" ? 1 : match[2] === "b" ? -1 : 0;
    return 12 * (Number(match[3]) + 1) + PITCH_CLASSES[match[1]] + shift;
  }

  // -------------------------------------------------------------- sections
  // The loaded track's sections: the piece's (unless the track has its
  // own timing) followed by the track's own
  const trackSections = () => {
    if (!current) return [];
    const piece = current.pieceSections === false ? [] : sectionsByPiece[String(current.pieceId)] || [];
    return [...piece, ...(sectionsByPiece[`track:${current.id}`] || [])];
  };
  const findSection = (id) => trackSections().find((s) => s.id === id);
  const sectionEdited = (section) =>
    !loopRegion || Math.abs(loopRegion.start - section.start) > 0.05 || Math.abs(loopRegion.end - section.end) > 0.05;

  // The loaded track's part's notes in time, from the score data: none
  // for a track with its own timing, or a piece without score data
  const partTimeline = () => {
    if (!current || current.pieceSections === false) return null;
    const parts = noteTimes[String(current.pieceId)] || {};
    return parts[current.part] || parts[data.voicePart] || null;
  };

  const toMidi = (pitches) => pitches.split(",").map(midiFor).filter((midi) => midi !== null);

  // With the score data's timeline: the part's next note from the
  // playhead, playing or paused (in the loop's lead-in, the note it enters
  // on at A). Without: the chosen section's starting note, or the piece's
  // first section's.
  function notePitches() {
    const timeline = partTimeline();
    if (timeline) {
      let from = audio.currentTime;
      if (loopOn && loopRegion && from < loopRegion.start && from >= rangeStart() - 0.05) from = loopRegion.start;
      const next = timeline.find(([seconds]) => seconds >= from - 0.05);
      return next ? toMidi(next[1]) : [];
    }
    const list = trackSections();
    const section = findSection(activeSection) || [...list].sort((x, y) => x.start - y.start)[0];
    if (!section) return [];
    return toMidi(section.notes[current.part] || section.notes[data.voicePart] || "");
  }

  function showNoteButton() {
    const hasNote = current && (Boolean(partTimeline()) || notePitches().length > 0);
    $$("[data-player-note]").forEach((button) => {
      button.hidden = !hasNote;
    });
  }

  // Sets the markers to a section and plays it: from the lead-in with the
  // loop on, from the section's start with it off
  function playSection(id) {
    const section = findSection(id);
    if (!section) return;
    activeSection = id;
    setLoopRegion(section.start, section.end);
    // Tapping a section loops it, so it turns the loop on
    setLoop(true);
    wavesurfer.setTime(rangeStart());
    wavesurfer.play().catch(() => {});
    showNoteButton();
    saveState();
  }

  // Built with textContent: labels are the committee's own text
  function renderSections() {
    const fieldset = $("[data-player-sections]");
    const list = $("[data-player-section-list]");
    list.replaceChildren();
    const sections = trackSections();
    fieldset.hidden = sections.length === 0;
    sections.forEach((section) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "practice-player__section";
      button.dataset.playerSection = section.id;

      const label = document.createElement("strong");
      label.textContent = section.label;
      const meta = document.createElement("span");
      meta.className = "practice-player__section-meta";
      meta.textContent = [
        section.bars ? `bars ${section.bars}` : "",
        formatTime(section.end - section.start),
        section.published === false ? "hidden from members" : "",
      ]
        .filter(Boolean)
        .join(" · ");
      const edited = document.createElement("span");
      edited.className = "practice-player__section-edited";
      edited.dataset.sectionEdited = "";
      edited.textContent = "Edited";
      edited.hidden = true;

      button.append(label, meta, edited);
      item.append(button);
      list.append(item);
    });
    markSections();
  }

  // The chosen section is highlighted, and marked "Edited" once the
  // markers no longer match its bounds (tapping it again restores them).
  function markSections() {
    const section = findSection(activeSection);
    const edited = section ? sectionEdited(section) : false;
    panel.querySelectorAll("[data-player-section]").forEach((button) => {
      const isActive = Number(button.dataset.playerSection) === activeSection;
      button.setAttribute("aria-pressed", String(isActive));
      button.querySelector("[data-section-edited]").hidden = !(isActive && edited);
    });
  }

  // --------------------------------------------------------------- controls
  document.addEventListener("click", (event) => {
    const target = event.target.closest(
      "[data-player-toggle], [data-player-loop], [data-marker-nudge], [data-marker-now], [data-player-reset], [data-player-section], [data-player-group], [data-player-part], [data-player-note], [data-player-capture]",
    );
    if (!target) return;

    if (target.matches("[data-player-section]")) {
      playSection(Number(target.dataset.playerSection));
    } else if (target.matches("[data-player-group]")) {
      chooseGroup(target.dataset.playerGroup);
    } else if (target.matches("[data-player-part]")) {
      switchPart(Number(target.dataset.playerPart));
    } else if (target.matches("[data-player-note]")) {
      notePitches().forEach(playNote);
    } else if (target.matches("[data-player-capture]")) {
      const input = document.getElementById(target.dataset.playerCapture);
      if (input) input.value = formatPrecise(audio.currentTime);
    } else if (target.matches("[data-player-toggle]")) {
      wavesurfer.playPause().catch(() => {});
    } else if (target.matches("[data-player-loop]")) {
      setLoop(!loopOn);
    } else if (target.matches("[data-marker-nudge]") && loopRegion) {
      const which = target.closest("[data-marker]").dataset.marker;
      const from = which === "a" ? loopRegion.start : loopRegion.end;
      moveMarker(which, from + Number(target.dataset.markerNudge));
    } else if (target.matches("[data-marker-now]")) {
      moveMarker(target.closest("[data-marker]").dataset.marker, audio.currentTime, { fromPlayhead: true });
    } else if (target.matches("[data-player-reset]")) {
      resetLoop();
    }
  });

  $("[data-player-piece-select]").addEventListener("change", (event) => {
    choosePiece(Number(event.target.value), { autoplay: !audio.paused });
  });

  $("[data-player-speed]").addEventListener("input", (event) => {
    setSpeed(Number(event.target.value));
    saveState();
  });

  $("[data-player-lead-in]").addEventListener("change", (event) => {
    leadIn = event.target.value;
    saveState();
  });

  // [ and ] set markers A and B at the playhead; never while typing
  document.addEventListener("keydown", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target && target.closest("input, select, textarea, [contenteditable]")) return;
    if (event.key === "[") moveMarker("a", audio.currentTime, { fromPlayhead: true });
    if (event.key === "]") moveMarker("b", audio.currentTime, { fromPlayhead: true });
  });

  window.addEventListener("pagehide", saveState);

  // ------------------------------------------------------------------ start
  buildKeyboard();
  buildPieceChoices();
  panel.hidden = false;
  if (bar) bar.hidden = false;
  document.querySelectorAll(".player-fallback").forEach((el) => {
    el.hidden = true;
  });
  // Buttons elsewhere on the page that need the player (on the committee's
  // piece page, Play and Set from player)
  $$("[data-player-show]").forEach((button) => {
    button.hidden = false;
  });

  // Where to start: a track or piece the page asks for (?track=, ?piece=,
  // or the committee's track being edited), else the piece last used
  // here, else the first
  const startTrack = tracks.find((t) => t.id === data.startTrack);
  const lastTrack = tracks.find((t) => t.id === store.get(LAST_TRACK_KEY));
  const startPieceId =
    (startTrack && startTrack.pieceId) ??
    data.startPiece ??
    [store.get(LAST_PIECE_KEY), lastTrack && lastTrack.pieceId].find((id) => pieceById(id)) ??
    pieces[0].id;
  choosePiece(startPieceId, { trackId: startTrack ? startTrack.id : null });
  requestAnimationFrame(keepInRange);
})();
