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
const canvasActions = [];
const context = { console, queueMicrotask: fn => fn(), Map, Date, JSON, Math, Number, String,
  document: { getElementById: () => true, createElement: tag => new Element(tag) },
  window:{addEventListener(){},removeEventListener(){}},
  app: { registerExtension(extension) { extensions.push(extension); }, canvas: {
    selectNode(node) { canvasActions.push(['select', node.id]); },
    centerOnNode(node) { canvasActions.push(['center', node.id]); },
    setDirty() { canvasActions.push(['dirty']); },
  } }, api: {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/director_layout.js'),'utf8').replace(/^import .*;\r?\n/gm, '').replace(/export /g,''),context);
const source = fs.readFileSync(path.join(__dirname, '../../web/director_shared.js'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '').replace(/export /g, '');
vm.runInContext(source + '\nthis.installSuite = installSuite;', context);
const descendants = (root, predicate, found = []) => {
  if (!root || typeof root !== 'object') return found;
  if (predicate(root)) found.push(root);
  for (const child of root.children || []) descendants(child, predicate, found);
  return found;
};
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
const standaloneText = descendants(panel, x => typeof x.textContent === 'string').map(x => x.textContent).join('\n');
for (const standaloneFlow of ['Prompt studio','Enhance / test','Prompt library','Style stack','Final prompts sent'])
  assert.equal(standaloneText.includes(standaloneFlow),true,`standalone Suite retains ${standaloneFlow}`);
assert.equal(descendants(panel, x => x.tagName === 'textarea').some(x => x.placeholder === 'Paste a prompt to test the selected provider'),true,
  'standalone Suite retains the pasted test editor');
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

const pairGraph = {_nodes:[], change(){this.changes=(this.changes || 0)+1;}};
const legacyOverride = 'Saved authored text retained until explicitly moved';
const pairWidget = {name:'state', value:JSON.stringify({provider:'Codex',model:'actual-model',guide:'H3 Ref2VA',
  enabled:true,autoUnload:false,promptOverrideEnabled:true,promptOverride:legacyOverride})};
const pairSuite = {id:30,comfyClass:'OvertliStudioSuite',properties:{overtliDirectorNodeId:20},widgets:[pairWidget],graph:pairGraph,
  computeSize(){return [900,760];},addDOMWidget(name,type,element){this.widgets.push({name,type,element});}};
pairGraph._nodes.push(pairSuite);
extensions.find(extension => extension.name === 'Overtli.Studio.Director').nodeCreated(pairSuite);
assert.equal(pairSuite._ovPromptPanel != null, true, 'a Studio created before its Director keeps its standalone authoring flow temporarily');
const director = {id:20,comfyClass:'OvertliH3ReferenceDirectorUI',properties:{overtliStudioNodeId:30},widgets:[],graph:pairGraph,
  onRemoved(){pairGraph._nodes = pairGraph._nodes.filter(node => node !== this);}};
pairGraph._nodes.push(director);
extensions.find(extension => extension.name === 'Overtli.Studio.Director').nodeCreated(director);
assert.equal(pairSuite._ovStudioPairKey,'paired:20','graph scan resolves the explicit pair after the Director appears');
const pairedPanel = pairSuite.widgets.find(w => w.name === 'overtli_studio').element;
assert.equal(pairSuite._ovPromptPanel, undefined, 'paired Suite no longer mounts a second prompt editor');
assert.equal(descendants(pairedPanel, x => x.tagName === 'textarea').length,0,'paired Suite has no authored or pasted test textarea');
const pairedText = descendants(pairedPanel, x => typeof x.textContent === 'string').map(x => x.textContent).join('\n');
for (const competingEditor of ['Prompt studio','Paste a prompt to test','Enhance / test','Prompt library','Style stack','Final prompts sent'])
  assert.equal(pairedText.includes(competingEditor),false,`paired Suite omits ${competingEditor}`);
assert.equal(pairedText.includes('The main Director owns prompts, styles, constants, the library, final inspection and inline enhancement.'),true,'paired Suite uses the plain source-owner note');
assert.equal(pairedText.includes('OvertliH3ReferenceDirectorUI'),false,'paired Suite does not expose internal node names');
assert.match(pairedText,/enabled Studio prompt override/,'active legacy override is explicitly called out');
assert.deepEqual(JSON.parse(pairWidget.value).promptOverrideEnabled,true,'pair discovery preserves an enabled override');
const providerAccordion = descendants(pairedPanel, x => x.tagName === 'details').find(x => x.children[0]?.textContent === 'Provider connections · saved locally');
assert.ok(providerAccordion,'paired Suite keeps provider connections in an accordion');
pairSuite.onConfigure();
extensions.find(extension => extension.name === 'Overtli.Studio.Director').loadedGraphNode(pairSuite);
assert.equal(pairSuite._ovStudioPairKey,'paired:20','save/reconfigure preserves the resolved pair');
assert.equal(JSON.parse(pairWidget.value).promptOverride,legacyOverride,'rehydration preserves saved override text');

let authoredPrompt = 'Main Director authored source';
const directorPanel = context.directorPromptPanel(director,{guide:'H3 Ref2VA',getPrompt:()=>authoredPrompt,setPrompt:value=>{authoredPrompt=value;}});
const authoredEditor = descendants(directorPanel, x => x.tagName === 'textarea')[0];
authoredEditor.value = 'Updated in the main Director'; authoredEditor.oninput();
assert.equal(authoredPrompt,'Updated in the main Director','Director editor remains the paired authored source');
assert.equal(authoredEditor.value,'Updated in the main Director','paired Studio refresh leaves the live source editor synchronized');
const focus = descendants(pairedPanel, x => x.tagName === 'button').find(x => x.textContent === 'Focus main Director');
focus.onclick();
assert.deepEqual(canvasActions.slice(-3),[['select',20],['center',20],['dirty']],'source-owner navigation focuses the paired Director');
const moveOverride = descendants(pairedPanel, x => x.tagName === 'button').find(x => x.textContent.includes('Move saved override to main Director and disable'));
assert.ok(moveOverride && !moveOverride.hidden && !moveOverride.disabled,'override migration is enabled only after the Director source editor is ready');
moveOverride.onclick();
assert.equal(authoredPrompt,legacyOverride,'explicit migration moves the saved override to the main Director');
assert.equal(JSON.parse(pairWidget.value).promptOverrideEnabled,false,'the override is disabled only after source confirmation');
assert.equal(JSON.parse(pairWidget.value).promptOverride,legacyOverride,'the old override text remains available for recovery');
assert.equal(moveOverride.hidden,true,'migration action is hidden once there is no enabled override');
director.onRemoved();
assert.equal(pairSuite._ovStudioPairKey,'waiting:20','Director removal rechecks and detaches the paired UI');
assert.ok(pairSuite._ovPromptPanel,'a Suite without a paired Director returns to standalone authoring');
console.log('Standalone authoring, explicit pair hydration, source ownership, override migration, and Director synchronization: OK');

(async () => {
  context.api.apiURL = url => url;
  context.fetch = async () => ({ok:true, json:async () => ({files:['OvertliDS/addtl/present.png']})});
  const changes=[];
  const present={name:'image',value:'OvertliDS/addtl/present.png',options:{values:['default.png']}};
  const missing={name:'image',value:'OvertliDS/addtl/missing.png',options:{values:['default.png']}};
  const scopeHost={comfyClass:'LoadImageWithSwitch',properties:{overtliAddtl:true,overtliDirectorManaged:true},widgets:[present,missing],
    onWidgetChanged(name,value,old,widget){changes.push({name,value,old,widget});}};
  await context.scopeNode(scopeHost);
  assert.deepEqual(Array.from(present.options.values),['OvertliDS/addtl/present.png']);
  assert.equal(present.value,'OvertliDS/addtl/present.png','discovery preserves authored selection');
  assert.equal(changes.length,1,'only a file verified by scoped discovery clears an initial stale warning');
  assert.equal(changes[0].widget,present);
  assert.equal(changes[0].old,changes[0].value);
  assert.equal(missing.options.values.includes(missing.value),true,'a missing authored selection remains recoverable');
  assert.equal(changes.some(change=>change.widget===missing),false,'missing files retain their diagnostic');
  console.log('Scoped discovery notifies confirmed selections and preserves missing-file diagnostics: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
