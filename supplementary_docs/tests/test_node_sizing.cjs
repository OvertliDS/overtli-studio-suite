const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.style = {}; this.value = ''; this.frame = null; }
  append(...children) { this.children.push(...children); }
  setAttribute(name, value) { this[name] = value; }
  closest(selector) {
    if (selector === '.lg-node') return this.frame;
    if (selector === '.lg-node-widget') return this.isWidget ? this : null;
    return null;
  }
}

const extensions = [];
const pendingMicrotasks = [];
const listeners = new Map();
const window = {
  addEventListener(name, fn) { const set = listeners.get(name) || new Set(); set.add(fn); listeners.set(name, set); },
  removeEventListener(name, fn) { listeners.get(name)?.delete(fn); },
  getComputedStyle(target) { return { cursor: target?.cursor || '' }; },
  dispatch(name, event) { for (const fn of [...(listeners.get(name) || [])]) fn(event); },
};
const context = {
  console, Map, Date, JSON, Math, Number, String, Object, Array,
  queueMicrotask: fn => pendingMicrotasks.push(fn),
  document: { createElement: tag => new Element(tag) }, window,
  app: { registerExtension(extension) { extensions.push(extension); } },
};
vm.createContext(context);
const sourcePath = path.join(__dirname, '../../web/director_layout.js');
const source = fs.readFileSync(sourcePath, 'utf8')
  .replace(/^import .*;\r?\n/gm, '')
  .replace(/\bexport /g, '') +
  '\nthis.installDirectorSizing = installDirectorSizing; this.sizingControls = sizingControls;';
vm.runInContext(source, context, { filename: sourcePath });

const countListeners = () => [...listeners.values()].reduce((total, set) => total + set.size, 0);
const flushMicrotasks = () => { while (pendingMicrotasks.length) pendingMicrotasks.shift()(); };
const makeRoot = frame => { const root = new Element('section'); root.frame = frame || null; return root; };
const resizeTarget = (frame, cursor = 'nwse-resize') => {
  const target = new Element('div'); target.frame = frame; target.cursor = cursor; return target;
};
const installFixture = ({ size = [850, 600], properties = {}, minimum = [700, 480], root = makeRoot(null) } = {}) => {
  const node = {
    size: size.slice(), properties: { ...properties }, root,
    computeSize() { return [1200, 900]; },
    graph: { changes: 0, change() { this.changes += 1; }, setDirtyCanvas() {} },
    setSize(value) { this.size = value.slice(); },
  };
  context.installDirectorSizing(node, root, minimum);
  return node;
};

// Selection/autosize can call onResize, but only a resize-handle gesture saves intent.
const main = installFixture({ size: [850, 600] });
main.comfyClass = 'OvertliStudioSuite';
main.size = [1200, 900]; main.onResize(main.size);
assert.equal(main.properties.overtliManualSize, undefined, 'autosize does not create manual intent');
assert.deepEqual(Array.from(main.computeSize()), [1200, 900], 'computed size is available before manual resize');

const legacyCanvas = { tagName: 'CANVAS', cursor: 'nwse-resize', closest() { return null; } };
window.dispatch('pointerdown', { target: legacyCanvas, button: 0 });
main.size = [760, 520]; main.onResize(main.size);
window.dispatch('pointerup', { target: legacyCanvas });
assert.deepEqual(Array.from(main.properties.overtliManualSize), [760, 520], 'legacy resize gesture saves chosen size');
assert.deepEqual(Array.from(main.computeSize()), [760, 520], 'saved size wins over a larger computed size');
main.setSize(main.computeSize());
assert.deepEqual(Array.from(main.size), [760, 520], 'Resize Selected Nodes applies the persisted size');

const legacyWidget = { tagName: 'DIV', cursor: 'ew-resize', isWidget: true, closest(selector) {
  if (selector === '.lg-node-widget') return this;
  return null;
} };
window.dispatch('pointerdown', { target: legacyWidget, button: 0 });
main.size = [1300, 1000]; main.onResize(main.size);
window.dispatch('pointerup', { target: legacyWidget });
assert.deepEqual(Array.from(main.size), [760, 520], 'widget gestures and autosize preserve saved geometry');
assert.deepEqual(Array.from(main.properties.overtliManualSize), [760, 520]);

const controls = context.sizingControls(main);
const fields = controls.children.filter(child => child.tagName === 'INPUT');
const apply = controls.children.find(child => child.tagName === 'BUTTON');
fields[0].value = '700'; fields[1].value = '480'; apply.onclick();
assert.deepEqual(Array.from(main.properties.overtliManualSize), [700, 480], 'explicit controls allow deliberate shrink to the node floor');
fields[0].value = '1180'; fields[1].value = '860'; apply.onclick();
assert.deepEqual(Array.from(main.properties.overtliManualSize), [1180, 860], 'explicit controls allow deliberate growth');
window.dispatch('pointerdown', { target: legacyCanvas, button: 0 });
main.size = [1240, 920]; main.onResize(main.size);
window.dispatch('pointerup', { target: legacyCanvas });
assert.deepEqual(fields.map(field => field.value), ['1240', '920'], 'drag updates existing size controls');
fields[0].value = '1180'; fields[1].value = '860'; apply.onclick();

const savedProperties = JSON.parse(JSON.stringify(main.properties));
const reopened = installFixture({ size: [900, 700], properties: savedProperties });
assert.deepEqual(Array.from(reopened.size), [1180, 860], 'saved geometry is restored on workflow reopen');
reopened.size = [1500, 1100]; reopened.onResize(reopened.size);
assert.deepEqual(Array.from(reopened.size), [1180, 860], 'autosize after reopen retains saved geometry');
const replacementRoot = makeRoot(null);
context.installDirectorSizing(reopened, replacementRoot, [700, 480]);
assert.equal(reopened._ovSizing.root, replacementRoot, 'reinstall binds the replacement DOM root');
assert.deepEqual(Array.from(reopened.size), [1180, 860], 'reinstall retains saved geometry');

for (const className of ['OvertliH3ReferenceDirectorUI', 'OvertliImageDirectorUI']) {
  const frame = {}, root = makeRoot(frame);
  const director = installFixture({ size: [820, 600], root });
  director.comfyClass = className;
  const target = resizeTarget(frame);
  window.dispatch('pointerdown', { target, button: 0 });
  director.size = [740, 520]; director.onResize(director.size);
  window.dispatch('pointerup', { target });
  assert.deepEqual(Array.from(director.properties.overtliManualSize), [740, 520], `${className} main DOM keeps manual geometry`);
  director.size = [1600, 1100]; director.onResize(director.size);
  assert.deepEqual(Array.from(director.size), [740, 520], `${className} main DOM ignores later autosize`);
  context.installDirectorSizing(director, makeRoot(frame), [700, 480]);
  assert.deepEqual(Array.from(director.size), [740, 520], `${className} main DOM reinstalls with saved geometry`);
  director.onRemoved?.();
}

// Named Overtli live/review widgets get the same lifecycle without patching unrelated packs.
const scopedExtension = extensions.find(extension => extension.name === 'Overtli.DirectorSizing.ScopedDOM');
assert.ok(scopedExtension, 'scoped DOM sizing extension registered');
const scoped = [
  ['OvertliH3LivePreviewControl', 'overtli_h3_live_monitor', [1, 260]],
  ['OvertliH3ResultReview', 'overtli_h3_result_review', [1, 260]],
  ['OvertliH3RunGallery', 'overtli_h3_review_wall', [1, 300]],
  ['OvertliH3UpscaleReview', 'overtli_h3_upscale_review', [1, 260]],
  ['OvertliImageLivePreviewMonitor', 'ov_live', [1, 300]],
  ['OvertliImageReviewWall', 'ov_review', [1, 360]],
  ['OvertliImageComparePanel', 'ov_compare', [520, 580]],
];
for (const [className, widgetName, minimum] of scoped) {
  const frame = {};
  const roots = [makeRoot(frame), makeRoot(frame)];
  let nextRoot = 0, removed = false;
  const nodeType = { prototype: {
    onNodeCreated() { return this.addDOMWidget(widgetName, widgetName, roots[nextRoot++]); },
    onConfigure() { return this.addDOMWidget(widgetName, widgetName, roots[nextRoot++]); },
  } };
  scopedExtension.beforeRegisterNodeDef(nodeType, { name: className });
  const initialWidth = minimum[0] <= 1 ? 420 : minimum[0] + 80;
  const node = {
    comfyClass: className, size: [initialWidth, minimum[1] + 80], properties: {}, widgets: [],
    graph: { change() {}, setDirtyCanvas() {} },
    addDOMWidget(name, type, element) {
      const widget = { name, type, element, computeLayoutSize: () => ({ minWidth: minimum[0], minHeight: minimum[1] }) };
      this.widgets.push(widget); return widget;
    },
    onRemoved() { removed = true; },
  };
  const before = countListeners();
  nodeType.prototype.onNodeCreated.call(node);
  flushMicrotasks();
  assert.ok(node._ovSizing, `${className} installs size lifecycle`);
  assert.equal(node._ovSizing.minimum[0], minimum[0], `${className} keeps its width floor`);
  if (minimum[0] <= 1) assert.equal(node.size[0], initialWidth, `${className} keeps its small default width`);
  assert.equal(countListeners(), before + 3, `${className} adds one scoped listener set`);

  const chosen = [minimum[0] + 50, minimum[1] + 50];
  window.dispatch('pointerdown', { target: resizeTarget(frame), button: 0 });
  node.size = chosen.slice(); node.onResize(node.size);
  window.dispatch('pointerup', { target: resizeTarget(frame) });
  assert.deepEqual(Array.from(node.properties.overtliManualSize), chosen, `${className} persists a manual resize`);

  node.size = [1800, 1200]; node.onResize(node.size);
  assert.deepEqual(Array.from(node.size), chosen, `${className} selection/autosize retains chosen geometry`);
  nodeType.prototype.onConfigure.call(node);
  flushMicrotasks();
  assert.equal(node._ovSizing.root, roots[1], `${className} rebinds after configure`);
  assert.deepEqual(Array.from(node.size), chosen, `${className} configure retains saved geometry`);
  node.onRemoved();
  assert.equal(removed, true, `${className} keeps its removal callback`);
  assert.equal(countListeners(), before, `${className} cleans up sizing listeners`);
}

const unrelatedType = { prototype: { onNodeCreated() { return 'unchanged'; } } };
// Socket rows are outside the DOM body and must fit inside the saved frame.
const socketNode = {size: [1100, 760], outputs: Array(17).fill({}), properties: {overtliManualSize: [1100, 760]},
  computeSize() {return [1100, 760];}};
context.installDirectorSizing(socketNode, makeRoot({}), [700, 480]);
assert.deepEqual(Array.from(socketNode.size), [1100, 868], 'editor plus sockets fit the minimum frame');
assert.deepEqual(Array.from(socketNode.properties.overtliManualSize), [1100, 868], 'old small geometry migrates to the same persisted floor');
socketNode.onRemoved();
const nativeType = {prototype: {onNodeCreated() {return 'legacy-native';}}};
scopedExtension.beforeRegisterNodeDef(nativeType, {name: 'GZ_StyleStackNode'});
const nativeNode = {size: [500, 300], properties: {}, outputs: [{}], computeSize() {return [500, 300];}};
nativeType.prototype.onNodeCreated.call(nativeNode); flushMicrotasks();
assert.ok(nativeNode._ovSizing, 'registered legacy Suite nodes use scoped manual geometry');
nativeNode.properties.overtliManualSize = [600, 400]; nativeNode.size = [300, 200]; nativeNode.onResize(nativeNode.size);
assert.deepEqual(Array.from(nativeNode.size), [600, 400]); nativeNode.onRemoved();
const unrelatedCreated = unrelatedType.prototype.onNodeCreated;
scopedExtension.beforeRegisterNodeDef(unrelatedType, { name: 'ThirdPartySmallNode' });
assert.equal(unrelatedType.prototype.onNodeCreated, unrelatedCreated, 'unrelated node packs remain untouched');

main.onRemoved?.(); reopened.onRemoved?.();
console.log('Manual sizing intent, scoped DOM lifecycle, reopen, resize controls, and cleanup: OK');
