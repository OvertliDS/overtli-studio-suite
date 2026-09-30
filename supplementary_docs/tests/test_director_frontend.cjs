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
vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/director_layout.js'),'utf8').replace(/export /g,''),context);
const source = fs.readFileSync(path.join(__dirname, '../../web/director_shared.js'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '').replace(/export /g, '');
vm.runInContext(source + '\nthis.installSuite = installSuite;', context);
assert.deepEqual(Array.from(context.scopeFiles(['OvertliDS/addtl/private.png', 'customer/addtl/ordinary.png', 'ordinary.png'], {properties:{overtliAddtl:true}})), ['OvertliDS/addtl/private.png']);
assert.deepEqual(Array.from(context.scopeFiles(['OvertliDS/addtl/private.png', 'customer/addtl/ordinary.png', 'ordinary.png'], {})), ['customer/addtl/ordinary.png', 'ordinary.png']);
const widget = {name: 'state', value:'{}'};
const node = { widgets:[widget], properties:{}, graph:{change(){}},
  addDOMWidget(name, type, element) { this.widgets.push({name,type,element}); } };
context.installSuite(node);
node.size=[900,760];node.onResize(node.size);
assert.deepEqual(Array.from(node.computeSize()),[900,760], 'autosize preserves selected dimensions');
node.size=[850,600];node.onResize(node.size);
assert.deepEqual(Array.from(node.properties.overtliManualSize),[850,600], 'manual size is saved');
const saved = {provider:'Codex', model:'actual-model', guide:'FLUX.2 Klein 9B',
  enabled:true, autoUnload:true, constantPrompt:'Preserve authored constant', constantEnabled:false};
widget.value = JSON.stringify(saved);
context.installSuite(node, true);
assert.equal(node.widgets.filter(w => w.name === 'overtli_studio').length, 1);
assert.deepEqual(JSON.parse(widget.value), saved, 'loading the UI must not rewrite saved state');
const panel = node.widgets.find(w => w.name === 'overtli_studio').element;
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
extensions[0].nodeCreated(node);
node.properties.overtliStudioState = saved;
widget.value = '{}';
node.onConfigure();
assert.deepEqual(JSON.parse(widget.value), saved, 'nested graph configure restores saved properties');
assert.equal(node._ovStudioGuideControl.value, 'FLUX.2 Klein 9B');
const stablePanel=node._ovPromptPanel.panel;
const reused=context.directorPromptPanel(node,{studio:true,guide:'FLUX.2 Klein 9B',getPrompt:()=>'',setPrompt(){}});
assert.equal(reused,stablePanel,'Director redraw preserves pending preflight and accordion controls');
console.log('Studio saved-state hydration and shared constant updates: OK');
