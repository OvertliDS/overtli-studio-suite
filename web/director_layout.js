// One sizing contract for legacy canvas and Nodes 2.0 DOM widgets.
export function installDirectorSizing(node, root, minimum = [700, 480]) {
  root.style.width = "100%"; root.style.height = "100%";
  root.style.minWidth = "0"; root.style.minHeight = "0";
  root.style.boxSizing = "border-box"; root.style.overflow = "auto";
  node.resizable = true; node.flags ||= {}; node.flags.resizable = true;
  if (node._ovSizing) { node._ovSizing.root = root; return; }
  node.properties ||= {};
  const state = node._ovSizing = {root, dragging: false};
  const size = node.properties.overtliManualSize || node.size || minimum;
  node.size = [Math.max(minimum[0], size[0] || 0), Math.max(minimum[1], size[1] || 0)];
  const originalCompute = node.computeSize;
  node.computeSize = function(...args) {
    const computed = originalCompute?.apply(this, args) || minimum;
    const saved = state.dragging ? minimum : this.properties?.overtliManualSize || minimum;
    return [Math.max(minimum[0], computed[0] || 0, saved[0]), Math.max(minimum[1], saved[1])];
  };
  const originalResize = node.onResize;
  node.onResize = function(...args) {
    originalResize?.apply(this, args);
    this.size[0] = Math.max(minimum[0], this.size[0]);
    this.size[1] = Math.max(minimum[1], this.size[1]);
    this.properties.overtliManualSize = Array.from(this.size);
  };
  const down = event => {
    const target = event.target, frame = state.root.closest?.('.lg-node');
    if (frame && target?.closest?.('.lg-node') !== frame) return;
    if (!frame && target?.tagName !== 'CANVAS') return;
    const cursor = target && window.getComputedStyle(target).cursor;
    if (cursor?.includes('resize')) state.dragging = true;
  };
  const up = () => { if (!state.dragging) return; state.dragging = false; node.onResize?.(node.size); node.graph?.change?.(); };
  window.addEventListener('pointerdown', down, true);
  window.addEventListener('pointerup', up, true);
  window.addEventListener('pointercancel', up, true);
  const removed = node.onRemoved;
  node.onRemoved = function(...args) {
    window.removeEventListener('pointerdown', down, true);
    window.removeEventListener('pointerup', up, true);
    window.removeEventListener('pointercancel', up, true);
    return removed?.apply(this, args);
  };
}

export function sizingControls(node) {
  const details = document.createElement('details'), summary = document.createElement('summary');
  summary.textContent = 'Node size'; details.append(summary);
  const fields = [0, 1].map((axis) => {
    const field = document.createElement('input'); field.type = 'number'; field.step = '20';
    field.setAttribute('aria-label', axis ? 'Node height' : 'Node width'); field.value = String(node.size?.[axis] || (axis ? 600 : 700));
    details.append(field); return field;
  });
  const apply = document.createElement('button'); apply.textContent = 'Apply size'; apply.type = 'button';
  apply.onclick = () => {
    const size = fields.map((field, i) => Math.max(i ? 480 : 700, Math.min(4000, Number(field.value) || (i ? 600 : 700))));
    node.properties ||= {}; node.properties.overtliManualSize = size;
    node.setSize?.(size); node.size = size; node.onResize?.(size); node.graph?.change?.(); node.graph?.setDirtyCanvas?.(true, true);
  }; details.append(apply); return details;
}
