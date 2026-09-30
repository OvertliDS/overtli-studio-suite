import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";
import { installDirectorSizing, sizingControls } from "./director_layout.js";

export const DEFAULT_CONSTANT = "Masterpiece cinematic 8k resolution, photorealistic. Maintaining absolute character consistency and facial structure throughout the shot. Seamless, fluid, and natural human movement, strictly respecting real-world physics, biological anatomy, and natural weight distribution. Perfect anatomy, correct proportions, no morphing, no extra limbs, no warping. Ultra-detailed textures, realistic skin pores, cinematic professional lighting, highly detailed environment.";
const el = (tag, text = "") => { const e = document.createElement(tag); e.textContent = text; return e; };
const button = (text, fn) => { const b = el("button", text); b.type = "button"; b.onclick = fn; return b; };
const input = (value, placeholder = "") => { const e = el("input"); e.value = value || ""; e.placeholder = placeholder; return e; };
function css() {
  if (document.getElementById("ovstudio-css")) return;
  const style = el("style"); style.id = "ovstudio-css";
  style.textContent = `.ovstudio{box-sizing:border-box;background:#14212a;color:#e7edf2;border:1px solid #426075;border-radius:10px;padding:12px;font:12px/1.45 system-ui;min-width:0}.ovstudio h3{margin:0 0 8px}.ovstudio label{display:block;margin:8px 0 3px}.ovstudio textarea,.ovstudio input,.ovstudio select,.ovprompt-search input{box-sizing:border-box;background:#0b151c;color:#edf3f7;border:1px solid #486071;border-radius:5px;padding:7px;max-width:100%;min-width:0}.ovstudio textarea{width:100%;white-space:pre-wrap;overflow-wrap:anywhere;resize:vertical;min-height:100px}.ovstudio button,.ovprompt-search button{background:#233b4c;color:#eef7fc;border:1px solid #52758a;border-radius:5px;padding:5px 9px;cursor:pointer}.ovstudio button:disabled{opacity:.5;cursor:wait}.ovstudio-row,.ovprompt-search{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0;align-items:center}.ovstudio-row input,.ovstudio-row select{flex:1}.ovstudio-status,.ovprompt-count{font:11px/1.4 system-ui;color:#a7c7d8;white-space:pre-wrap}.ovstudio-preview{max-height:220px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:#09141a;padding:8px;border-radius:5px}.ovstudio details{margin:9px 0}.ovstudio summary{cursor:pointer}.ovprompt-search{background:#14212a;border:1px solid #426075;padding:6px;border-radius:5px}.ovstudio-video{width:100%;max-height:400px;background:#050a0d}`;
  document.head.append(style);
}
export function isAddtl(node) {
  const graph = node?.graph?.rootGraph || app.rootGraph || node?.graph;
  return !!node?.properties?.overtliAddtl || !!graph?.extra?.overtliAddtl || !!graph?._nodes?.some(n => n.properties?.overtliAddtl);
}
export function scopeFiles(values, node) {
  const addtl = isAddtl(node);
  return values.filter(v => /^OvertliDS[\\/]addtl[\\/]/i.test(String(v)) === addtl);
}
export function appendConstant(prompt, constant, enabled = true) {
  if (!enabled || !String(constant || "").trim()) return String(prompt || "");
  return String(prompt || "").split(/^\s*\[Constant\]\s*$/im)[0].trimEnd() + "\n\n[Constant]\n" + String(constant).replace(/^\s*\[Constant\]\s*/i, "").trim();
}
export function enhanceEditor(area) {
  if (area._ovEditor) return area;
  area._ovEditor = true; css(); area.wrap = "soft";
  area.style.whiteSpace = "pre-wrap"; area.style.overflowWrap = "anywhere"; area.style.boxSizing = "border-box";
  const count = el("div"); count.className = "ovprompt-count";
  const update = () => { count.textContent = `${area.value.length.toLocaleString()} characters · ~${Math.ceil(area.value.length / 4).toLocaleString()} tokens (estimate)`; area.style.height = Math.min(520, Math.max(110, area.scrollHeight)) + "px"; };
  area.addEventListener("input", update);
  queueMicrotask(() => { if (area.parentElement) area.after(count); update(); });
  area.addEventListener("keydown", e => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "f") return;
    e.preventDefault(); e.stopPropagation();
    if (area._ovSearch?.isConnected) { area._ovSearch.querySelector("input").focus(); return; }
    const bar = el("div"); bar.className = "ovprompt-search"; area._ovSearch = bar;
    const find = input("", "Find literal text"), replace = input("", "Replace with"), status = el("span"), sensitive = el("input"); sensitive.type = "checkbox";
    const label = el("label", "Match case "); label.append(sensitive);
    let nextAt = 0;
    const matches = () => {
      if (!find.value) return [];
      const source = sensitive.checked ? area.value : area.value.toLocaleLowerCase(), needle = sensitive.checked ? find.value : find.value.toLocaleLowerCase();
      const positions = []; let at = 0;
      while ((at = source.indexOf(needle, at)) >= 0) { positions.push(at); at += needle.length; }
      return positions;
    };
    const refresh = () => { status.textContent = `${matches().length} matches`; nextAt = 0; };
    const next = () => { const rows = matches(); if (!rows.length) return; const at = rows.find(x => x >= nextAt) ?? rows[0]; area.focus(); area.setSelectionRange(at, at + find.value.length); nextAt = at + find.value.length; status.textContent = `${rows.indexOf(at)+1}/${rows.length}`; };
    const changed = () => { area.dispatchEvent(new Event("input", { bubbles: true })); area.dispatchEvent(new Event("change", { bubbles: true })); refresh(); };
    bar.append(find, replace, label, button("Next", next), button("Replace", () => {
      if (!matches().includes(area.selectionStart) || area.selectionEnd-area.selectionStart !== find.value.length) { next(); return; }
      area.setRangeText(replace.value, area.selectionStart, area.selectionEnd, "end"); changed(); next();
    }), button("Replace all", () => { const positions = matches(); for (const at of positions.reverse()) area.value = area.value.slice(0, at) + replace.value + area.value.slice(at + find.value.length); changed(); }), status, button("Close", () => { bar.remove(); area.focus(); }));
    find.oninput = refresh; sensitive.onchange = refresh;
    bar.onkeydown = e => { e.stopPropagation(); if (e.key === "Escape") { bar.remove(); area.focus(); } if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); next(); } };
    area.before(bar); find.focus(); refresh();
  });
  return area;
}
export function textEditor(value, change) {
  const area = el("textarea"); area.value = value || ""; area.oninput = () => change(area.value); return enhanceEditor(area);
}
async function json(url, body) {
  const response = await fetch(api.apiURL(url), body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json(); if (!response.ok || data.error) throw Error(data.error || `Request failed (${response.status})`); return data;
}
function suiteNode(host) {
  const seen=new Set();const walk=g=>{if(!g||seen.has(g))return null;seen.add(g);for(const n of g._nodes||[]){if((n.comfyClass||n.type)==="OvertliStudioSuite")return n;const found=walk(n.subgraph||app.rootGraph?.subgraphs?.get?.(n.type));if(found)return found}return null};return walk(host?.graph);
}
function suiteState(host) { const n = suiteNode(host), w = n?.widgets?.find(w => w.name === "state"); let s = {}; try { s = JSON.parse(w?.value || "{}"); } catch {} return { n, w, s }; }
function updateStudio(host, changes) {
  const current = suiteState(host); if (!current.w) return;
  current.s = {...current.s, ...changes}; current.w.value = JSON.stringify(current.s);
  current.n.properties ||= {}; current.n.properties.overtliStudioState = {...current.s}; host.graph?.change?.();
}
function stylePanel(host) {
  const details = el('details'); details.append(el('summary', 'Style stack · presets and custom guidance'));
  const filter = input('', 'Find a style'), category = el('select'), choices = el('select');
  const selected = el('div'), preview = el('div'); preview.className = 'ovstudio-preview';
  const custom = textEditor(suiteState(host).s.customStyle || '', value => updateStudio(host,{customStyle:value}));
  custom.placeholder = 'Custom style guidance (optional)'; let catalog = [];
  const render = () => {
    choices.replaceChildren(el('option','Choose a style'));
    const search = filter.value.toLowerCase();
    for (const item of catalog.filter(x => (!category.value || category.value === 'All' || x.category === category.value) && (x.label+' '+x.description+' '+x.tags.join(' ')).toLowerCase().includes(search))) choices.append(el('option',item.label));
    selected.replaceChildren();
    for (const label of suiteState(host).s.styles || []) selected.append(button('Remove '+label,()=>{updateStudio(host,{styles:(suiteState(host).s.styles || []).filter(x=>x!==label)});render();}));
  };
  choices.onchange=()=>{const item=catalog.find(x=>x.label===choices.value);preview.textContent=item?item.description+'\n\n'+item.instruction:'';};
  const add=button('Add style',()=>{const styles=suiteState(host).s.styles || []; if(styles.length>=7){preview.textContent='Seven style layers are supported; remove one first.';return;}if(catalog.some(x=>x.label===choices.value)){updateStudio(host,{styles:[...new Set([...styles,choices.value])]});render();}});
  details.append(filter,category,choices,add,selected,preview,custom);
  filter.oninput=render;category.onchange=render;
  details.addEventListener('toggle',async()=>{if(!details.open)return;try{catalog=(await json('/overtli/studio/styles')).styles;category.replaceChildren(el('option','All'));for(const c of [...new Set(catalog.map(x=>x.category))].sort())category.append(el('option',c));render();}catch(e){preview.textContent=e.message;}});
  return details;
}
function finalPromptPanel(host) {
  const details = el('details'); details.append(el('summary','Final prompts sent to the model'));
  const status=el('div');status.className='ovstudio-status';
  status.textContent='Prepare a current snapshot after edits. Enabled enhancement runs once and its identical next run reuses the result for ten minutes.';
  const picker=el('select'), counts=el('div'), area=textEditor('',()=>{});area.readOnly=true; let rows=[];
  picker.onchange=()=>{const row=rows[Number(picker.value)];area.value=row?.prompt || '';area.dispatchEvent(new Event('input'));const b=row?.budget;counts.textContent=b?`${b.characters} characters · ${b.utf16_units} UTF-16 units · ${b.tokens == null ? 'exact token count unavailable' : b.tokens+' text/template tokens'}\n${b.policy}\n${b.token_count_kind}`:'';};
  const prepare=button('Prepare final prompts',async()=>{prepare.disabled=true;status.textContent='Resolving current graph prompts…';try{
    const graph=await app.graphToPrompt();const data=await json('/overtli/studio/preflight',{output:graph.output});rows=data.prompts;
    picker.replaceChildren();rows.forEach((row,index)=>{const option=el('option',row.label+' · '+row.characters+' characters');option.value=String(index);picker.append(option);});picker.value=String(Math.max(0,rows.findIndex(row=>row.characters>0)));picker.onchange();
    status.textContent=(data.complete?'Prepared current snapshot. ':'Resolve prompt errors before generating. ')+data.note+'\n'+[...data.unresolved.map(x=>x.label+': '+x.error),...rows.flatMap(x=>[...(x.budget?.errors || []),...(x.budget?.warnings || [])].map(y=>x.label+': '+y))].join('\n');
  }catch(e){status.textContent=e.message;}finally{prepare.disabled=false;}});
  details.append(prepare,picker,counts,area,status);return details;
}
export function directorPromptPanel(host, options) {
  // Graph preparation updates seeds/state and can redraw a Director while a
  // preflight request is pending. Keep this panel and its controls alive.
  if (host._ovPromptPanel) { host._ovPromptPanel.refresh(options); return host._ovPromptPanel.panel; }
  css(); const panel = el("section"); panel.className = "ovstudio";
  panel.append(el("h3", "Prompt studio"), el("div", "Ctrl+F in a prompt opens local find/replace. Token counts are estimates."), sizingControls(host));
  const authored = textEditor(options.getPrompt(), value => { options.setPrompt(value); }); panel.append(authored);
  const current = suiteState(host); if(current.w){current.s.guide=options.guide;current.w.value=JSON.stringify(current.s);if(current.n._ovStudioGuideControl)current.n._ovStudioGuideControl.value=options.guide;} const initial = options.getConstant?.() ?? current.s.constantPrompt ?? "";
  const constant = textEditor(initial, value => {
    options.setConstant?.(value);
    if (current.w) { Object.assign(current.s, suiteState(host).s); current.s.constantPrompt = value; current.s.constantEnabled = enabled.checked; current.w.value = JSON.stringify(current.s); host.graph?.change?.(); }
  });
  const enabled = el("input"); enabled.type = "checkbox"; enabled.checked = options.constantEnabled?.() ?? current.s.constantEnabled !== false;
  enabled.onchange = () => { options.setConstantEnabled?.(enabled.checked); if (current.w) { Object.assign(current.s, suiteState(host).s); current.s.constantEnabled = enabled.checked; current.w.value = JSON.stringify(current.s); host.graph?.change?.(); } };
  const toggle = el("label", "Append editable [Constant] block "); toggle.append(enabled); panel.append(toggle, constant);
  panel.append(button("Use example constant", () => { constant.value = DEFAULT_CONSTANT; constant.dispatchEvent(new Event("input")); }));
  const status = el("div"); status.className = "ovstudio-status";
  const actions = el("div"); actions.className = "ovstudio-row";
  actions.append(button("Check structure", async () => { try { const r = await json("/overtli/studio/prompt", { prompt: authored.value, state: { guide: options.guide, constantPrompt: constant.value, constantEnabled: enabled.checked }, reference_tags: options.referenceTags?.() || "", duration: options.duration?.() }); status.textContent = [...r.checks.errors, ...r.checks.warnings].join("\n") || "Checks passed."; } catch (e) { status.textContent = e.message; } }));
  if (current.n && !options.studio) actions.append(button("Open enhancer node", () => { const canvas = app.canvas; if (!canvas) return; if (current.n.graph && canvas.graph !== current.n.graph) canvas.setGraph(current.n.graph); canvas.deselectAll?.(); canvas.select?.(current.n); canvas.centerOnNode?.(current.n); canvas.setDirty?.(true, true); }));
  panel.append(actions, status);
  panel.append(stylePanel(host),finalPromptPanel(host));
  const details = el("details"), summary = el("summary", isAddtl(host) ? "Addtl prompt library" : "Prompt library"); details.append(summary); panel.append(details);
  const filter = input("", "Search name, prompt, tags"), category = el("select"), names = el("select"), preview = el("div"); preview.className = "ovstudio-preview";
  const name = input("", "Save name"), tags = input("", "Comma-separated tags"), notes = input("", "Notes"), saveCategory = input("General", "Category");
  let entries = [];
  const row = el("div"); row.className = "ovstudio-row"; row.append(filter, category);
  details.append(row, names, preview, name, saveCategory, tags, notes);
  const refresh = async () => {
    try { const selected = category.value || "All", data = await json(`/overtli/studio/library?addtl=${isAddtl(host) ? 1 : 0}&search=${encodeURIComponent(filter.value)}&category=${encodeURIComponent(selected)}`); entries = data.entries; category.replaceChildren(); for (const c of ["All", ...data.categories.filter(x => x !== "All")]) { const o = el("option", c); o.value = c; category.append(o); } category.value = selected; names.replaceChildren(el("option", "Select a saved prompt")); for (const e of entries) { const o = el("option", e.name); o.value = e.name; names.append(o); } preview.textContent = `${entries.length} prompts`; } catch (e) { preview.textContent = e.message; }
  };
  names.onchange = () => { const e = entries.find(x => x.name === names.value); preview.textContent = e ? `${e.name} · ${e.category} · used ${e.uses || 0}\n${e.notes || ""}\n\n${e.prompt}` : ""; if (e) { name.value = e.name; tags.value = e.tags.join(", "); notes.value = e.notes; saveCategory.value = e.category; } };
  let searchTimer; filter.oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(refresh, 250); }; category.onchange = refresh;
  const libActions = el("div"); libActions.className = "ovstudio-row";
  libActions.append(button("Load selected", async () => { try { const { entry } = await json("/overtli/studio/library", { action: "load", name: names.value, addtl: isAddtl(host) }); const pieces = entry.prompt.split(/^\s*\[Constant\]\s*$/im); authored.value = pieces[0].trim(); authored.dispatchEvent(new Event("input")); const recipe=entry.studio || {}; updateStudio(host,{styles:recipe.styles || [],customStyle:recipe.customStyle || ''}); constant.value = recipe.constantPrompt ?? pieces[1]?.trim() ?? ""; enabled.checked=recipe.constantEnabled ?? true; enabled.onchange(); constant.dispatchEvent(new Event("input")); status.textContent = "Loaded " + entry.name + ' with saved styles and constants. Reopen Style stack to refresh its selections.'; } catch (e) { status.textContent = e.message; } }), button("Save new", () => save(false)), button("Update existing", () => save(true)), button("Refresh", refresh));
  async function save(overwrite) { try { await json("/overtli/studio/library", { name: name.value, prompt: authored.value, studio:{...suiteState(host).s,constantPrompt:constant.value,constantEnabled:enabled.checked}, category: saveCategory.value, tags: tags.value.split(",").map(x => x.trim()).filter(Boolean), notes: notes.value, overwrite, addtl: isAddtl(host) }); status.textContent = "Saved " + name.value; await refresh(); } catch (e) { status.textContent = e.message; } }
  details.append(libActions); details.addEventListener("toggle", () => { if (details.open) refresh(); });
  host._ovPromptPanel={panel,refresh:next=>{options=next;const value=options.getPrompt();if(document.activeElement!==authored&&authored.value!==value){authored.value=value;authored.dispatchEvent(new Event('input'));}const now=suiteState(host);if(now.w){Object.assign(current.s,now.s);current.w=now.w;current.s.guide=options.guide;now.w.value=JSON.stringify(current.s);}if(document.activeElement!==constant)constant.value=options.getConstant?.()??now.s.constantPrompt??'';enabled.checked=options.constantEnabled?.()??now.s.constantEnabled!==false;}};
  return panel;
}

function installSuite(node, rehydrate = false) {
  if (node._ovStudio && !rehydrate) return;
  if (rehydrate) {
    delete node._ovPromptPanel;
    const old = node.widgets?.find(w => w.name === "overtli_studio");
    old?.element?.remove(); old?.onRemove?.();
    if (old) node.widgets.splice(node.widgets.indexOf(old), 1);
  }
  node._ovStudio = true; css();
  const widget = node.widgets.find(w => w.name === "state"); let state = {}; try { state = JSON.parse(widget.value); } catch {}
  state = { provider: "LM Studio", model: "", guide: "H3 Ref2VA", enabled: false, autoUnload: true, ...node.properties?.overtliStudioState, ...state };
  if (rehydrate) widget.value = JSON.stringify(state);
  widget.type = "converted-widget"; widget.computeSize = () => [0, -4];
  for (const element of [widget.element, widget.inputEl]) if (element?.style) element.style.display = "none";
  const panel = el("section"); panel.className = "ovstudio"; const status = el("div"); status.className = "ovstudio-status";
  let lastSaved = { ...state };
  const save = () => { let current = {}; try { current = JSON.parse(widget.value || "{}"); } catch {} for (const [key, value] of Object.entries(current)) if (state[key] === lastSaved[key]) state[key] = value; widget.value = JSON.stringify(state); lastSaved = { ...state }; node.properties ||= {}; node.properties.overtliStudioState = { ...state }; node.graph?.change?.(); };
  panel.append(el("h3", "OVERTLI Studio"));
  const provider = el("select"), model = el("select"), guide = el("select");
  for (const p of ["LM Studio", "Ollama", "Codex", "Pollinations", "OpenAI-compatible"]) provider.append(el("option", p)); provider.value = state.provider;
  for (const g of ["H3 Ref2VA", "H3 Base", "FLUX.2 Klein 9B", "Qwen Image 2.1"]) guide.append(el("option", g)); guide.value = state.guide; node._ovStudioGuideControl = guide;
  const refresh = async (force = false) => { status.textContent = "Discovering models…"; model.disabled = true; try { const r = await json(`/overtli/studio/models?provider=${encodeURIComponent(state.provider)}&refresh=${force ? 1 : 0}`); model.replaceChildren(el("option", "Choose model")); for (const m of r.models) { const o = el("option", m.label || m.id); o.value = m.id; model.append(o); } if (r.models.some(m => m.id === state.model)) model.value = state.model; else { state.model = ""; save(); } status.textContent = `${r.models.length} models. Discovery is cached; use Refresh after provider changes.`; } catch (e) { status.textContent = e.message; } finally { model.disabled = false; } };
  provider.onchange = () => { state.provider = provider.value; state.model = ""; save(); refresh(); }; model.onchange = () => { state.model = model.value === "Choose model" ? "" : model.value; save(); }; guide.onchange = () => { state.guide = guide.value; save(); };
  const controls = el("div"); controls.className = "ovstudio-row"; controls.append(provider, model, button("Refresh models", () => refresh(true))); panel.append(controls, guide);
  for (const [key, label] of [["enabled", "Enhance when workflow runs"], ["autoUnload", "Fully unload selected local model after enhance/test"]]) { const check = el("input"); check.type = "checkbox"; check.checked = state[key]; check.onchange = () => { state[key] = check.checked; save(); }; const l = el("label", label + " "); l.append(check); panel.append(l); }
  const budget = input(String(state.maxTokens || 2048)); budget.type = "number"; budget.min = "256"; budget.max = "16384"; budget.step = "256"; budget.onchange = () => { state.maxTokens = Math.max(256, Math.min(16384, Number(budget.value) || 2048)); save(); }; const budgetLabel = el("label", "Local / API response token budget (Codex uses its own budget) "); budgetLabel.append(budget); panel.append(budgetLabel);
  const contextBudget=input(String(state.contextTokens || 8192));contextBudget.type='number';contextBudget.min='2048';contextBudget.max='131072';contextBudget.step='1024';contextBudget.onchange=()=>{state.contextTokens=Math.max(2048,Math.min(131072,Number(contextBudget.value)||8192));save();};const contextLabel=el('label','Local context budget (tokens; default 8192) ');contextLabel.append(contextBudget);panel.append(contextLabel,el('div','LM Studio and Ollama use this context budget, expanding to fit guides and output. Codex and hosted APIs control their own context window.'));
  const instruction = textEditor(state.instructions || "", value => { state.instructions = value; save(); }); instruction.placeholder = "Extra instructions (optional)"; panel.append(instruction);
  const source = textEditor("", () => {}); source.placeholder = "Paste a prompt to test the selected provider"; const result = textEditor("", () => {}); result.readOnly = true;
  panel.append(button("Use connected prompt for test", () => { const upstream = node.getInputNode?.(0); const w = upstream?.widgets?.find(w => w.name === "text" || w.name === "prompt"); if (!w) { status.textContent = "Connected source has no editable prompt widget; paste the resolved prompt here."; return; } source.value = String(w.value || ""); source.dispatchEvent(new Event("input")); }));
  const test = button("Enhance / test", async () => { save(); test.disabled = true; status.textContent = "Enhancing; selected local model will unload before completion…"; try { const r = await json("/overtli/studio/prompt", { action: "test", prompt: source.value, state }); result.value = r.prompt; result.dispatchEvent(new Event("input")); status.textContent = [...r.checks.errors, ...r.checks.warnings].join("\n") || "Completed. Prompt checks passed."; } catch (e) { status.textContent = e.message; } finally { test.disabled = false; } });
  panel.append(source, test, result, status);
  const upstream=node.getInputNode?.(0), upstreamText=upstream?.widgets?.find(w=>w.name==='text'||w.name==='prompt'||w.name==='value');
  const override=el('input');override.type='checkbox';override.checked=!!state.promptOverrideEnabled;override.onchange=()=>{state.promptOverrideEnabled=override.checked;save();};const overrideLabel=el('label','Use Studio authored prompt instead of connected source ');overrideLabel.append(override);panel.append(overrideLabel);
  panel.append(directorPromptPanel(node,{studio:true,guide:state.guide,getPrompt:()=>state.promptOverrideEnabled?state.promptOverride || '':String(upstreamText?.value || ''),setPrompt:value=>{if(!override.checked && upstreamText){upstreamText.value=value;upstreamText.callback?.(value);node.graph?.change?.();}else{state.promptOverride=value;override.checked=true;state.promptOverrideEnabled=true;save();}},getConstant:()=>suiteState(node).s.constantPrompt || '',setConstant:value=>updateStudio(node,{constantPrompt:value}),constantEnabled:()=>suiteState(node).s.constantEnabled!==false,setConstantEnabled:value=>updateStudio(node,{constantEnabled:value})}));
  const settings = el("details"); settings.append(el("summary", "Provider connections · saved locally")); panel.append(settings);
  const fields = {}; for (const key of ["lmstudio_base_url", "lmstudio_api_key", "ollama_base_url", "ollama_api_key", "openai_compatible_base_url", "openai_compatible_api_key", "pollinations_api_key", "codex_executable"]) { const value = input("", key.replaceAll("_", " ")); if (key.endsWith("api_key")) { value.type = "password"; value.autocomplete = "new-password"; } settings.append(el("label", key.replaceAll("_", " ")), value); fields[key] = value; }
  settings.addEventListener("toggle", async () => { if (!settings.open) return; try { const data = await json("/overtli/studio/settings"); for (const [key, value] of Object.entries(fields)) { if (key.endsWith("api_key")) value.placeholder = data[key] ? "Key stored · blank preserves" : "No key stored"; else value.value = data[key] || ""; } } catch (e) { status.textContent = e.message; } });
  settings.append(button("Save connections", async () => { try { await json("/overtli/studio/settings", Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, v.value]))); for (const [k, v] of Object.entries(fields)) if (k.endsWith("api_key")) v.value = ""; status.textContent = "Connections saved locally. Refresh models when ready."; } catch (e) { status.textContent = e.message; } }));
  for (const key of Object.keys(fields).filter(k => k.endsWith("api_key"))) settings.append(button("Clear stored " + key.replaceAll("_", " "), async () => { try { await json("/overtli/studio/settings", { clear_keys: [key] }); fields[key].value = ""; fields[key].placeholder = "No key stored"; status.textContent = "Stored key cleared."; } catch (e) { status.textContent = e.message; } }));
  const dom = node.addDOMWidget("overtli_studio", "overtli_studio", panel, { serialize: false, hideOnZoom: false, getMinHeight: () => 480 });
  if (dom) { dom.computeLayoutSize = () => ({minWidth:700,minHeight:480}); dom.options ||= {}; dom.options.getMinHeight = () => 480; }
  installDirectorSizing(node, panel, [700, 480]); panel.append(sizingControls(node));
  // Discovery is user initiated; loading workflows never polls providers.
  if (state.model) { const o = el("option", state.model); o.value = state.model; model.append(o); model.value = state.model; } else model.append(el("option", "Choose model"));
}
const scopedDiscovery = new Map();
async function scopeNode(node) {
  if (!node.properties?.overtliDirectorManaged) return;
  try {
    const scope = isAddtl(node) ? 1 : 0;
    let cached = scopedDiscovery.get(scope);
    if (!cached || Date.now() - cached.time > 30000) { cached = { time: Date.now(), promise: json(`/overtli/studio/files?addtl=${scope}`) }; scopedDiscovery.set(scope, cached); }
    const data = await cached.promise;
    for (const w of node.widgets || []) {
      if (!/^(?:image|video|audio|file)$/.test(w.name) || !Array.isArray(w.options?.values)) continue;
      const old = w.options.values, sample = old.find(x => /\.[a-z0-9]+$/i.test(String(x))) || "";
      const extensions = /\.(mp4|mov|webm|mkv|avi|m4v)$/i.test(sample) || w.name === "video" ? /\.(mp4|mov|webm|mkv|avi|m4v)$/i : /\.(wav|mp3|flac|ogg|m4a|aac)$/i.test(sample) || w.name === "audio" ? /\.(wav|mp3|flac|ogg|m4a|aac)$/i : /\.(png|jpe?g|webp|bmp|gif|tiff?)$/i;
      w.options.values = data.files.filter(x => extensions.test(x));
      if (w.value && scopeFiles([w.value], node).length && !w.options.values.includes(w.value)) w.options.values.unshift(w.value);
    }
    for (const upload of node.widgets || []) {
      if (upload.type !== "button" || !/upload/i.test(upload.name)) continue;
      upload.callback = () => {
        const chooser = el("input"); chooser.type = "file";
        const target = node.widgets.find(w => /^(?:image|video|audio|file)$/.test(w.name));
        if (!target) return;
        chooser.accept = /Video/.test(node.comfyClass || node.type) ? "video/*" : /Audio/.test(node.comfyClass || node.type) ? "audio/*" : "image/*";
        chooser.onchange = async () => {
          const file = chooser.files?.[0]; if (!file) return;
          try {
            const form = new FormData(); form.append("image", file, file.name); form.append("type", "input");
            form.append("subfolder", scope ? "OvertliDS/addtl" : "OvertliDS/references");
            const response = await api.fetchApi("/upload/image", { method: "POST", body: form });
            const result = await response.json(); if (!response.ok) throw Error(result.error || "Upload failed");
            const value = (result.subfolder ? result.subfolder + "/" : "") + result.name;
            if (!target.options.values.includes(value)) target.options.values.unshift(value);
            target.value = value; target.callback?.(value); node.graph?.change?.(); scopedDiscovery.delete(scope);
          } catch (e) { alert("Reference upload failed: " + e.message); }
        };
        chooser.click();
      };
    }
  } catch (e) { console.error("[OVERTLI] Scoped input discovery failed:", e.message); }
}
app.registerExtension({ name: "Overtli.Studio.Director", nodeCreated(node) { const original = node.onConfigure; node.onConfigure = function(...args) { const result = original?.apply(this, args); queueMicrotask(() => { if ((this.comfyClass || this.type) === "OvertliStudioSuite") installSuite(this, true); scopeNode(this); }); return result; }; if ((node.comfyClass || node.type) === "OvertliStudioSuite") queueMicrotask(() => installSuite(node)); }, loadedGraphNode(node) { if ((node.comfyClass || node.type) === "OvertliStudioSuite") queueMicrotask(() => installSuite(node, true)); queueMicrotask(() => scopeNode(node)); } });

// Extend the existing Pixaroma submit path without changing its frontend ID.
// Metadata inputs are linked to the actual executed Studio/LoRA outputs.
app.registerExtension({ name: "Overtli.Studio.SaveMetadata", setup() {
  const original = app.graphToPrompt.bind(app);
  app.graphToPrompt = async (...args) => {
    const result = await original(...args), output = result.output || {};
    const studio = Object.entries(output).find(([,n]) => n.class_type === "OvertliStudioSuite");
    if (!studio) return result;
    const lora = Object.entries(output).find(([,n]) => n.class_type === "OvertliH3OptionalLoRAStack");
    const director = (app.graph?._nodes || []).find(n => (n.comfyClass || n.type) === "OvertliH3ReferenceDirectorUI");
    for (const n of Object.values(output)) {
      if (n.class_type !== "PixaromaSaveVideo") continue;
      n.inputs ||= {}; n.inputs.prompt_text = [studio[0], 0];
      if (lora) n.inputs.lora_plan = [lora[0], 1];
      if (director) n.inputs.director_state = JSON.stringify({ ...director.properties?.overtliH3ReferenceState, production: director.properties?.overtliH3ProductionProfile });
    }
    return result;
  };
} });
