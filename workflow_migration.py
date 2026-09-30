"""Surgical, idempotent director workflow upgrades; preserve authored content."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil


def _file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _graphs(workflow):
    yield workflow
    yield from workflow.get("definitions", {}).get("subgraphs", [])


def _link_parts(link):
    if isinstance(link, dict):
        return link["id"], link["origin_id"], link["origin_slot"], link["target_id"], link["target_slot"]
    return link[:5]


def _rewire_source(link, source, slot):
    if isinstance(link, dict):
        link["origin_id"], link["origin_slot"] = source, slot
    else:
        link[1:3] = [source, slot]


def insert_studio(graph, source, guide, addtl=False):
    if any(n["type"] == "OvertliStudioSuite" for n in graph.get("nodes", [])):
        return
    links = graph.get("links", [])
    outgoing = [link for link in links if _link_parts(link)[1:3] == [source["id"], 0]]
    if not outgoing:
        outgoing = [link for link in links if tuple(_link_parts(link)[1:3]) == (source["id"], 0)]
    if not outgoing:
        return
    nid = max([int(n["id"]) for n in graph["nodes"] if isinstance(n["id"], int)] + [0]) + 1
    lid = max([int(_link_parts(link)[0]) for link in links] + [0]) + 1
    prompt = str((source.get("widgets_values") or [""])[0] or "")
    constant = re.split(r"(?im)^\s*\[Constant\]\s*$", prompt, maxsplit=1)
    state = {"provider": "LM Studio", "model": "", "guide": guide, "enabled": False, "autoUnload": True, "constantEnabled": True, "constantPrompt": constant[1].strip() if len(constant)>1 else ""}
    node = {"id": nid, "type": "OvertliStudioSuite", "title": "OVERTLI Studio · Prompt Director", "pos": [source.get("pos", [0,0])[0]-750, source.get("pos", [0,0])[1]], "size": [660,800], "flags": {}, "order": source.get("order",0)+1, "mode": 0, "inputs": [{"name":"prompt", "type":"STRING", "link":lid}], "outputs": [{"name":"prompt", "type":"STRING", "links":[_link_parts(link)[0] for link in outgoing]}, {"name":"checks", "type":"STRING", "links":[]}], "properties": {"Node name for S&R":"OvertliStudioSuite", "overtliDirectorManaged": True, "overtliAddtl": addtl, "overtliStudioState":state}, "widgets_values": [json.dumps(state)]}
    for link in outgoing:
        _rewire_source(link,nid,0)
    source["outputs"][0]["links"] = [lid]
    if links and isinstance(links[0],dict):
        links.append({"id":lid,"origin_id":source["id"],"origin_slot":0,"target_id":nid,"target_slot":0,"type":"STRING"})
        graph.setdefault("state",{}).update(lastNodeId=nid,lastLinkId=lid)
    else:
        links.append([lid,source["id"],0,nid,0,"STRING"])
        graph["last_node_id"]=max(graph.get("last_node_id",0),nid)
        graph["last_link_id"]=max(graph.get("last_link_id",0),lid)
    graph["nodes"].append(node)


def _stage_reference(value, input_root, receipts):
    if not isinstance(value,str) or not value or value.startswith("OvertliDS/addtl/"):
        return value
    value = value.removesuffix(" [input]")
    source = (input_root/value.replace("\\","/")).resolve()
    if not source.is_relative_to(input_root) or not source.is_file():
        return value
    digest = _file_hash(source)
    destination = input_root/"OvertliDS/addtl"/source.name
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists() and _file_hash(destination)!=digest:
        destination=destination.with_name(destination.stem+"_"+digest[:10]+destination.suffix)
    if not destination.exists():
        shutil.copy2(source,destination)
    receipts.append({"source":value,"staged":destination.relative_to(input_root).as_posix(),"sha256":digest})
    return destination.relative_to(input_root).as_posix()


def upgrade_director_workflow(workflow, *, addtl=False, input_root=None):
    receipts=[]
    if input_root:
        input_root=Path(input_root).resolve()
    workflow.setdefault("extra",{})["overtliDirectorParityVersion"]=1
    workflow["extra"]["overtliAddtl"]=bool(addtl)
    for graph in _graphs(workflow):
        for n in list(graph.get("nodes",[])):
            if addtl and n["type"] in {"LoadImage", "LoadVideo"}:
                n["type"] = "OvertliAddtl" + n["type"]
                n.setdefault("properties", {})["Node name for S&R"] = n["type"]
            props=n.setdefault("properties",{})
            props["overtliDirectorManaged"]=True
            props["overtliAddtl"]=bool(addtl)
            if n["type"] in {"OvertliH3AutoLoadLatent", "OvertliH3SaveLatent", "OvertliH3FinalArtifactName"}:
                inputs = n.setdefault("inputs", [])
                values = n.setdefault("widgets_values", [])
                slot = next((x for x in inputs if x["name"] == "namespace"), None)
                if slot is None:
                    inputs.append({"name": "namespace", "type": "COMBO", "widget": {"name": "namespace"}, "link": None})
                    values.append("Addtl" if addtl else "Default")
                else:
                    index = [x for x in inputs if x.get("widget")].index(slot)
                    if index < len(values):
                        values[index] = "Addtl" if addtl else "Default"
            if n["type"]=="OvertliH3OptionalLoRAStack":
                values=n.setdefault("widgets_values",[])
                while len(values)<10:values.extend(["None",0.5])
                for i in (4,5):
                    if not any(x["name"]==f"profile_{i}" for x in n.get("inputs",[])):
                        n.setdefault("inputs",[]).extend([{"name":f"profile_{i}","type":"COMBO","widget":{"name":f"profile_{i}"},"link":None},{"name":f"strength_{i}","type":"FLOAT","widget":{"name":f"strength_{i}"},"link":None}])
            profile=props.get("overtliH3ProductionProfile")
            if profile:
                for field,default in (("loras","None"),("strengths",0.5)):
                    while len(profile.get(field,[]))<5:profile.setdefault(field,[]).append(default)
                if addtl:profile.update(showAdditionalLoras=True,showNsfwLoras=True,blurNsfwThumbnails=False)
            if n["type"]=="PixaromaSaveVideo":
                state=json.loads(props.get("saveVideoState") or "{}")
                state["saveOnRun"]=True
                if addtl:
                    folder=str(state.get("folder") or "")
                    if folder and not re.search(r"(?:^|[\\/])addtl(?:[\\/]|$)",folder,re.I):state["folder"]=str(Path(folder)/"addtl")
                    if not folder and not state.get("pattern","").startswith("OvertliDS/addtl/"):state["pattern"]="OvertliDS/addtl/"+str(state.get("pattern") or "Video_%counter%")
                props["saveVideoState"]=json.dumps(state)
            h3state=props.get("overtliH3ReferenceState")
            if isinstance(h3state,dict):h3state["saveVideo"]=True
            image_state=props.get("overtliImageDirectorState")
            if isinstance(image_state,dict):
                image_state.setdefault("constantPrompt","")
                image_state.setdefault("constantEnabled",True)
                image_state.setdefault("aspectPolicy","Canvas preset")
                image_state.setdefault("generationRaster","Custom")
                image_state["overtliAddtl"]=bool(addtl)
                if addtl:image_state.update(loraShowAdditional=True,loraShowNSFW=True,loraBlurNSFW=False)
            if n.get("title")=="Main Prompt Textbox":
                insert_studio(graph,n,"FLUX.2 Klein 9B",addtl)
            elif n.get("title")=="Prompt - Manual FL2VA" or n["type"]=="OvertliH3AudioSyncPrompt":
                insert_studio(graph,n,"H3 Base",addtl)
            elif n.get("title")=="REFERENCE PROMPT - SIX-SECTION REF2VA":
                insert_studio(graph,n,"H3 Ref2VA",addtl)
            elif "base" in n.get("title","").lower() and "prompt" in n.get("title","").lower() and n["type"] in {"PixaromaText","PrimitiveStringMultiline"}:
                insert_studio(graph,n,"H3 Base",addtl)
            if addtl and input_root:
                # Only media selector widget positions, never authored prompt text.
                media_slots=[x for x in n.get("inputs",[]) if x.get("widget") and x["name"] in {"image","video","audio","file"}]
                widget_inputs=[x for x in n.get("inputs",[]) if x.get("widget")]
                for slot in media_slots:
                    index=widget_inputs.index(slot)
                    values=n.get("widgets_values") or []
                    if index<len(values):values[index]=_stage_reference(values[index],input_root,receipts)
                for key in ("audioLoadState","loadAudioState"):
                    if key in props:
                        raw=props[key];state=json.loads(raw) if isinstance(raw,str) else dict(raw)
                        for field in ("file","filename","audio","path"):
                            if field in state:state[field]=_stage_reference(state[field],input_root,receipts)
                        props[key]=json.dumps(state) if isinstance(raw,str) else state
    return receipts
