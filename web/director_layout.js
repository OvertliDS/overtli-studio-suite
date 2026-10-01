import { app } from "/scripts/app.js";

// One sizing contract for legacy canvas and Nodes 2.0 DOM widgets.
const MANUAL_SIZE = "overtliManualSize";
const validMinimum = (value, fallback) => Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : fallback;
const normalizedMinimum = (value, node) => {
  const slots = Math.max(node?.inputs?.length || 0, node?.outputs?.length || 0);
  // The public minimum describes the editor body. ComfyUI renders sockets
  // above that body; reserving their rows prevents minimum-height overflow.
  return [validMinimum(value?.[0], 700), validMinimum(value?.[1], 480) + (slots ? slots * 20 + 48 : 0)];
};
const normalizeSize = (value, minimum, fallback = minimum) => [0, 1].map(axis => {
  const candidate = Number(value?.[axis]);
  const backup = Number(fallback?.[axis]);
  return Math.max(minimum[axis], Number.isFinite(candidate) && candidate > 0 ? candidate : (Number.isFinite(backup) && backup > 0 ? backup : minimum[axis]));
});
const sameSize = (left, right) => !!left && !!right && left.length >= 2 && right.length >= 2 &&
  Math.abs(Number(left[0]) - Number(right[0])) < 1 && Math.abs(Number(left[1]) - Number(right[1])) < 1;

function styleSizingRoot(root) {
  if (!root?.style) return;
  root.style.width = "100%"; root.style.height = "100%";
  root.style.minWidth = "0"; root.style.minHeight = "0";
  root.style.boxSizing = "border-box"; root.style.overflow = "auto";
}

function saveManualSize(node, size, state = node._ovSizing) {
  const normalized = normalizeSize(size, state?.minimum || [700, 480], node.size);
  node.properties ||= {};
  node.properties[MANUAL_SIZE] = normalized.slice();
  if (node._ovSizeFields) {
    for (const fields of [...node._ovSizeFields]) {
      if (fields[0].isConnected === false) { node._ovSizeFields.delete(fields); continue; }
      fields.forEach((field, axis) => { field.value = String(Math.round(normalized[axis])); });
    }
  }
  state && (state.gesture = null);
  if (typeof node.setSize === "function") node.setSize(normalized.slice());
  node.size = normalized.slice();
  node.onResize?.(normalized.slice());
  node.size = normalized.slice();
  node.properties[MANUAL_SIZE] = normalized.slice();
  node.graph?.change?.();
  node.graph?.setDirtyCanvas?.(true, true);
  return normalized;
}

export function installDirectorSizing(node, root, minimum = [700, 480]) {
  if (!node || !root) return;
  const min = normalizedMinimum(minimum, node);
  styleSizingRoot(root);
  node.resizable = true; node.flags ||= {}; node.flags.resizable = true;

  if (node._ovSizing) {
    const state = node._ovSizing;
    state.root = root; state.minimum = min;
    node.properties ||= {};
    node.size = normalizeSize(node.properties[MANUAL_SIZE] || node.size, min, min);
    if (node.properties[MANUAL_SIZE]) node.properties[MANUAL_SIZE] = node.size.slice();
    return;
  }

  node.properties ||= {};
  const state = node._ovSizing = { root, minimum: min, gesture: null };
  node.size = normalizeSize(node.properties[MANUAL_SIZE] || node.size, min, min);
  if (node.properties[MANUAL_SIZE]) node.properties[MANUAL_SIZE] = node.size.slice();
  const originalCompute = node.computeSize;
  node.computeSize = function(...args) {
    const saved = this.properties?.[MANUAL_SIZE];
    if (saved) return normalizeSize(saved, state.minimum, this.size);
    if (state.gesture) return normalizeSize(this.size, state.minimum, state.gesture.startSize);
    const computed = originalCompute?.apply(this, args) || state.minimum;
    return normalizeSize(computed, state.minimum, state.minimum);
  };

  const originalResize = node.onResize;
  node.onResize = function(...args) {
    const result = originalResize?.apply(this, args);
    const manual = this.properties?.[MANUAL_SIZE];
    if (state.gesture) this.size = normalizeSize(this.size || args[0], state.minimum, state.gesture.startSize);
    else if (manual) this.size = normalizeSize(manual, state.minimum, this.size);
    else this.size = normalizeSize(this.size || args[0], state.minimum, state.minimum);
    return result;
  };

  const start = event => {
    const target = event.target;
    if ((event.button !== undefined && event.button !== 0) || target?.closest?.(".lg-node-widget")) return;
    const frame = state.root?.closest?.(".lg-node");
    const hitFrame = target?.closest?.(".lg-node");
    if (frame && hitFrame !== frame) return;
    if (!frame && target?.tagName !== "CANVAS") return;
    let cursor = "";
    try { cursor = target && window.getComputedStyle(target).cursor || ""; } catch {}
    if (!cursor.includes("resize")) return;
    state.gesture = { startSize: normalizeSize(node.size, state.minimum, state.minimum) };
  };
  const finish = () => {
    const gesture = state.gesture;
    if (!gesture) return;
    const result = normalizeSize(node.size, state.minimum, gesture.startSize);
    state.gesture = null;
    if (!sameSize(result, gesture.startSize)) saveManualSize(node, result, state);
  };
  window.addEventListener("pointerdown", start, true);
  window.addEventListener("pointerup", finish, true);
  window.addEventListener("pointercancel", finish, true);
  state.dispose = () => {
    window.removeEventListener("pointerdown", start, true);
    window.removeEventListener("pointerup", finish, true);
    window.removeEventListener("pointercancel", finish, true);
    state.gesture = null;
    node._ovSizeFields?.clear();
  };
  const removed = node.onRemoved;
  node.onRemoved = function(...args) {
    state.dispose?.();
    return removed?.apply(this, args);
  };
}

export function sizingControls(node) {
  const details = document.createElement('details'), summary = document.createElement('summary');
  summary.textContent = 'Node size'; details.append(summary);
  const minimum = node._ovSizing?.minimum || [700, 480];
  const fields = [0, 1].map((axis) => {
    const field = document.createElement('input'); field.type = 'number'; field.step = '20';
    field.setAttribute('aria-label', axis ? 'Node height' : 'Node width'); field.min = String(minimum[axis]); field.value = String(Math.round(node.size?.[axis] || minimum[axis]));
    details.append(field); return field;
  });
  (node._ovSizeFields ||= new Set()).add(fields);
  const apply = document.createElement('button'); apply.textContent = 'Apply size'; apply.type = 'button';
  apply.onclick = () => {
    const size = fields.map((field, i) => Math.max(minimum[i], Math.min(4000, Number(field.value) || minimum[i])));
    saveManualSize(node, size);
    fields.forEach((field, axis) => { field.value = String(node.size[axis]); });
  }; details.append(apply); return details;
}

// Keep sizing scoped to Overtli DOM widgets that do not call the public helper
// themselves. Their node frame owns geometry; unrelated custom-node packs are untouched.
const SCOPED_DOM_NODES = {
  OvertliH3LivePreviewControl: { overtli_h3_live_monitor: [1, 260] },
  OvertliH3ResultReview: { overtli_h3_result_review: [1, 260] },
  OvertliH3RunGallery: { overtli_h3_review_wall: [1, 300] },
  OvertliH3UpscaleReview: { overtli_h3_upscale_review: [1, 260] },
  OvertliImageLivePreviewMonitor: { ov_live: [1, 300] },
  OvertliImageReviewWall: { ov_review: [1, 360] },
  OvertliImageComparePanel: { ov_compare: [520, 580] },
};

// These are this Suite's registered legacy native-widget nodes. Keep their
// existing natural size until a user resizes; persisted geometry then wins.
const SUITE_NATIVE_NODES = new Set([
  "GZ_TextEnhancer", "GZ_ImageGen", "GZ_VideoGen", "GZ_TextToSpeech",
  "GZ_SpeechToText", "GZ_TextToAudio", "GZ_LLMTextEnhancer", "GZ_LMStudioTextEnhancer",
  "GZ_CopilotAgent", "GZ_OpenAICompatibleTextEnhancer", "GZ_AdvancedTextEnhancer",
  "GZ_ProviderSettings", "GZ_PromptLibraryNode", "GZ_StyleStackNode",
]);

function installScopedDOMSizing(node, names) {
  if (node._ovDirectorDOMSizingPatch || typeof node.addDOMWidget !== "function") return;
  const originalAdd = node.addDOMWidget;
  const hadOwnAdd = Object.prototype.hasOwnProperty.call(node, "addDOMWidget");
  const scopedAdd = function(name, type, element, ...args) {
    const widget = originalAdd.call(this, name, type, element, ...args);
    const minimum = names[name];
    if (minimum) queueMicrotask(() => {
      const root = element || widget?.element;
      const layout = widget?.computeLayoutSize?.();
      installDirectorSizing(this, root, [layout?.minWidth ?? minimum[0], layout?.minHeight ?? minimum[1]]);
    });
    return widget;
  };
  node.addDOMWidget = scopedAdd;
  const patch = node._ovDirectorDOMSizingPatch = { originalAdd, scopedAdd, hadOwnAdd };
  const removed = node.onRemoved;
  node.onRemoved = function(...args) {
    if (this._ovDirectorDOMSizingPatch === patch) {
      if (this.addDOMWidget === scopedAdd) {
        if (hadOwnAdd) this.addDOMWidget = originalAdd;
        else delete this.addDOMWidget;
      }
      delete this._ovDirectorDOMSizingPatch;
    }
    return removed?.apply(this, args);
  };
}

app.registerExtension({ name: "Overtli.DirectorSizing.ScopedDOM", beforeRegisterNodeDef(nodeType, nodeData) {
  const names = SCOPED_DOM_NODES[nodeData?.name];
  const native = SUITE_NATIVE_NODES.has(nodeData?.name);
  if (!names && !native) return;
  const install = node => {
    if (names) installScopedDOMSizing(node, names);
    else queueMicrotask(() => installDirectorSizing(node, document.createElement("div"), [240, 80]));
  };
  const originalCreated = nodeType.prototype.onNodeCreated;
  nodeType.prototype.onNodeCreated = function(...args) {
    install(this);
    return originalCreated?.apply(this, args);
  };
  const originalConfigure = nodeType.prototype.onConfigure;
  nodeType.prototype.onConfigure = function(...args) {
    install(this);
    return originalConfigure?.apply(this, args);
  };
}});
