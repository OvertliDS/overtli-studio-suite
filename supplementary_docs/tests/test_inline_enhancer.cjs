const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.style = {}; this.value = ''; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener() {}
  setAttribute(name, value) { this[name] = value; }
  dispatchEvent() {}
}
const requests = [];
let pending = null;
const context = { console, Map, Date, JSON, Math, Number, String, Event: class {}, queueMicrotask: fn => fn(),
  document: {getElementById: () => true, createElement: tag => new Element(tag)},
  app: {registerExtension() {}}, api: {apiURL: x => x},
  fetch: async (url, options) => {
    requests.push({url, body: options?.body && JSON.parse(options.body)});
    if (url.includes('/models')) return {ok: true, json: async () => ({models: [{id: 'available'}]})};
    if (pending) return pending;
    return {ok: true, json: async () => ({prompt: 'editable draft', checks: {errors: [], warnings: []}})};
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../web/director_shared.js'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '').replace(/export /g, '') + '\nthis.inlineEnhancer = inlineEnhancer; this.suiteNode = suiteNode; this.refreshPromptPanels = refreshPromptPanels; this.finalPromptPanel = finalPromptPanel; this.promptFingerprint = promptFingerprint;', context);
(async () => {
  const widget = {name: 'state', value: JSON.stringify({provider: 'LM Studio', model: 'saved-offline', enabled: true, autoUnload: true})};
  const paired = {id: 3, type: 'OvertliStudioSuite', widgets: [widget], properties: {}, graph: {change() {}}};
  const unrelated = {id: 4, type: 'OvertliStudioSuite', widgets: [{name: 'state', value: '{}'}]};
  const host = {properties: {overtliStudioNodeId: 3}, graph: {_nodes: [paired, unrelated]}};
  assert.equal(context.suiteNode(host), paired);
  assert.equal(context.suiteNode({...host, properties: {}}), null, 'ambiguous Studio never guessed');
  let hostRefreshes = 0, studioRefreshes = 0, unrelatedRefreshes = 0;
  host.id = 2;
  host._ovPromptPanel = {sync: () => hostRefreshes++};
  unrelated._ovPromptPanel = {sync: () => unrelatedRefreshes++};
  paired.properties.overtliDirectorNodeId = 2;
  paired.graph._nodes = [host, paired, unrelated];
  paired._ovStudioRefreshControls = () => studioRefreshes++;
  context.refreshPromptPanels(host);
  context.refreshPromptPanels(paired);
  assert.equal(hostRefreshes, 2, 'Director and Studio edits both invalidate the paired prompt panel');
  assert.equal(studioRefreshes, 2);
  assert.equal(unrelatedRefreshes, 0, 'another Studio island is untouched');
  let authored = 'original';
  const panel = context.inlineEnhancer(host, () => ({guide: 'FLUX.2 Klein 9B', getPrompt: () => authored, setPrompt: x => {authored = x;}}));
  const [provider, model, refresh] = panel.children.find(x => x.tagName === 'div' && x.className === 'ovstudio-row').children;
  assert.equal(model.value, 'saved-offline');
  assert.equal(requests.length, 0, 'no model polling on construction');
  await refresh.onclick();
  assert.equal(model.value, 'saved-offline', 'explicit refresh preserves unavailable saved models');
  const draft = panel.children.find(x => x.textContent === 'Enhance draft');
  const apply = panel.children.find(x => x.textContent === 'Use draft as authored · enhancement Off');
  await draft.onclick();
  assert.equal(requests.at(-1).body.prompt, 'original');
  authored = 'edited during preview'; apply.onclick();
  assert.equal(authored, 'edited during preview', 'stale source cannot be replaced');
  await draft.onclick(); apply.onclick();
  assert.equal(authored, 'editable draft');
  assert.equal(JSON.parse(widget.value).enabled, false);
  assert.equal(JSON.parse(widget.value).promptOverrideEnabled, false);
  let resolve;
  pending = new Promise(done => {resolve = done;});
  const wait = draft.onclick();
  provider.value = 'Ollama'; provider.onchange();
  resolve({ok: true, json: async () => ({prompt: 'stale request', checks: {errors: [], warnings: []}})});
  await wait;
  assert.equal(apply.disabled, true, 'settings edits invalidate an in-flight draft');
  assert.equal(authored, 'editable draft');
  assert.equal(JSON.parse(widget.value).provider, 'Ollama');
  let graphDone;
  context.app.graphToPrompt = () => new Promise(resolve => { graphDone = resolve; });
  const final = context.finalPromptPanel(host);
  let fingerprint = 'original inputs';
  final.getFingerprint = () => fingerprint;
  const prepare = final.children.find(x => x.textContent === 'Prepare final prompts');
  const beforeRequests = requests.length;
  const preparation = prepare.onclick();
  fingerprint = 'edited while graph was being prepared';
  graphDone({output: {}});
  await preparation;
  assert.equal(requests.length, beforeRequests, 'mixed graph snapshot is rejected before backend preflight');
  assert.match(final.children.at(-1).textContent, /changed during graph preparation/);
  const settings = {getPrompt: () => 'author', guide:'H3 Ref2VA'};
  // Studio seed changes are settings changes; only a Director's transient
  // execution seed is omitted, while model and canvas changes remain relevant.
  const directorHost = {properties:{overtliStudioNodeId:3}, graph:host.graph, widgets:[{name:'state',value:'{"seed":1,"width":1024}'}]};
  const original = context.promptFingerprint(directorHost, settings);
  directorHost.widgets[0].value = '{"seed":2,"width":1024}';
  assert.equal(context.promptFingerprint(directorHost, settings), original);
  directorHost.widgets[0].value = '{"seed":2,"width":768}';
  assert.notEqual(context.promptFingerprint(directorHost, settings), original);
  console.log('Inline enhancement pairing, explicit discovery, offline model persistence and stale draft guards: OK');
})().catch(error => {console.error(error); process.exitCode = 1;});
