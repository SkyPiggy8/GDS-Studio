"""Binary renders and reproducible exports, preserving units and provenance."""
import csv
import json
import math
import os
import tempfile
from pathlib import Path
import cv2
import numpy as np
from .matching import geometry,polygon_parts
from .model import Document,Shape
from .io import export_gds,atomic_json
from .library import Library


def render_mask(polygons,size=256,padding=16):
    g=geometry(polygons);x,y,r,t=g.bounds
    factor=(size-2*padding-1)/max(r-x,t-y)
    ox=(size-(r-x)*factor)/2;oy=(size-(t-y)*factor)/2
    def points(coords):
        return np.rint([[(px-x)*factor+ox,(t-py)*factor+oy] for px,py in coords]).astype(np.int32)
    mask=np.zeros((size,size),np.uint8)
    for p in polygon_parts(g):
        cv2.fillPoly(mask,[points(p.exterior.coords)],255)
        for h in p.interiors:cv2.fillPoly(mask,[points(h.coords)],0)
    return mask,{"coordinate_bounds_nm":[x,y,r,t],"coordinate_units_per_pixel":1/factor,"padding_px":padding}


def save_png(path,array):
    ok,buf=cv2.imencode(".png",array)
    if not ok:raise ValueError("无法编码图片")
    Path(path).write_bytes(buf.tobytes())


def export_library(db_path,directory,ids=None,progress=lambda *_:None,cancelled=lambda:False):
    target=Path(directory)
    if target.exists():raise ValueError("请选择一个尚不存在的导出目录，避免覆盖数据")
    target.parent.mkdir(parents=True,exist_ok=True);lib=Library(db_path)
    try:
        lib.db.execute("BEGIN")  # Consistent WAL snapshot while editor remains usable.
        selected=ids or [r[0] for r in lib.db.execute("SELECT id FROM samples ORDER BY layer,datatype,id")]
        if not selected:raise ValueError("样本库为空")
        # Shape families and shared source files are joined into leakage groups.
        parent={id:id for id in selected};families={};sources={}
        def root(n):
            while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
            return n
        def join(a,b):parent[root(b)]=root(a)
        for id in selected:
            row=lib.db.execute("SELECT same_shape FROM samples WHERE id=?",(id,)).fetchone()
            if row is None:raise ValueError(f"样本 {id} 不存在")
            key=row[0]
            if key in families:join(id,families[key])
            else:families[key]=id
            for src, in lib.db.execute("SELECT source_id FROM occurrences WHERE sample_id=?",(id,)):
                if src in sources:join(id,sources[src])
                else:sources[src]=id
        minimum={}
        for id in selected:minimum[root(id)]=min(id,minimum.get(root(id),id))
        groups={id:f"group-{minimum[root(id)]:06d}" for id in selected}
        manifest=[];atlas_groups={}
        with tempfile.TemporaryDirectory(prefix=".gds-export-",dir=target.parent) as temp:
            stage=Path(temp)/"result";stage.mkdir();(stage/"masks").mkdir();(stage/"gds").mkdir();(stage/"atlas").mkdir()
            for number,id in enumerate(selected):
                if cancelled():raise InterruptedError("已取消，没有生成不完整数据集")
                sample=lib.get(id);name=f"sample-{id:06d}";mask,render=render_mask(sample["polygons"])
                save_png(stage/"masks"/f"{name}.png",mask)
                doc=Document(name=name,shapes=[Shape(name=sample["name"],polygons=sample["polygons"],layer=sample["layer"],datatype=sample["datatype"],metadata={"calibrated":bool(sample["calibrated"]),"library_id":id})])
                export_gds(stage/"gds"/f"{name}.gds",doc)
                record={k:sample[k] for k in ("id","name","layer","datatype","calibrated","width","height","area","components","holes","strict","congruent","same_shape","tags","review","origins")}
                record.update(mask=f"masks/{name}.png",gds=f"gds/{name}.gds",render=render,
                              nm_per_pixel=render["coordinate_units_per_pixel"] if sample["calibrated"] else None,
                              units="nm" if sample["calibrated"] else "nominal_unscaled",leakage_group=groups[id],split="unassigned")
                manifest.append(record);atlas_groups.setdefault((sample["layer"],sample["datatype"]),[]).append(id)
                if number%25==0:progress(f"正在渲染与导出 {number+1}/{len(selected)}")
            for (layer,datatype),layer_ids in atlas_groups.items():
                for page,start in enumerate(range(0,len(layer_ids),64),1):
                    if cancelled():raise InterruptedError("已取消，没有生成不完整数据集")
                    tile_ids=layer_ids[start:start+64];rows=math.ceil(len(tile_ids)/8)
                    atlas=np.full((rows*180,8*160),245,np.uint8);shapes=[]
                    samples=[lib.get(id) for id in tile_ids]
                    step=max(max(s["width"],s["height"]) for s in samples)*1.2+1
                    placements=[]
                    for n,s in enumerate(samples):
                        row,col=divmod(n,8);mask,_=render_mask(s["polygons"],size=144,padding=8)
                        atlas[row*180:row*180+144,col*160:col*160+144]=255-mask
                        cv2.putText(atlas,f"#{s['id']}  {layer}/{datatype}",(col*160+4,row*180+161),cv2.FONT_HERSHEY_SIMPLEX,.38,50,1,cv2.LINE_AA)
                        x,y,_,_=geometry(s["polygons"]).bounds
                        shapes.append(Shape(name=s["name"],polygons=s["polygons"],x=col*step-x,y=-row*step-y,layer=layer,datatype=datatype,metadata={"library_id":s["id"],"calibrated":bool(s["calibrated"])}))
                        placements.append({"id":s["id"],"offset_nm":[col*step-x,-row*step-y],"calibrated":bool(s["calibrated"])})
                    name=f"layer-{layer}-{datatype}-page-{page:03d}"
                    save_png(stage/"atlas"/f"{name}.png",atlas)
                    export_gds(stage/"atlas"/f"{name}.gds",Document(name=name,shapes=shapes))
                    atomic_json(stage/"atlas"/f"{name}.placement.json",placements)
            atomic_json(stage/"manifest.json",{"format":"gds-studio-dataset","version":1,"foreground":255,"background":0,
              "matching":"translation / D4 / uniform scale; fingerprints quantized to 0.1 nm or 1e-5 relative",
              "split_policy":"unassigned; keep each leakage_group in one split; groups join same-shape families and shared sources",
              "samples":manifest})
            with (stage/"index.csv").open("w",encoding="utf-8-sig",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=["id","name","layer","datatype","calibrated","review","tags","leakage_group","split","mask","gds"]);writer.writeheader()
                for s in manifest:writer.writerow({k:s[k] for k in writer.fieldnames})
            if cancelled():raise InterruptedError("已取消，没有生成不完整数据集")
            os.replace(stage,target)
        return {"samples":len(selected),"layers":len(atlas_groups),"directory":str(target),"leakage_groups":len(set(groups.values()))}
    finally:lib.close()
