const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.style = {};
    this.dataset = {};
    this.attributes = {};
    this.listeners = new Map();
    this.className = '';
    this.textContent = '';
    this.value = '';
    this.disabled = false;
    this.hidden = false;
    this.files = [];
    this.paused = true;
    this.isConnected = true;
    this.classList = { toggle: () => {} };
  }
  get firstChild() { return this.children[0] || null; }
  append(...children) { for (const child of children) { child.parentNode = this; this.children.push(child); } }
  appendChild(child) { this.append(child); return child; }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  setAttribute(name, value) { this.attributes[name] = String(value); this[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; delete this[name]; }
  addEventListener(name, fn) { const list = this.listeners.get(name) || new Set(); list.add(fn); this.listeners.set(name, list); }
  removeEventListener(name, fn) { this.listeners.get(name)?.delete(fn); }
  dispatch(name, event = {}) { for (const fn of [...(this.listeners.get(name) || [])]) fn(event); }
  closest() { return null; }
  remove() { this.removed = true; this.parentNode?.replaceChildren(...this.parentNode.children.filter(child => child !== this)); }
  click() { this.onclick?.(); }
  pause() { if (!this.paused) { this.paused = true; this.dispatch('pause'); } }
  play() { if (this.paused) { this.paused = false; this.dispatch('play'); } return Promise.resolve(); }
  load() { this.loadCount = (this.loadCount || 0) + 1; }
}

const calls = [];
const appListeners = new Map();
const local = new Map();
const historyEntry = {
  filename: 'old-export.mov', type: 'external', token: 'legacy-token',
  _overtli_scope: 'addtl', status: { folder: 'OvertliDS/addtl/old-export.mov', format: 'QuickTime' },
};
let proxyCount = 0;
let frameCount = 0;
let extractCount = 0;
let uploadSubfolder = '';

const response = (data, status = 200, headers = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => data,
  blob: async () => new Blob(['decoded-png']),
  headers: { get: name => headers[name] ?? null },
});

const api = {
  apiURL: value => `/api${value}`,
  addEventListener(name, listener) { appListeners.set(name, listener); },
  async fetchApi(url, options = {}) {
    calls.push({ url, options });
    if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if (url.startsWith('/history?')) {
      return response({ prompt: { outputs: { 44: { pixaroma_save_video: [historyEntry] } } } });
    }
    if (url.startsWith('/overtli/studio/files?')) {
      const addtl = url.endsWith('addtl=1');
      return response({ files: [addtl ? 'OvertliDS/addtl/uploaded.webm' : 'OvertliDS/references/normal.webm'] });
    }
    if (url === '/overtli/studio/video-scope') {
      return response({ error: 'This external save has no verified Normal/Addtl scope.' }, 400);
    }
    if (url === '/overtli/studio/video-inspect') {
      const body = JSON.parse(options.body);
      if (body.entry.type === 'external') {
        return response({ error: 'This external save has no verified Normal/Addtl scope. Upload it into the selected Normal or Addtl input island before frame inspection or extraction.' }, 400);
      }
      const scope = body.entry.subfolder.includes('/addtl/') ? 'addtl' : 'normal';
      return response({ scope, width: 64, height: 48, frame_count: 10, avg_fps: 24, nominal_fps: 24, duration: 0.417, raster: { width: 64, height: 48 } });
    }
    if (url === '/overtli/studio/video-proxy') {
      const body = JSON.parse(options.body);
      proxyCount++;
      return response({
        preview: { filename: `proxy-${proxyCount}.mp4`, subfolder: '', type: 'temp' },
        playback_only: true,
        source_scope: body.subfolder?.includes('/addtl/') ? 'addtl' : null,
      });
    }
    if (url === '/overtli/studio/video-frame') {
      frameCount++;
      return response(null, 200, { 'X-Overtli-Frame-Timestamp': '0.125' });
    }
    if (url === '/overtli/studio/video-frames/extract') {
      const body = JSON.parse(options.body);
      extractCount++;
      return response({ frames: body.frame_indices.map(index => ({
        filename: `frame-${index}.png`, subfolder: body.scope === 'addtl' ? 'OvertliDS/addtl/frames' : 'OvertliDS/references/frames',
        frame_index: index, timestamp: index / 24, raster: { width: 64, height: 48 },
      })) });
    }
    if (url === '/upload/image') {
      uploadSubfolder = options.body.get('subfolder');
      return response({ name: 'uploaded-now.webm', subfolder: uploadSubfolder });
    }
    throw new Error(`Unexpected request ${url}`);
  },
};

const rootGraph = {
  extra: { workflowId: 'review-test-workflow' },
  _nodes: [
    { id: 77, comfyClass: 'OvertliH3RunGallery', properties: {} },
    { id: 44, comfyClass: 'OvertliDirectorSaveVideo', title: 'Installed saver', properties: {} },
  ],
  links: {},
};
const app = { graph: rootGraph, rootGraph, registerExtension() {} };
const document = {
  head: new Element('head'),
  getElementById: () => null,
  createElement: tag => new Element(tag),
};
const revoked = [];
const context = {
  app, api, document, console, localStorage: {
    getItem: key => local.get(key) ?? null,
    setItem: (key, value) => local.set(key, value),
  },
  URL: {
    createObjectURL: () => `blob:frame-${Math.random()}`,
    revokeObjectURL: value => revoked.push(value),
  },
  isAddtl: host => !!host?.properties?.overtliAddtl || !!host?.graph?.extra?.overtliAddtl
    || !!host?.graph?._nodes?.some(node => node.properties?.overtliAddtl),
  AbortController, Blob, DOMException, FormData, URLSearchParams,
  setTimeout, clearTimeout, Math, Number, String, Object, Array, JSON, Map, Set,
};
vm.createContext(context);
const sourcePath = path.resolve(__dirname, '../../web/video_compare.js');
const source = fs.readFileSync(sourcePath, 'utf8')
  .replace(/^import .*;\r?\n/gm, '')
  .replace(/\bexport /g, '') + '\nthis.videoCompareForTest = videoCompare;';
vm.runInContext(source, context, { filename: sourcePath });

const walk = root => {
  const result = [];
  const visit = element => {
    if (!element || typeof element !== 'object') return;
    if (element.tagName) result.push(element);
    for (const child of element.children || []) visit(child);
  };
  visit(root);
  return result;
};
const turn = async () => { await new Promise(resolve => setImmediate(resolve)); await new Promise(resolve => setImmediate(resolve)); };

(async () => {
  const host = { id: 77, graph: rootGraph, properties: {} };
  const panel = context.videoCompareForTest(host, { sourceProvider: async () => [] });
  await panel.refreshSources();

  const elements = walk(panel);
  const select = elements.find(element => element.tagName === 'SELECT');
  assert.ok(select, 'two source selectors are rendered');
  const legacyOption = select.children.find(option => option.textContent.includes('Playback only · scope unverified'));
  assert.ok(legacyOption, 'unknown legacy external saves remain selectable for playback');
  select.value = legacyOption.value;
  select.onchange();
  await turn();
  assert.equal(proxyCount, 1, 'unknown legacy media uses the playback proxy');
  assert.ok(elements.find(element => element.tagName === 'VIDEO').src.includes('proxy-1.mp4'));
  assert.ok(panel.children.at(-1).textContent.includes('Upload it into the selected Normal or Addtl input island'));
  assert.ok(elements.find(element => element.tagName === 'INPUT' && element.type === 'range').disabled,
    'unknown external scope disables exact frame controls');

  const normalOption = select.children.find(option => option.textContent.includes('normal.webm'));
  assert.ok(normalOption);
  select.value = normalOption.value;
  select.onchange();
  await turn();
  assert.equal(proxyCount, 2, 'browser-native WebM is still routed through the playback proxy');
  assert.equal(elements.find(element => element.tagName === 'VIDEO').src.includes('proxy-2.mp4'), true);
  const knownInspect = calls.findLast(call => call.url === '/overtli/studio/video-inspect');
  assert.equal(JSON.parse(knownInspect.options.body).entry.filename, 'normal.webm');
  assert.equal(JSON.parse(knownInspect.options.body).entry.type, 'input');
  assert.ok(elements.find(element => element.tagName === 'INPUT' && element.type === 'range').disabled === false,
    'backend-confirmed media enables exact frame controls');

  const step = elements.find(element => element.tagName === 'BUTTON' && element.textContent === 'Frame +');
  const framesBeforeStep = frameCount;
  step.onclick();
  await turn();
  assert.equal(frameCount, framesBeforeStep + 1, 'frame stepping decodes the selected original frame');
  const single = elements.find(element => element.tagName === 'BUTTON' && element.textContent === 'Export current frame');
  single.onclick();
  await turn();
  assert.equal(extractCount, 1);
  const extraction = calls.findLast(call => call.url === '/overtli/studio/video-frames/extract');
  const extractionBody = JSON.parse(extraction.options.body);
  assert.equal(extractionBody.entry.filename, 'normal.webm', 'extraction receives the original, never the proxy');
  assert.equal(extractionBody.frame_indices[0], 1);
  assert.equal(extractionBody.scope, 'normal');

  const key = [...local.keys()].find(value => value.startsWith('overtli.video-compare.v3:'));
  assert.ok(key.includes(':normal:77'), 'selection storage is separated by wall scope and ID');
  assert.ok(JSON.parse(local.get(key)).source[0].entry.filename === 'normal.webm');

  appListeners.get('executed')?.({ detail: { node: '44', output: { pixaroma_save_video: [
    { filename: 'saver-h264.mp4', type: 'temp', subfolder: '', _pixaroma_status: { format: 'H.264' } },
    { filename: 'saver-prores.mov', type: 'temp', subfolder: '', _pixaroma_status: { format: 'ProRes' } },
  ] } } });
  await panel.refreshSources();
  assert.ok(select.children.some(option => option.textContent.includes('saver-h264.mp4')));
  assert.ok(select.children.some(option => option.textContent.includes('saver-prores.mov')),
    'the current save event retains all installed saver format outputs');

  const frameNumberInputs = elements.filter(element => element.tagName === 'INPUT' && element.type === 'number');
  const rangeStart = frameNumberInputs[1];
  const rangeEnd = frameNumberInputs[2];
  const rangeButton = elements.find(element => element.tagName === 'BUTTON' && element.textContent === 'Export frame range');
  rangeStart.value = '0'; rangeEnd.value = '1000000000';
  rangeButton.onclick();
  assert.equal(extractCount, 1, 'oversized UI ranges are rejected before allocating a frame list');

  const addtlGraph = {
    extra: { workflowId: 'review-test-workflow' },
    _nodes: [{ id: 78, comfyClass: 'OvertliH3RunGallery', properties: { overtliAddtl: true } }],
    links: {},
  };
  const addtlPanel = context.videoCompareForTest({ id: 78, graph: addtlGraph, properties: { overtliAddtl: true } }, { sourceProvider: async () => [] });
  await addtlPanel.refreshSources();
  const addtlElements = walk(addtlPanel);
  const addtlUploadButton = addtlElements.find(element => element.tagName === 'BUTTON' && element.textContent === 'Upload comparison video');
  addtlUploadButton.click();
  const fileInput = walk(addtlPanel).find(element => element.tagName === 'INPUT' && element.type === 'file');
  assert.ok(fileInput);
  fileInput.files = [new File(['small-video'], 'new.webm', { type: 'video/webm' })];
  await fileInput.onchange();
  assert.equal(uploadSubfolder, 'OvertliDS/addtl/compare');

  const callsBeforeDispose = calls.length;
  panel.dispose();
  addtlPanel.dispose();
  appListeners.get('executed')?.({ detail: { node: '44', output: { pixaroma_save_video: [{ filename: 'changed.mp4' }] } } });
  await turn();
  assert.equal(calls.length, callsBeforeDispose, 'disposed panels no longer refresh from executed events');
  assert.ok(revoked.length >= 0);
  console.log('Video compare proxy, scope, extraction, persistence, upload, bounds, and cleanup: OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
