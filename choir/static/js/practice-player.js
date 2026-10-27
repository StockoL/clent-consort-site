/* ==========================================================================
    PRACTICE PLAYER (voice-part hub; Build Order Phase 7 / Learning Hub P1)
   ========================================================================== */
/**
 * Loop a section, slow it down without changing pitch, and hear any note.
 * See docs/LEARNING_HUB_PLAYER.md for the design.
 *
 * - Playback is a media element (pitch-preserving playbackRate, streams
 *   from S3, keeps playing with the screen locked) wrapped by wavesurfer.js
 *   for the waveform and the draggable loop region.
 * - The waveform needs the file fetched by the page, which S3 only allows
 *   with a CORS rule on the bucket. Without one, the player falls back to a
 *   flat bar of the right length: everything else works the same.
 * - Playback never leaves the loop range (checked every animation frame;
 *   timeupdate is too coarse): at the loop end it goes back to the loop
 *   start minus the lead-in, or stops there with loop off.
 * - Each track remembers position, speed, loop and lead-in in localStorage.
 * - Presigned track URLs expire; on a load error the player fetches fresh
 *   ones from the page's refreshUrl once and resumes.
 *
 * Data comes from the #player-data JSON block:
 *   { tracks: [{id, name, piece, composer, url}], refreshUrl, storageKey }
 */
(() => {
  const dataBlock = document.getElementById("player-data");
  const panel = document.querySelector("[data-player]");
  if (!dataBlock || !panel || !window.WaveSurfer || !window.WaveSurfer.Regions) return;

  const data = JSON.parse(dataBlock.textContent);
  let tracks = data.tracks;
  if (!tracks.length) return;

  const $ = (selector) => panel.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);
  const bar = document.querySelector("[data-player-bar]");

  const DEFAULT_LEAD_IN = 2;
  const MIN_LOOP = 0.5; // seconds
  const LAST_TRACK_KEY = `cc-player:last:${data.storageKey}`;

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

  // ------------------------------------------------------------ the player
  const audio = document.createElement("audio");
  audio.preload = "metadata";
  audio.preservesPitch = true;
  audio.mozPreservesPitch = true;
  audio.webkitPreservesPitch = true;

  const wavesurfer = WaveSurfer.create({
    container: $("[data-player-wave]"),
    media: audio,
    height: 96,
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

  let current = null; // the loaded track
  let loopRegion = null;
  let loopOn = false;
  let leadIn = DEFAULT_LEAD_IN;
  let pendingState = null; // restored once the track is ready
  let triedFallback = false;
  let triedRefresh = false;
  let lastSaved = 0;

  // ----------------------------------------------------------- persistence
  function saveState() {
    if (!current) return;
    store.set(trackKey(current.id), {
      t: audio.currentTime,
      rate: audio.playbackRate,
      a: loopRegion ? loopRegion.start : null,
      b: loopRegion ? loopRegion.end : null,
      loop: loopOn,
      lead: leadIn,
    });
  }

  // ------------------------------------------------------------- loop region
  function setLoopRegion(start, end) {
    const duration = wavesurfer.getDuration();
    start = Math.max(0, Math.min(start, duration - MIN_LOOP));
    end = Math.min(duration, Math.max(end, start + MIN_LOOP));
    if (loopRegion) {
      loopRegion.setOptions({ start, end });
    } else {
      loopRegion = regions.addRegion({
        start,
        end,
        color: "rgba(201, 164, 94, 0.25)",
        drag: true,
        resize: true,
      });
    }
    showRange();
  }

  function showRange() {
    const label = document.querySelector("[data-player-range]");
    if (!loopRegion) return;
    const whole = loopRegion.start <= 0.05 && wavesurfer.getDuration() - loopRegion.end <= 0.05;
    label.textContent = whole
      ? "Whole track"
      : `Loop ${formatTime(loopRegion.start)}–${formatTime(loopRegion.end)}`;
  }

  function setLoop(on) {
    loopOn = on;
    $$("[data-player-loop]").forEach((button) => {
      button.setAttribute("aria-pressed", on);
      button.textContent = on ? "Loop on" : "Loop off";
      if (button.dataset.variant) button.dataset.variant = on ? "primary" : "outline";
    });
    saveState();
  }

  // Playback never leaves the loop range (plus its lead-in): at the loop
  // end it goes back to the start (loop on) or stops there, rewound and
  // ready to play the section again (loop off). Anywhere outside the range
  // - after a seek, or the range being moved past the playhead - it jumps
  // to the start. Checked every frame; timeupdate is too coarse.
  const rangeStart = () => Math.max(0, loopRegion.start - leadIn);

  function keepInRange() {
    if (loopRegion && !audio.paused) {
      const time = audio.currentTime;
      if (time >= loopRegion.end - 0.02) {
        if (!loopOn) wavesurfer.pause();
        audio.currentTime = rangeStart();
      } else if (time < rangeStart() - 0.05) {
        audio.currentTime = rangeStart();
      }
    }
    requestAnimationFrame(keepInRange);
  }

  // A click on the waveform outside the range while playing goes straight
  // to the range's start, rather than being corrected a frame later (which
  // could let a few milliseconds of the wrong place be heard).
  wavesurfer.on("interaction", (newTime) => {
    if (!loopRegion || audio.paused) return;
    if (newTime < rangeStart() - 0.05 || newTime >= loopRegion.end - 0.02) {
      wavesurfer.setTime(rangeStart());
    }
  });

  // Pressing play from outside the range starts at the range's start.
  audio.addEventListener("play", () => {
    if (!loopRegion) return;
    const time = audio.currentTime;
    if (time < rangeStart() - 0.05 || time >= loopRegion.end - 0.02) {
      audio.currentTime = rangeStart();
    }
  });

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

  // ------------------------------------------------------------- loading
  function loadTrack(id, { autoplay = false, force = false } = {}) {
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
    pendingState = { ...(store.get(trackKey(id)) || {}), autoplay };
    store.set(LAST_TRACK_KEY, id);

    document.querySelectorAll("[data-player-name]").forEach((el) => {
      el.textContent = track.name;
    });
    $("[data-player-piece]").textContent = `${track.piece}${track.composer ? ` (${track.composer})` : ""}`;
    $("[data-player-fallback]").hidden = true;
    $$("[data-player-load]").forEach((button) => {
      button.setAttribute("aria-pressed", String(Number(button.dataset.playerLoad) === id));
    });

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
    if (triedRefresh || !current) return;
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

  wavesurfer.on("ready", (duration) => {
    const state = pendingState || {};
    pendingState = null;

    setLoopRegion(
      Number.isFinite(state.a) ? state.a : 0,
      Number.isFinite(state.b) ? state.b : duration,
    );
    leadIn = Number.isFinite(state.lead) ? state.lead : DEFAULT_LEAD_IN;
    $("[data-player-lead-in]").value = String(leadIn);
    setSpeed(Number.isFinite(state.rate) ? state.rate * 100 : 100);
    setLoop(Boolean(state.loop));
    if (Number.isFinite(state.t) && state.t < duration) wavesurfer.setTime(state.t);

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
    showRange();
    saveState();
  });

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

  // --------------------------------------------------------------- controls
  // Loop start/end at the playhead. A start after the current end keeps
  // the rest of the track (not a half-second sliver); an end before the
  // current start runs from the beginning.
  const setStart = () => {
    if (!loopRegion) return;
    const time = audio.currentTime;
    setLoopRegion(time, time < loopRegion.end - MIN_LOOP ? loopRegion.end : wavesurfer.getDuration());
    saveState();
  };
  const setEnd = () => {
    if (!loopRegion) return;
    const time = audio.currentTime;
    setLoopRegion(time > loopRegion.start + MIN_LOOP ? loopRegion.start : 0, time);
    saveState();
  };

  document.addEventListener("click", (event) => {
    const target = event.target.closest(
      "[data-player-toggle], [data-player-loop], [data-player-set-start], [data-player-set-end], [data-player-whole], [data-player-load]",
    );
    if (!target) return;

    if (target.matches("[data-player-load]")) {
      loadTrack(Number(target.dataset.playerLoad), { autoplay: true });
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      panel.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    } else if (target.matches("[data-player-toggle]")) {
      wavesurfer.playPause().catch(() => {});
    } else if (target.matches("[data-player-loop]")) {
      setLoop(!loopOn);
    } else if (target.matches("[data-player-set-start]")) {
      setStart();
    } else if (target.matches("[data-player-set-end]")) {
      setEnd();
    } else if (target.matches("[data-player-whole]")) {
      setLoopRegion(0, wavesurfer.getDuration());
      saveState();
    }
  });

  $("[data-player-speed]").addEventListener("input", (event) => {
    setSpeed(Number(event.target.value));
    saveState();
  });

  $("[data-player-lead-in]").addEventListener("change", (event) => {
    leadIn = Number(event.target.value);
    saveState();
  });

  // [ and ] set the loop start and end on a keyboard; never while typing
  document.addEventListener("keydown", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target && target.closest("input, select, textarea, [contenteditable]")) return;
    if (event.key === "[") setStart();
    if (event.key === "]") setEnd();
  });

  window.addEventListener("pagehide", saveState);

  // ------------------------------------------------------------------ start
  buildKeyboard();
  panel.hidden = false;
  if (bar) bar.hidden = false;
  document.querySelectorAll(".player-fallback").forEach((el) => {
    el.hidden = true;
  });
  $$("[data-player-load]").forEach((button) => {
    button.hidden = false;
  });

  const lastId = store.get(LAST_TRACK_KEY);
  loadTrack(tracks.some((t) => t.id === lastId) ? lastId : tracks[0].id);
  requestAnimationFrame(keepInRange);
})();
