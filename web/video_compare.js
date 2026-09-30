import { api } from "/scripts/api.js";
import { app } from "/scripts/app.js";
import { isAddtl } from "./director_shared.js";

const CACHE = new Map(), LISTENERS = new Set();
const el = (tag, text = "") => { const e = document.createElement(tag); e.textContent = text; return e; };
const btn = (text, fn) => { const b = el("button", text); b.type = "button"; b.onclick = fn; return b; };
function url(entry) {
  if (!entry) return "";
  if (entry.type === "external") return api.apiURL("/pixaroma/api/save_video/file?t=" + encodeURIComponent(entry.token));
  return api.apiURL("/view?" + new URLSearchParams({ filename: entry.filename, subfolder: entry.subfolder || "", type: entry.type || "output" }));
}
api.addEventListener("executed", e => {
  const entries = e.detail?.output?.pixaroma_save_video;
  if (!entries?.length) return;
  const id = String(e.detail.node || e.detail.display_node);
  CACHE.set(id, entries[entries.length - 1]);
  const node = app.graph?.getNodeById?.(id);
  if (node?.properties) node.properties.overtliVideoLastRun = entries[entries.length - 1];
  for (const callback of LISTENERS) callback(id);
});
export function videoCompare(host) {
  const panel = el("section"); panel.className = "ovstudio";
  panel.append(el("h3", "Video compare"), el("div", "Compare two outputs or upload references. Playback uses browser proxies when a master codec needs them."));
  const status = el("div"); status.className = "ovstudio-status";
  const grid = el("div"); grid.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:10px;min-width:0";
  const videos = [], entries = [], selects = []; let lock = false;
  const candidates = () => {
    const all = host.graph?._nodes || [];
    return all.filter(n => /(?:PixaromaSaveVideo|OvertliDirectorSaveVideo)/.test(n.comfyClass || n.type)).map(n => ({ id: String(n.id), label: n.title || String(n.id), entry: CACHE.get(String(n.id)) || n.properties?.overtliVideoLastRun || n.properties?.pixSvLastRun })).filter(x => x.entry?.filename && /(^|[\\/])addtl([\\/]|$)/i.test(x.entry.subfolder || x.entry.status?.folder || x.entry._pixaroma_status?.folder || "") === isAddtl(host));
  };
  for (let i = 0; i < 2; i++) {
    const column = el("div"), choose = el("select"), video = el("video"), info = el("div"), metadata = el("details");
    video.className = "ovstudio-video"; video.controls = true; video.preload = "metadata"; video.playsInline = true;
    info.className = "ovstudio-status"; metadata.append(el("summary", "Prompt / LoRAs / generation metadata")); const text = el("pre"); text.style.cssText = "white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto"; metadata.append(text);
    const load = async entry => {
      entries[i] = entry; text.textContent = JSON.stringify(entry._overtli_metadata || { note: "Older output has no director sidecar metadata.", generation: entry.status || entry._pixaroma_status || {} }, null, 2);
      video._proxyTried = false;
      let preview = entry._pixaroma_preview;
      const format = entry._pixaroma_status?.format || entry.status?.format || entry.format || "";
      if (!preview && (/prores|mp4hq|quicktime/i.test(format) || /\.mov$/i.test(entry.filename))) preview = await proxy(entry);
      video.src = url(preview || entry); info.textContent = entry.filename;
    };
    async function proxy(entry) { status.textContent = "Preparing browser proxy…"; const r = await fetch(api.apiURL("/overtli/studio/video-proxy"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(entry) }); const data = await r.json(); if (!r.ok) throw Error(data.error || "Proxy failed"); status.textContent = "Browser proxy ready; master file preserved."; return data.preview; }
    choose.onchange = () => { const e = candidates().find(x => x.id === choose.value); if (e) load(e.entry).catch(e => { status.textContent = e.message; }); };
    video.onerror = async () => { if (!entries[i] || video._proxyTried) return; video._proxyTried = true; try { const p = await proxy(entries[i]); video.src = url(p); } catch (e) { status.textContent = e.message; } };
    video.onloadedmetadata = () => { info.textContent = `${entries[i]?.filename || "Video"} · ${video.videoWidth}×${video.videoHeight} · ${video.duration.toFixed(2)}s`; };
    column.append(choose, btn("Upload comparison", () => {
      const fileInput = el("input"); fileInput.type = "file"; fileInput.accept = "video/*,.mov,.mkv,.avi";
      fileInput.onchange = async () => { const file = fileInput.files?.[0]; if (!file) return; try { const fd = new FormData(); fd.append("image", file, file.name); fd.append("type", "input"); fd.append("subfolder", isAddtl(host) ? "OvertliDS/addtl/compare" : "OvertliDS/references/compare"); const r = await api.fetchApi("/upload/image", { method: "POST", body: fd }), d = await r.json(); if (!r.ok) throw Error(d.error || "Upload failed"); await load({ filename: d.name, subfolder: d.subfolder, type: "input", format: file.type }); } catch (e) { status.textContent = e.message; } }; fileInput.click();
    }), video, info, metadata); grid.append(column); videos.push(video); selects.push(choose);
  }
  const refresh = () => { for (const select of selects) { const old = select.value; select.replaceChildren(el("option", "Select a saved output")); for (const item of candidates()) { const o = el("option", item.label + " · " + item.entry.filename); o.value = item.id; select.append(o); } select.value = old; } };
  const sync = el("input"); sync.type = "checkbox"; sync.checked = true; const syncLabel = el("label", "Synchronize playback / seek "); syncLabel.append(sync);
  for (const video of videos) {
    const other = videos.find(x => x !== video);
    video.addEventListener("seeked", () => { if (!sync.checked || lock || !Number.isFinite(other.duration)) return; if (Math.abs(other.currentTime-video.currentTime) < .08) return; lock = true; other.currentTime = Math.min(video.currentTime, Math.max(0, other.duration-.01)); setTimeout(() => { lock = false; }, 100); });
    video.addEventListener("play", () => { if (sync.checked && other.src) other.play().catch(e => { status.textContent = "Playback requires clicking the other player: " + e.message; }); });
    video.addEventListener("pause", () => { if (sync.checked) other.pause(); });
    video.addEventListener("ratechange", () => { if (sync.checked) other.playbackRate = video.playbackRate; });
  }
  const uploadedFps = el("input"); uploadedFps.type = "number"; uploadedFps.value = "24"; uploadedFps.min = "1"; uploadedFps.max = "240"; uploadedFps.setAttribute("aria-label", "Uploaded video FPS"); uploadedFps.style.width = "65px";
  const fpsLabel = el("label", "Uploaded video FPS "); fpsLabel.append(uploadedFps);
  const frameRate = v => { const entry = entries[videos.indexOf(v)]; return Math.max(1, Number(entry?._pixaroma_status?.fps || entry?.status?.fps || uploadedFps.value) || 24); };
  const controls = el("div"); controls.className = "ovstudio-row"; controls.append(syncLabel, fpsLabel, btn("Refresh outputs", refresh), btn("Frame −", () => { videos.forEach(v => { v.pause(); v.currentTime = Math.max(0, v.currentTime - 1/frameRate(v)); }); }), btn("Frame +", () => { videos.forEach(v => { v.pause(); if (Number.isFinite(v.duration)) v.currentTime = Math.min(v.duration, v.currentTime + 1/frameRate(v)); }); }));
  panel.append(controls, grid, status); refresh();
  const changed = () => { if (panel.isConnected) refresh(); else LISTENERS.delete(changed); }; LISTENERS.add(changed);
  return panel;
}
