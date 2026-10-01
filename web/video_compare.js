import { api } from "/scripts/api.js";
import { app } from "/scripts/app.js";
import { isAddtl } from "./director_shared.js";

const CACHE = new Map();
const LISTENERS = new Set();
const VIDEO_EXTENSIONS = /\.(?:mp4|mov|webm|mkv|avi|m4v)$/i;
const MAX_HISTORY_ITEMS = 24;
const MAX_CANDIDATES = 240;
const MAX_SCOPE_CHECKS = 24;
const MAX_RANGE = 32;

const el = (tag, text = "") => {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
};

const button = (text, fn) => {
  const element = el("button", text);
  element.type = "button";
  element.onclick = fn;
  return element;
};

function mediaUrl(entry) {
  if (!entry) return "";
  if (entry.type === "external") {
    return api.apiURL("/pixaroma/api/save_video/file?t=" + encodeURIComponent(entry.token || ""));
  }
  return api.apiURL("/view?" + new URLSearchParams({
    filename: entry.filename,
    subfolder: entry.subfolder || "",
    type: entry.type || "output",
  }));
}

function requestError(response, data) {
  const error = new Error(data?.error || `Request failed (${response.status}).`);
  error.status = response.status;
  return error;
}

async function jsonRequest(path, body, signal) {
  const response = await api.fetchApi(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw requestError(response, data);
  return data;
}

function normalizedEntry(raw) {
  if (!raw || typeof raw !== "object" || !raw.filename) return null;
  const entry = {
    filename: String(raw.filename),
    subfolder: String(raw.subfolder || "").replace(/\\/g, "/"),
    type: String(raw.type || "output"),
    format: String(raw.format || raw.mime || ""),
  };
  for (const key of ["token", "_overtli_scope", "_overtli_slot", "_overtli_label"]) {
    if (raw[key] !== undefined) entry[key] = raw[key];
  }
  for (const key of ["status", "_pixaroma_status", "_overtli_status"]) {
    if (raw[key] && typeof raw[key] === "object") entry[key] = { ...raw[key] };
  }
  if (raw._pixaroma_preview && typeof raw._pixaroma_preview === "object") {
    entry._pixaroma_preview = normalizedEntry(raw._pixaroma_preview);
  }
  if (raw._overtli_metadata && typeof raw._overtli_metadata === "object") {
    entry._overtli_metadata = raw._overtli_metadata;
  }
  return entry;
}

function identityText(entry) {
  const status = entry?._pixaroma_status || entry?.status || {};
  const externalLocation = status.folder || entry?.path || "";
  return [entry?.type || "", entry?.subfolder || "", externalLocation, entry?.filename || "", entry?.token || ""].join("\0");
}

function hash(value) {
  let result = 2166136261;
  for (let index = 0; index < value.length; index++) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return (result >>> 0).toString(16).padStart(8, "0");
}

function rootGraph(host) {
  let graph = host?.graph || app.rootGraph || app.graph;
  const seen = new Set();
  while (graph?.rootGraph && graph.rootGraph !== graph && !seen.has(graph)) {
    seen.add(graph);
    graph = graph.rootGraph;
  }
  return graph || app.rootGraph || app.graph || null;
}

function rootGraphIdentity(host) {
  const root = rootGraph(host);
  if (!root) return "graph-unavailable";
  const extra = root.extra || {};
  const explicit = [extra.overtliWorkflowId, extra.workflowId, extra.workflow_id, extra.uuid, extra.name, extra.title]
    .find(value => typeof value === "string" && value.trim());
  const graphs = [];
  const visited = new Set();
  const walk = graph => {
    if (!graph || visited.has(graph) || graphs.length >= 64) return;
    visited.add(graph);
    const nodes = (graph._nodes || []).map(node => [
      String(node.id ?? ""),
      String(node.comfyClass || node.type || ""),
      String(node.title || ""),
      node.properties?.overtliAddtl === true ? 1 : 0,
    ]).sort((a, b) => a[0].localeCompare(b[0]));
    const links = Object.values(graph.links || {}).map(link => [
      String(link?.id ?? ""), String(link?.origin_id ?? ""), String(link?.target_id ?? ""),
      String(link?.origin_slot ?? ""), String(link?.target_slot ?? ""),
    ]).sort((a, b) => a[0].localeCompare(b[0]));
    graphs.push({ nodes, links });
    for (const node of graph._nodes || []) {
      const nested = node.subgraph || app.rootGraph?.subgraphs?.get?.(node.type);
      if (nested) walk(nested);
    }
  };
  walk(root);
  const signature = JSON.stringify({ explicit: explicit || "", graphs });
  return `graph-${hash(signature)}`;
}

function graphNodes(host) {
  const root = rootGraph(host);
  const result = [];
  const seen = new Set();
  const walk = graph => {
    if (!graph || seen.has(graph) || result.length >= 4000) return;
    seen.add(graph);
    for (const node of graph._nodes || []) {
      result.push(node);
      walk(node.subgraph || app.rootGraph?.subgraphs?.get?.(node.type));
    }
  };
  walk(root);
  return result;
}

function pathIsAddtl(value) {
  const path = `/${String(value || "").replace(/\\/g, "/").replace(/^[a-z]:/i, "")}`;
  return /(?:^|\/)OvertliDS\/addtl(?:\/|$)/i.test(path);
}

function sourceScope(entry) {
  // External scope comes from backend execution/sidecar validation, never
  // from a caller-provided flag or folder label.
  if (entry?.type === "external") return null;
  return pathIsAddtl(entry?.subfolder) ? "addtl" : "normal";
}

function entryForPersistence(entry) {
  const normalized = normalizedEntry(entry);
  if (!normalized) return null;
  const keepStatus = value => {
    if (!value || typeof value !== "object") return undefined;
    const status = {};
    for (const key of ["format", "fps", "duration", "frames", "w", "h", "saved_to_disk"]) {
      if (value[key] !== undefined) status[key] = value[key];
    }
    return status;
  };
  if (normalized.status) normalized.status = keepStatus(normalized.status);
  if (normalized._pixaroma_status) normalized._pixaroma_status = keepStatus(normalized._pixaroma_status);
  if (normalized._overtli_status) normalized._overtli_status = keepStatus(normalized._overtli_status);
  delete normalized._overtli_metadata;
  delete normalized.path;
  return normalized;
}

function sourceId(entry) {
  return `media-${hash(identityText(entry))}`;
}

function makeCandidate(raw, fallback = {}) {
  const entry = normalizedEntry(raw?.entry || raw);
  if (!entry) return null;
  const origin = String(raw?.origin || fallback.origin || "Saved video");
  const label = String(raw?.label || entry._overtli_label || fallback.label || entry.filename);
  return {
    id: String(raw?.id || sourceId(entry)),
    label,
    origin,
    entry,
    scope: sourceScope(entry) || (raw?.scopeVerified === true && ["normal", "addtl"].includes(raw.scope) ? raw.scope : null),
    stale: !!raw?.stale,
    playbackOnly: entry.type === "external" && sourceScope(entry) === null
      && !(raw?.scopeVerified === true && ["normal", "addtl"].includes(raw.scope)),
  };
}

function sourceForInputPath(value) {
  const normalized = String(value || "").replace(/\\/g, "/").replace(/^\/+/, "");
  if (!VIDEO_EXTENSIONS.test(normalized)) return null;
  const slash = normalized.lastIndexOf("/");
  const filename = slash < 0 ? normalized : normalized.slice(slash + 1);
  const subfolder = slash < 0 ? "" : normalized.slice(0, slash);
  const extension = filename.slice(filename.lastIndexOf(".") + 1).toLowerCase();
  const mime = extension === "mov" ? "video/quicktime" : `video/${extension === "mkv" ? "x-matroska" : extension}`;
  return { filename, subfolder, type: "input", format: mime };
}

async function responseJson(path, signal) {
  const response = await api.fetchApi(path, { signal });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw requestError(response, data);
  return data;
}

async function historyCandidates(signal) {
  const history = await responseJson(`/history?max_items=${MAX_HISTORY_ITEMS}`, signal);
  const result = [];
  for (const [promptId, run] of Object.entries(history || {})) {
    const outputs = run?.outputs || {};
    for (const [nodeId, output] of Object.entries(outputs)) {
      const saved = output?.pixaroma_save_video;
      if (Array.isArray(saved)) {
        for (const entry of saved) result.push(makeCandidate(entry, {
          origin: "Save Video history",
          label: `${entry?._pixaroma_status?.format || "Saved"} · ${entry?.filename || nodeId}`,
        }));
      }
      const review = output?.overtli_h3_review;
      if (Array.isArray(review)) {
        for (const entry of review) result.push(makeCandidate(entry, {
          origin: "H3 wall history",
          label: entry?._overtli_label || entry?.filename || `H3 result ${promptId}`,
        }));
      }
    }
  }
  return result.filter(Boolean);
}

function checkScope(entry, expectedScope, signal) {
  return jsonRequest("/overtli/studio/video-scope", { entry, scope: expectedScope }, signal);
}

function displayTime(value) {
  if (!Number.isFinite(value) || value < 0) return "—";
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return `${minutes}:${seconds.toFixed(3).padStart(6, "0")}`;
}

function displayFrameRate(value) {
  return Number.isFinite(value) && value > 0 ? `${value.toFixed(value % 1 ? 3 : 0)} fps` : "rate unavailable";
}

export function videoCompare(host, options = {}) {
  const scope = isAddtl(host) ? "addtl" : "normal";
  const panel = el("section");
  panel.className = "ovstudio ovstudio-video-compare";
  panel.append(el("h3", options.title || "Video compare and frame review"));
  panel.append(el("div", "Select generated, saved or uploaded video sources. Frame inspection decodes the original; the browser proxy is used for playback only."));
  const state = el("div");
  state.className = "ovstudio-status";
  const columns = el("div");
  columns.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;min-width:0;min-height:0";
  const sync = document.createElement("input");
  sync.type = "checkbox";
  sync.checked = true;
  const syncLabel = el("label", "Synchronize playback and frame positions ");
  syncLabel.append(sync);
  const sourcesButton = button("Refresh saved / history sources", () => refreshSources(true));
  const toolbar = el("div");
  toolbar.className = "ovstudio-row";
  toolbar.append(syncLabel, sourcesButton);
  panel.append(toolbar, columns, state);

  const graphIdentity = rootGraphIdentity(host);
  const storageKey = `overtli.video-compare.v3:${graphIdentity}:${scope}:${String(host?.id ?? "wall")}`;
  const persist = { version: 3, scope, selected: ["", ""], source: [null, null] };
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
    if (saved?.scope === scope && Array.isArray(saved.selected) && Array.isArray(saved.source)) {
      persist.selected = saved.selected.slice(0, 2).map(value => String(value || ""));
      persist.source = saved.source.slice(0, 2);
    }
  } catch { /* Browser storage can be disabled; the current session still works. */ }

  const records = [];
  const allCandidates = new Map();
  let refreshGeneration = 0;
  let disposed = false;
  let syncLock = false;
  let syncUnlockTimer = 0;
  let verifyController = null;
  let refreshController = null;

  const writePersist = () => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(persist));
    } catch { /* Large/private browser storage is optional. */ }
  };

  const assignStatus = value => { if (!disposed) state.textContent = value; };

  const unscopedExternal = candidate => candidate?.entry?.type === "external" && candidate.scope === null;

  function setFrameControls(record, enabled) {
    for (const control of [record.slider, record.indexInput, record.stepBack, record.stepForward,
      record.startInput, record.endInput, record.singleButton, record.exportButton]) {
      control.disabled = !enabled;
    }
  }

  const addCandidate = raw => {
    const candidate = makeCandidate(raw);
    if (!candidate || (candidate.scope !== scope && !unscopedExternal(candidate))) return false;
    if (!VIDEO_EXTENSIONS.test(candidate.entry.filename)) return false;
    const current = allCandidates.get(candidate.id);
    if (!current || (current.scope === null && candidate.scope !== null)) allCandidates.set(candidate.id, candidate);
    return true;
  };

  function savedNodeCandidates() {
    const result = [];
    for (const node of graphNodes(host)) {
      if (!/(?:PixaromaSaveVideo|OvertliDirectorSaveVideo)/.test(node.comfyClass || node.type || "")) continue;
      const id = String(node.id);
      const cached = CACHE.get(id);
      const entries = Array.isArray(cached) && cached.length
        ? cached
        : [node.properties?.overtliVideoLastRun || node.properties?.pixSvLastRun].filter(Boolean);
      for (const entry of entries) result.push(makeCandidate(entry, {
        origin: node.title || "Saved video node",
        label: `${node.title || id} · ${entry._pixaroma_status?.format || entry.status?.format || "Saved"} · ${entry.filename || "video"}`,
      }));
    }
    return result.filter(Boolean);
  }

  async function verifyExternal(candidates, generation) {
    const unknown = candidates.filter(candidate => candidate.scope === null && candidate.entry.type === "external").slice(0, MAX_SCOPE_CHECKS);
    verifyController?.abort();
    verifyController = new AbortController();
    const signal = verifyController.signal;
    let cursor = 0;
    let verifiedCount = 0;
    const workers = Array.from({ length: Math.min(4, unknown.length) }, async () => {
      while (cursor < unknown.length && !signal.aborted) {
        const item = unknown[cursor++];
        try {
          const data = await checkScope(item.entry, scope, signal);
          if (generation !== refreshGeneration || disposed) return;
          if (data.scope === scope) {
            item.scope = data.scope;
            item.scopeVerified = true;
            delete item.entry._overtli_scope;
            if (addCandidate(item)) verifiedCount++;
          }
        } catch (error) {
          if (error.status === 403) allCandidates.delete(item.id);
          // Known opposite-island outputs are removed; unknown legacy tokens
          // remain available for playback only and cannot pass frame review.
        }
      }
    });
    await Promise.all(workers);
    return verifiedCount;
  }

  async function refreshSources(userRequested = false) {
    if (disposed) return;
    const generation = ++refreshGeneration;
    refreshController?.abort();
    refreshController = new AbortController();
    const signal = refreshController.signal;
    verifyController?.abort();
    allCandidates.clear();
    assignStatus("Loading current wall, saved output, history and uploaded video sources…");
    sourcesButton.disabled = true;
    const additions = [];
    try {
      const provided = options.sourceProvider ? await options.sourceProvider(signal) : [];
      for (const source of Array.isArray(provided) ? provided : []) {
        const candidate = makeCandidate(source, { origin: "H3 Review Wall" });
        if (candidate) additions.push(candidate);
      }
    } catch (error) {
      additions.push(null);
      assignStatus(`Could not read the current H3 wall sources: ${error.message}`);
    }
    if (disposed || generation !== refreshGeneration) return;
    additions.push(...savedNodeCandidates());

    const [historyResult, filesResult] = await Promise.allSettled([
      historyCandidates(signal),
      responseJson(`/overtli/studio/files?addtl=${scope === "addtl" ? 1 : 0}`, signal),
    ]);
    if (disposed || generation !== refreshGeneration) return;
    if (historyResult.status === "fulfilled") additions.push(...historyResult.value);
    if (filesResult.status === "fulfilled") {
      for (const path of filesResult.value.files || []) {
        const entry = sourceForInputPath(path);
        if (entry) additions.push(makeCandidate(entry, { origin: "Uploaded input", label: path }));
      }
    }
    for (const source of additions) addCandidate(source);

    // Scope-check external tokens against executed-save/sidecar evidence.
    // Unknown tokens stay playback-only; known opposite-island media is removed.
    const externalToCheck = additions.filter(source => source?.scope === null && source.entry?.type === "external");
    const verified = await verifyExternal(externalToCheck, generation);
    if (disposed || generation !== refreshGeneration) return;

    for (let index = 0; index < 2; index++) {
      const saved = persist.source[index];
      const selectedId = persist.selected[index];
      if (!selectedId || allCandidates.has(selectedId) || !saved || saved.scope !== scope) continue;
      const candidate = makeCandidate({ ...saved, stale: true });
      if (candidate && (candidate.scope === scope || unscopedExternal(candidate))) allCandidates.set(candidate.id, candidate);
    }
    const candidates = [...allCandidates.values()].slice(0, MAX_CANDIDATES);
    for (const record of records) {
      const prior = record.choose.value || persist.selected[record.index];
      record.choose.replaceChildren(el("option", "Select a video source"));
      record.choose.firstChild.value = "";
      for (const candidate of candidates) {
        const origin = candidate.playbackOnly
          ? "Playback only · scope unverified"
          : candidate.stale ? "Saved selection may be unavailable" : candidate.origin;
        const option = el("option", `${origin} · ${candidate.label}`);
        option.value = candidate.id;
        record.choose.append(option);
      }
      if (prior && candidates.some(candidate => candidate.id === prior)) record.choose.value = prior;
    }

    if (historyResult.status === "rejected" || filesResult.status === "rejected") {
      const failures = [historyResult, filesResult].filter(result => result.status === "rejected").length;
      assignStatus(`${candidates.length} source(s) available. ${failures} source listing request(s) failed; use Refresh to retry.`);
    } else if (externalToCheck.length > verified) {
      assignStatus(`${candidates.length} source(s) available. Unverified legacy external videos are playback only; upload one into this wall's input island for frame review.`);
    } else {
      assignStatus(candidates.length ? `${candidates.length} Normal/Addtl-scoped video source(s) available.` : "No saved, historical or uploaded video sources in this wall's island yet.");
    }
    sourcesButton.disabled = false;

    for (const record of records) {
      const selected = record.choose.value || persist.selected[record.index];
      const candidate = allCandidates.get(selected);
      if (candidate && !record.candidate) await loadCandidate(record, candidate, { persist: false });
    }
    if (userRequested && !candidates.length) assignStatus("No video sources were found in this Normal/Addtl island.");
  }

  function selectCandidate(record, candidate) {
    persist.selected[record.index] = candidate.id;
    persist.source[record.index] = {
      id: candidate.id,
      label: candidate.label,
      origin: candidate.origin,
      scope,
      entry: entryForPersistence(candidate.entry),
    };
    writePersist();
  }

  async function loadCandidate(record, candidate, { persist: saveSelection = true } = {}) {
    if (disposed || (candidate.scope !== scope && !unscopedExternal(candidate))) {
      assignStatus(`This source does not belong to the ${scope === "addtl" ? "Addtl" : "Normal"} wall.`);
      return;
    }
    const generation = ++record.loadGeneration;
    record.inspectController?.abort();
    record.frameController?.abort();
    record.proxyController?.abort();
    record.extractController?.abort();
    clearTimeout(record.scrubTimer);
    clearTimeout(record.suppressSeekTimer);
    record.frameImage.onload = null;
    record.frameImage.onerror = null;
    record.candidate = candidate;
    record.entry = candidate.entry;
    record.videoInfo = null;
    record.frameIndex = 0;
    record.proxyTried = false;
    record.exportGeneration++;
    record.exporting = false;
    setFrameControls(record, false);
    record.video.pause();
    record.video.removeAttribute("src");
    record.video.load();
    record.indexInput.value = "0";
    record.slider.value = "0";
    record.slider.max = "0";
    record.frameImage.removeAttribute("src");
    if (record.objectUrl) URL.revokeObjectURL(record.objectUrl);
    record.objectUrl = "";
    record.frameCaption.textContent = "Select a source to scrub exact frames.";
    record.infoElement.textContent = candidate.playbackOnly
      ? "Scope is unverified. Playback is available; upload this video into the selected input island for frame review."
      : "Reading original media metadata…";
    record.metadataText.textContent = JSON.stringify(candidate.entry._overtli_metadata || {
      note: "Older output has no Director metadata sidecar.",
      generation: candidate.entry.status || candidate.entry._pixaroma_status || {},
    }, null, 2);
    if (saveSelection) selectCandidate(record, candidate);
    assignStatus(candidate.stale ? "Rechecking the saved selection; a missing temporary preview will be reported here." : `Loading ${candidate.label}…`);
    record.video.onerror = () => handleVideoError(record, generation);
    record.video.onloadedmetadata = () => {
      if (generation !== record.loadGeneration) return;
      if (!record.videoInfo) record.infoElement.textContent = `${record.entry.filename} · ${record.video.videoWidth}×${record.video.videoHeight} · ${displayTime(record.video.duration)}`;
    };

    record.inspectController = new AbortController();
    const inspect = jsonRequest("/overtli/studio/video-inspect", { entry: record.entry, scope }, record.inspectController.signal)
      .then(async data => {
        if (disposed || generation !== record.loadGeneration) return;
        if (data.scope !== scope) throw new Error("The backend did not confirm this video's Normal/Addtl scope.");
        if (candidate.playbackOnly) {
          candidate.scope = data.scope;
          candidate.scopeVerified = true;
          candidate.playbackOnly = false;
          allCandidates.set(candidate.id, candidate);
          rebuildOptions();
        }
        record.videoInfo = data;
        setFrameControls(record, true);
        record.slider.max = String(Math.max(0, data.frame_count - 1));
        record.indexInput.max = record.slider.max;
        record.startInput.max = record.slider.max;
        record.endInput.max = record.slider.max;
        record.endInput.value = record.slider.max;
        const rate = data.avg_fps ? `avg ${displayFrameRate(data.avg_fps)}` : displayFrameRate(data.nominal_fps);
        const nominal = data.nominal_fps && data.avg_fps && Math.abs(data.nominal_fps - data.avg_fps) > 0.005
          ? ` · nominal ${displayFrameRate(data.nominal_fps)}` : "";
        record.infoElement.textContent = `${record.entry.filename} · ${data.width}×${data.height} · ${data.frame_count} frames · ${rate}${nominal} · ${displayTime(data.duration)}`;
        assignStatus(`Exact source frame indexing ready for ${record.entry.filename}.`);
        const ratio = record.restoreRatio ?? 0;
        record.restoreRatio = null;
        setFrameIndex(record, Math.round(ratio * Math.max(0, data.frame_count - 1)), false, true);
      }).catch(error => {
        if (!disposed && generation === record.loadGeneration) {
          setFrameControls(record, false);
          record.infoElement.textContent = candidate.playbackOnly
            ? "Scope is unverified. Upload this video into the selected Normal/Addtl input island before exact frame review or extraction."
            : `Frame review unavailable: ${error.message}`;
          record.frameCaption.textContent = candidate.playbackOnly
            ? "Playback proxy only. Upload into this wall's input island to decode source frames."
            : "Source frames could not be inspected.";
        }
        throw error;
      });
    const play = attachPlayback(record, generation);
    const results = await Promise.allSettled([inspect, play]);
    if (disposed || generation !== record.loadGeneration) return;
    const failure = results.find(result => result.status === "rejected" && result.reason?.name !== "AbortError");
    if (failure) assignStatus(`Could not load ${candidate.label}: ${failure.reason.message}`);
  }

  async function attachPlayback(record, generation) {
    record.proxyController = new AbortController();
    record.proxyTried = true;
    const playback = await requestProxy(record.entry, record.proxyController.signal);
    if (disposed || generation !== record.loadGeneration) return;
    record.video.src = mediaUrl(playback || record.entry);
    record.video.load();
  }

  async function requestProxy(entry, signal) {
    assignStatus("Preparing browser playback proxy; the original remains the extraction source…");
    const data = await jsonRequest("/overtli/studio/video-proxy", entry, signal);
    if (!data.preview) throw new Error("The browser playback proxy returned no preview media.");
    return data.preview;
  }

  async function handleVideoError(record, generation) {
    if (disposed || generation !== record.loadGeneration || !record.entry) return;
    if (record.proxyTried) {
      assignStatus("The playback proxy could not be played by this browser.");
      return;
    }
    record.proxyTried = true;
    record.proxyController?.abort();
    record.proxyController = new AbortController();
    try {
      const preview = await requestProxy(record.entry, record.proxyController.signal);
      if (disposed || generation !== record.loadGeneration) return;
      record.video.src = mediaUrl(preview);
      record.video.load();
    } catch (error) {
      if (error.name !== "AbortError") assignStatus(`Playback proxy failed: ${error.message}`);
    }
  }

  async function showFrame(record, generation) {
    if (!record.entry || !record.videoInfo || disposed || generation !== record.loadGeneration) return;
    record.frameController?.abort();
    record.frameController = new AbortController();
    const frameGeneration = record.frameGeneration = record.frameGeneration + 1;
    record.frameCaption.textContent = `Decoding source frame ${record.frameIndex}…`;
    try {
      const response = await api.fetchApi("/overtli/studio/video-frame", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry: record.entry, scope, frame_index: record.frameIndex }),
        signal: record.frameController.signal,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw requestError(response, data);
      }
      const blob = await response.blob();
      if (disposed || generation !== record.loadGeneration || frameGeneration !== record.frameGeneration) return;
      const timestamp = Number(response.headers.get("X-Overtli-Frame-Timestamp"));
      const nextUrl = URL.createObjectURL(blob);
      const previousUrl = record.objectUrl;
      record.objectUrl = nextUrl;
      record.frameImage.onload = () => {
        if (disposed || generation !== record.loadGeneration || frameGeneration !== record.frameGeneration) {
          URL.revokeObjectURL(nextUrl);
          return;
        }
        if (previousUrl && previousUrl !== record.objectUrl) URL.revokeObjectURL(previousUrl);
      };
      record.frameImage.onerror = () => {
        if (disposed || generation !== record.loadGeneration || frameGeneration !== record.frameGeneration) {
          URL.revokeObjectURL(nextUrl);
          return;
        }
        if (previousUrl) URL.revokeObjectURL(previousUrl);
        assignStatus("The decoded frame image could not be displayed by this browser.");
      };
      record.frameImage.src = nextUrl;
      record.frameCaption.textContent = Number.isFinite(timestamp)
        ? `Source frame ${record.frameIndex} · ${displayTime(timestamp)} · ${record.videoInfo.width}×${record.videoInfo.height}`
        : `Source frame ${record.frameIndex} · ${record.videoInfo.width}×${record.videoInfo.height}`;
      if (Number.isFinite(timestamp) && Number.isFinite(record.video.duration)) {
        const sourceStart = Number.isFinite(record.videoInfo.start_time) ? record.videoInfo.start_time : 0;
        const playbackTime = timestamp - sourceStart;
        record.video.currentTime = Math.max(0, Math.min(playbackTime, Math.max(0, record.video.duration - 0.001)));
        record.suppressSeekSync = true;
        clearTimeout(record.suppressSeekTimer);
        record.suppressSeekTimer = setTimeout(() => { record.suppressSeekSync = false; }, 250);
      }
    } catch (error) {
      if (error.name !== "AbortError" && !disposed && generation === record.loadGeneration) {
        record.frameCaption.textContent = "Frame preview unavailable.";
        assignStatus(`Could not decode source frame ${record.frameIndex}: ${error.message}`);
      }
    }
  }

  function setFrameIndex(record, index, synchronize = true, immediate = false) {
    if (!record.videoInfo || !Number.isFinite(index)) return;
    const max = Math.max(0, record.videoInfo.frame_count - 1);
    record.frameIndex = Math.max(0, Math.min(max, Math.floor(index)));
    record.slider.value = String(record.frameIndex);
    record.indexInput.value = String(record.frameIndex);
    const generation = record.loadGeneration;
    clearTimeout(record.scrubTimer);
    if (immediate) showFrame(record, generation);
    else record.scrubTimer = setTimeout(() => showFrame(record, generation), 110);
    if (!synchronize || !sync.checked || syncLock) return;
    const other = records.find(item => item !== record);
    if (!other?.videoInfo) return;
    syncLock = true;
    const position = max > 0 ? record.frameIndex / max : 0;
    setFrameIndex(other, Math.round(position * Math.max(0, other.videoInfo.frame_count - 1)), false, immediate);
    syncLock = false;
  }

  async function exportFrames(record, indices) {
    if (!record.entry || !record.videoInfo || record.exporting) return;
    if (indices.length > MAX_RANGE) {
      assignStatus(`Choose a range of no more than ${MAX_RANGE} frames.`);
      return;
    }
    record.extractController?.abort();
    record.extractController = new AbortController();
    const loadGeneration = record.loadGeneration;
    const exportGeneration = ++record.exportGeneration;
    record.exporting = true;
    record.cancelExport.hidden = false;
    record.exportButton.disabled = true;
    record.singleButton.disabled = true;
    record.cancelExport.disabled = false;
    assignStatus(`Extracting ${indices.length} exact source frame(s)…`);
    try {
      const result = await jsonRequest("/overtli/studio/video-frames/extract", {
        entry: record.entry,
        scope,
        frame_indices: indices,
      }, record.extractController.signal);
      if (disposed || loadGeneration !== record.loadGeneration || exportGeneration !== record.exportGeneration) return;
      record.exportList.replaceChildren();
      for (const frame of result.frames || []) {
        const line = el("div", `${frame.filename} · frame ${frame.frame_index} · ${displayTime(frame.timestamp)} · ${frame.raster.width}×${frame.raster.height}`);
        record.exportList.append(line);
      }
      assignStatus(`Exported ${(result.frames || []).length} PNG frame(s) to input/${result.frames?.[0]?.subfolder || "frames"}.`);
    } catch (error) {
      if (loadGeneration === record.loadGeneration && exportGeneration === record.exportGeneration) {
        if (error.name === "AbortError") assignStatus("Frame extraction cancelled.");
        else assignStatus(`Frame extraction failed: ${error.message}`);
      }
    } finally {
      if (exportGeneration === record.exportGeneration) {
        record.exporting = false;
        record.cancelExport.hidden = true;
        record.exportButton.disabled = false;
        record.singleButton.disabled = false;
        record.cancelExport.disabled = true;
      }
    }
  }

  function uploadVideo(record) {
    if (record.fileInput || disposed) return;
    const fileInput = el("input");
    fileInput.type = "file";
    fileInput.accept = "video/*,.mov,.mkv,.avi,.m4v";
    fileInput.hidden = true;
    columns.append(fileInput);
    record.fileInput = fileInput;
    const uploadGeneration = ++record.uploadGeneration;
    const releaseInput = () => {
      fileInput.onchange = null;
      fileInput.oncancel = null;
      fileInput.remove();
      if (record.fileInput === fileInput) record.fileInput = null;
    };
    fileInput.oncancel = releaseInput;
    fileInput.onchange = async () => {
      const file = fileInput.files?.[0];
      releaseInput();
      if (!file) return;
      const form = new FormData();
      form.append("image", file, file.name);
      form.append("type", "input");
      form.append("subfolder", scope === "addtl" ? "OvertliDS/addtl/compare" : "OvertliDS/references/compare");
      assignStatus(`Uploading ${file.name} to the ${scope === "addtl" ? "Addtl" : "Normal"} input island…`);
      record.uploadController?.abort();
      record.uploadController = new AbortController();
      try {
        const response = await api.fetchApi("/upload/image", { method: "POST", body: form, signal: record.uploadController.signal });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw requestError(response, data);
        if (disposed || uploadGeneration !== record.uploadGeneration) return;
        const entry = { filename: data.name || file.name, subfolder: data.subfolder || "", type: "input", format: file.type };
        const candidate = makeCandidate(entry, { origin: "Uploaded now", label: entry.filename });
        addCandidate(candidate);
        rebuildOptions();
        record.choose.value = candidate.id;
        await loadCandidate(record, candidate);
      } catch (error) {
        if (error.name !== "AbortError" && !disposed && uploadGeneration === record.uploadGeneration) assignStatus(`Video upload failed: ${error.message}`);
      }
    };
    fileInput.click();
  }

  function rebuildOptions() {
    const candidates = [...allCandidates.values()].slice(0, MAX_CANDIDATES);
    for (const record of records) {
      const selected = record.choose.value || persist.selected[record.index];
      record.choose.replaceChildren(el("option", "Select a video source"));
      record.choose.firstChild.value = "";
      for (const candidate of candidates) {
        const option = el("option", `${candidate.origin}${candidate.stale ? " · saved; source may be offline" : ""} · ${candidate.label}`);
        option.value = candidate.id;
        record.choose.append(option);
      }
      if (selected && candidates.some(candidate => candidate.id === selected)) record.choose.value = selected;
    }
  }

  function buildColumn(index) {
    const column = el("div");
    const choose = el("select");
    choose.setAttribute("aria-label", `Video source ${index + 1}`);
    const video = el("video");
    video.className = "ovstudio-video";
    video.controls = true;
    video.preload = "metadata";
    video.playsInline = true;
    const info = el("div");
    info.className = "ovstudio-status";
    const meta = el("details");
    meta.append(el("summary", "Prompt / generation metadata"));
    const metadataText = el("pre");
    metadataText.style.cssText = "white-space:pre-wrap;overflow-wrap:anywhere;max-height:150px;overflow:auto";
    meta.append(metadataText);

    const frameStage = el("div");
    frameStage.style.cssText = "background:#050a0d;border:1px solid #385263;border-radius:5px;min-height:120px;display:flex;align-items:center;justify-content:center;overflow:hidden;margin:6px 0";
    const frameImage = el("img");
    frameImage.alt = `Exact source frame preview ${index + 1}`;
    frameImage.style.cssText = "display:block;max-width:100%;max-height:270px;object-fit:contain";
    frameStage.append(frameImage);
    const frameCaption = el("div", "Select a source to scrub exact frames.");
    frameCaption.className = "ovstudio-status";

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "0";
    slider.value = "0";
    slider.setAttribute("aria-label", `Exact frame index ${index + 1}`);
    slider.style.width = "100%";
    const indexInput = document.createElement("input");
    indexInput.type = "number";
    indexInput.min = "0";
    indexInput.max = "0";
    indexInput.value = "0";
    indexInput.setAttribute("aria-label", `Frame index ${index + 1}, zero based`);
    indexInput.style.width = "90px";
    const stepBack = button("Frame −", () => setFrameIndex(record, record.frameIndex - 1, true, true));
    const stepForward = button("Frame +", () => setFrameIndex(record, record.frameIndex + 1, true, true));
    const frameControls = el("div");
    frameControls.className = "ovstudio-row";
    frameControls.append(indexInput, stepBack, stepForward);

    const startInput = document.createElement("input");
    startInput.type = "number";
    startInput.min = "0";
    startInput.max = "0";
    startInput.value = "0";
    startInput.setAttribute("aria-label", `First frame to export ${index + 1}`);
    startInput.style.width = "82px";
    const endInput = document.createElement("input");
    endInput.type = "number";
    endInput.min = "0";
    endInput.max = "0";
    endInput.value = "0";
    endInput.setAttribute("aria-label", `Last frame to export ${index + 1}`);
    endInput.style.width = "82px";
    const singleButton = button("Export current frame", () => exportFrames(record, [record.frameIndex]));
    const exportButton = button("Export frame range", () => {
      const first = Number(startInput.value), last = Number(endInput.value);
      if (!Number.isInteger(first) || !Number.isInteger(last) || first > last) {
        assignStatus("Enter a valid zero-based frame range with the first index at or before the last.");
        return;
      }
      if (!record.videoInfo || first < 0 || last >= record.videoInfo.frame_count) {
        assignStatus("Choose a frame range inside the inspected source video.");
        return;
      }
      if (last - first + 1 > MAX_RANGE) {
        assignStatus(`Choose a range of no more than ${MAX_RANGE} frames.`);
        return;
      }
      exportFrames(record, Array.from({ length: last - first + 1 }, (_, offset) => first + offset));
    });
    const cancelExport = button("Cancel export", () => record.extractController?.abort());
    cancelExport.hidden = true;
    cancelExport.disabled = true;
    const rangeControls = el("div");
    rangeControls.className = "ovstudio-row";
    rangeControls.append(el("span", "Export frames"), startInput, el("span", "through"), endInput, singleButton, exportButton, cancelExport);
    const exportList = el("div");
    exportList.className = "ovstudio-status";

    const uploadButton = button("Upload comparison video", () => uploadVideo(record));
    const selectControls = el("div");
    selectControls.className = "ovstudio-row";
    selectControls.append(choose, uploadButton);
    column.append(selectControls, video, info, meta, frameStage, frameCaption, slider, frameControls, rangeControls, exportList);
    const record = {
      index, column, choose, video, info, metadataText, frameImage, frameCaption,
      slider, indexInput, stepBack, stepForward, startInput, endInput, singleButton, exportButton, cancelExport, exportList,
      loadGeneration: 0, frameGeneration: 0, uploadGeneration: 0, frameIndex: 0,
      inspectController: null, frameController: null, proxyController: null, extractController: null, uploadController: null,
      candidate: null, entry: null, videoInfo: null, objectUrl: "", scrubTimer: null, exporting: false,
      exportGeneration: 0, fileInput: null, listeners: [], suppressSeekTimer: 0,
    };
    record.infoElement = info;
    setFrameControls(record, false);
    choose.onchange = () => {
      const candidate = allCandidates.get(choose.value);
      if (candidate) {
        record.uploadGeneration++;
        record.uploadController?.abort();
        loadCandidate(record, candidate);
      }
    };
    slider.oninput = () => setFrameIndex(record, Number(slider.value));
    indexInput.onchange = () => setFrameIndex(record, Number(indexInput.value), true, true);
    stepBack.onclick = () => setFrameIndex(record, record.frameIndex - 1, true, true);
    stepForward.onclick = () => setFrameIndex(record, record.frameIndex + 1, true, true);
    records.push(record);
    columns.append(column);
    return record;
  }

  // Build the two synchronized source columns after their helpers are defined.
  const left = buildColumn(0);
  const right = buildColumn(1);

  function bindPlaybackSync(record) {
    const other = records.find(item => item !== record);
    if (!other) return;
    const listen = (name, listener) => {
      record.video.addEventListener(name, listener);
      record.listeners.push(() => record.video.removeEventListener(name, listener));
    };
    listen("seeked", () => {
      if (!sync.checked || record.suppressSeekSync || syncLock || !other.video.src || !Number.isFinite(record.video.duration) || !Number.isFinite(other.video.duration)) return;
      const ratio = record.video.duration > 0 ? record.video.currentTime / record.video.duration : 0;
      const next = Math.max(0, Math.min(other.video.duration, ratio * other.video.duration));
      if (Math.abs(other.video.currentTime - next) < 0.08) return;
      syncLock = true;
      other.video.currentTime = next;
      clearTimeout(syncUnlockTimer);
      syncUnlockTimer = setTimeout(() => { syncLock = false; }, 100);
    });
    listen("play", () => {
      if (sync.checked && other.video.src) other.video.play().catch(error => assignStatus(`Click the other player to start synchronized playback: ${error.message}`));
    });
    listen("pause", () => { if (sync.checked) other.video.pause(); });
    listen("ratechange", () => { if (sync.checked) other.video.playbackRate = record.video.playbackRate; });
  }
  bindPlaybackSync(left);
  bindPlaybackSync(right);

  const changed = () => {
    if (disposed) return;
    if (panel.isConnected) refreshSources();
  };
  LISTENERS.add(changed);
  panel.refreshSources = refreshSources;
  panel.dispose = () => {
    if (disposed) return;
    disposed = true;
    refreshGeneration++;
    verifyController?.abort();
    refreshController?.abort();
    clearTimeout(syncUnlockTimer);
    syncLock = false;
    LISTENERS.delete(changed);
    for (const record of records) {
      record.loadGeneration++;
      record.uploadGeneration++;
      record.exportGeneration++;
      clearTimeout(record.scrubTimer);
      clearTimeout(record.suppressSeekTimer);
      for (const controller of [record.inspectController, record.frameController, record.proxyController, record.extractController, record.uploadController]) controller?.abort();
      record.fileInput?.remove();
      if (record.fileInput) {
        record.fileInput.onchange = null;
        record.fileInput.oncancel = null;
      }
      record.fileInput = null;
      for (const off of record.listeners.splice(0)) off();
      record.video.onloadedmetadata = null;
      record.video.onerror = null;
      record.frameImage.onload = null;
      record.frameImage.onerror = null;
      record.video.pause();
      record.video.removeAttribute("src");
      record.video.load();
      if (record.objectUrl) URL.revokeObjectURL(record.objectUrl);
      record.objectUrl = "";
    }
    allCandidates.clear();
    panel.refreshSources = () => {};
    panel.dispose = () => {};
  };
  refreshSources();
  return panel;
}

api.addEventListener("executed", event => {
  const detail = event.detail || {};
  const output = detail.output || {};
  const rows = output.pixaroma_save_video;
  if (Array.isArray(rows) && rows.length) {
    const id = String(detail.node || detail.display_node || "");
    if (id) {
      const entries = CACHE.get(id) || [];
      for (const raw of rows) {
        const entry = normalizedEntry(raw);
        if (!entry) continue;
        const identity = sourceId(entry);
        const prior = entries.findIndex(value => sourceId(value) === identity);
        if (prior >= 0) entries.splice(prior, 1);
        entries.unshift(entry);
      }
      if (entries.length > MAX_HISTORY_ITEMS) entries.length = MAX_HISTORY_ITEMS;
      CACHE.set(id, entries);
    }
  }
  if (Array.isArray(rows) || Array.isArray(output.overtli_h3_review)) {
    for (const callback of LISTENERS) callback(detail.node || detail.display_node || "");
  }
});
