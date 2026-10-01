const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.style = {}; this.value = ''; }
  append(...children) { this.children.push(...children); }
  remove() { this.removed = true; }
  addEventListener() {}
  setAttribute(name,value) {this[name]=value;}
  closest() {return null;}
  replaceChildren(...children) {this.children=children;}
}
const extensions = [];
const context = { console, queueMicrotask: fn => fn(), Map, Date, JSON, Math, Number, String,
  document: { getElementById: () => true, createElement: tag => new Element(tag) },
  window:{addEventListener(){},removeEventListener(){}},
  app: { registerExtension(extension) { extensions.push(extension); } }, api: {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/director_layout.js'),'utf8').replace(/^import .*;\r?\n/gm, '').replace(/export /g,''),context);
const source = fs.readFileSync(path.join(__dirname, '../../web/director_shared.js'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '').replace(/export /g, '');
vm.runInContext(source + '\nthis.installSuite = installSuite;', context);
assert.deepEqual(Array.from(context.scopeFiles(['OvertliDS/addtl/private.png', 'customer/addtl/ordinary.png', 'ordinary.png'], {properties:{overtliAddtl:true}})), ['OvertliDS/addtl/private.png']);
assert.deepEqual(Array.from(context.scopeFiles(['OvertliDS/addtl/private.png', 'customer/addtl/ordinary.png', 'ordinary.png'], {})), ['customer/addtl/ordinary.png', 'ordinary.png']);
const widget = {name: 'state', value:'{}'};
const node = { widgets:[widget], properties:{}, graph:{change(){}},
  computeSize() { return [900,760]; },
  addDOMWidget(name, type, element) { this.widgets.push({name,type,element}); } };
context.installSuite(node);
node.size=[900,760];node.onResize(node.size);
assert.equal(node.properties.overtliManualSize, undefined, 'selection/autosize does not save a manual size');
assert.deepEqual(Array.from(node.computeSize()),[900,760], 'autosize remains available before a manual resize');
const saved = {provider:'Codex', model:'actual-model', guide:'FLUX.2 Klein 9B',
  enabled:true, autoUnload:true, constantPrompt:'Preserve authored constant', constantEnabled:false};
widget.value = JSON.stringify(saved);
context.installSuite(node, true);
assert.equal(node.widgets.filter(w => w.name === 'overtli_studio').length, 1);
assert.deepEqual(JSON.parse(widget.value), saved, 'loading the UI must not rewrite saved state');
const panel = node.widgets.find(w => w.name === 'overtli_studio').element;
const sizeDetails = panel.children.find(x => x.tagName === 'details' && x.children[0]?.textContent === 'Node size');
const sizeFields = sizeDetails.children.filter(x => x.tagName === 'input');
const applySize = sizeDetails.children.find(x => x.tagName === 'button');
sizeFields[0].value = '760'; sizeFields[1].value = '520'; applySize.onclick();
assert.deepEqual(Array.from(node.properties.overtliManualSize), [760,520], 'Studio size controls save explicit geometry');
node.size = [1500,1100]; node.onResize(node.size);
assert.deepEqual(Array.from(node.size), [760,520], 'Studio autosize keeps explicit geometry');
const controls = panel.children.find(x => x.className === 'ovstudio-row');
assert.equal(controls.children[0].value, 'Codex');
assert.equal(controls.children[1].value, 'actual-model');
const guide = panel.children.find(x => x.tagName === 'select');
assert.equal(guide.value, 'FLUX.2 Klein 9B');
guide.value = 'Qwen Image 2.1'; guide.onchange();
assert.equal(JSON.parse(widget.value).constantEnabled, false);
assert.equal(JSON.parse(widget.value).constantPrompt, saved.constantPrompt);
widget.value = JSON.stringify({...JSON.parse(widget.value),constantPrompt:'Edited from director'});
guide.value = 'H3 Base'; guide.onchange();
assert.equal(JSON.parse(widget.value).constantPrompt, 'Edited from director');
node.comfyClass = 'OvertliStudioSuite';
extensions.find(extension => extension.name === 'Overtli.Studio.Director').nodeCreated(node);
node.properties.overtliStudioState = saved;
widget.value = '{}';
node.onConfigure();
assert.deepEqual(JSON.parse(widget.value), saved, 'nested graph configure restores saved properties');
assert.deepEqual(Array.from(node.size), [760,520], 'Studio configure keeps saved geometry');
assert.equal(node._ovStudioGuideControl.value, 'FLUX.2 Klein 9B');
const stablePanel=node._ovPromptPanel.panel;
const reused=context.directorPromptPanel(node,{studio:true,guide:'FLUX.2 Klein 9B',getPrompt:()=>'',setPrompt(){}});
assert.equal(reused,stablePanel,'Director redraw preserves pending preflight and accordion controls');
console.log('Studio saved-state hydration and shared constant updates: OK');
