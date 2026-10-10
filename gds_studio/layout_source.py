"""Bounded extraction from KLayout's hierarchical C++ database, in a worker.

Cell definitions are the default. Recursive traversal is only opt-in. Limit
overflow aborts the entire transaction, especially for connected components.
"""
from pathlib import Path
import math
import klayout.db as kdb
from .library import Library,file_hash


def read_layout(path):
    layout=kdb.Layout();layout.read(str(Path(path).resolve()));return layout


def index_layout(path):
    layout=read_layout(path);layers=layout.layer_indices();tops={c.cell_index() for c in layout.top_cells()}
    cells=[]
    for c in layout.each_cell():
        box=c.dbbox()
        cells.append({"name":c.name,"top":c.cell_index() in tops,"bounds_nm":[box.left*1000,box.bottom*1000,box.right*1000,box.top*1000],
                      "layers":{str(i):c.shapes(i).size() for i in layers if not c.shapes(i).is_empty()}})
    return {"path":str(path),"bytes":Path(path).stat().st_size,"dbu_nm":layout.dbu*1000,"cells":cells,
            "layers":[{"index":i,"layer":layout.get_info(i).layer,"datatype":layout.get_info(i).datatype,"name":layout.get_info(i).name} for i in layers]}


def contour(p,factor):
    # GDS-compatible connected contour, retaining holes via cut lines.
    p=p.to_simple_polygon()
    return [[v.x*factor,v.y*factor] for v in p.each_point()]


def extract_layout(path,db_path,options,progress=lambda *_:None,cancelled=lambda:False):
    mode=options.get("mode","polygon")
    if mode not in ("polygon","connected","region","cell"):raise ValueError("未知提取方式")
    limit=int(options.get("limit",20000));sample_limit=int(options.get("sample_limit",10000))
    if not 1<=limit<=1000000:raise ValueError("提取上限无效")
    layout=read_layout(path);factor=layout.dbu*1000
    selected=options.get("cells") or [c.name for c in layout.top_cells()]
    layers=options.get("layers",layout.layer_indices());recursive=bool(options.get("recursive",False))
    roi=options.get("roi")
    if roi:
        if len(roi)!=4 or not all(math.isfinite(v) for v in roi) or roi[2]<=roi[0] or roi[3]<=roi[1]:raise ValueError("区域需要有效的左下 / 右上坐标")
        region_box=kdb.Box(math.floor(roi[0]/factor),math.floor(roi[1]/factor),math.ceil(roi[2]/factor),math.ceil(roi[3]/factor))
    else:region_box=None
    if mode=="region" and roi is None:raise ValueError("区域提取需要填写区域坐标")
    report={"added":0,"duplicates":0,"geometry_seen":0,"text_seen":0,"samples":0,"cells":len(selected),"mode":mode,"complete":True}
    lib=Library(db_path)
    try:
        with lib.transaction():
            sid=lib.source(file_hash(path),path,"gds",{"dbu_nm":factor,"file_bytes":Path(path).stat().st_size})
            for cell_no,name in enumerate(selected):
                cell=layout.cell(name)
                if cell is None:raise ValueError(f"Cell 不存在：{name}")
                for li in layers:
                    if cancelled():raise InterruptedError("已取消，未写入本批样本")
                    info=layout.get_info(li);polygons=[];origins=[];labels=[]
                    # Region iterators omit zero-area text boxes. Preserve bounded
                    # annotations from unique definitions, not array-expanded text.
                    annotation_cells=[cell]+([layout.cell(i) for i in cell.called_cells()] if recursive else [])
                    for ac in annotation_cells:
                        for ts in ac.shapes(li).each(kdb.Shapes.STexts):
                            text=ts.text;point=text.trans.disp
                            labels.append({"text":text.string,"x_nm":point.x*factor,"y_nm":point.y*factor,"cell":ac.name,"coordinate_frame":"cell_definition"})
                            report["text_seen"]+=1
                            if len(labels)>=200:break
                        if len(labels)>=200:break
                    if recursive:
                        iterator=cell.begin_shapes_rec_overlapping(li,region_box.enlarged(1)) if region_box is not None else cell.begin_shapes_rec(li)
                        iterator.shape_flags=kdb.Shapes.SPolygons|kdb.Shapes.SBoxes|kdb.Shapes.SPaths
                        def entries():
                            while not iterator.at_end():
                                yield iterator.shape(),iterator.trans(),iterator.cell().name
                                iterator.next()
                    else:
                        def entries():
                            for shape in cell.shapes(li).each():yield shape,kdb.ICplxTrans(),cell.name
                    for shape,trans,origin in entries():
                        if cancelled():raise InterruptedError("已取消，未写入本批样本")
                        if shape.is_text():
                            continue
                        p=shape.polygon
                        if p is None:continue
                        p=p.transformed(trans)
                        if region_box is not None:
                            clipped=kdb.Region(p)&kdb.Region(region_box)
                            pieces=list(clipped.each())
                        else:pieces=[p]
                        if not pieces:continue
                        report["geometry_seen"]+=1
                        if report["geometry_seen"]>limit:
                            raise ValueError(f"几何数量超过 {limit:,} 上限。本批未入库，请缩小区域、减少 Cell / 图层，或提高上限。")
                        for piece in pieces:
                            polygons.append(piece);origins.append(origin)
                    if not polygons:continue
                    # Never combine a truncated geometry set into a false connected sample.
                    if mode=="connected":
                        region=kdb.Region()
                        for p in polygons:region.insert(p)
                        region.merge();groups=[[p] for p in region.each_merged()]
                    elif mode in ("cell","region"):groups=[polygons]
                    else:groups=[[p] for p in polygons]
                    for n,group in enumerate(groups):
                        if cancelled():raise InterruptedError("已取消，未写入本批样本")
                        if len(group)>20000 or sum(p.num_points() for p in group)>200000:
                            raise ValueError("单个样本过于复杂，请使用更小区域或单多边形模式")
                        pts=[contour(p,factor) for p in group if p.area()>0]
                        if not pts:continue
                        report["samples"]+=1
                        if report["samples"]>sample_limit:raise ValueError(f"样本超过 {sample_limit:,} 上限，本批未入库。请减少提取范围。")
                        metadata={"cell":name,"source_cells":sorted(set(origins)),"layer":info.layer,"datatype":info.datatype,
                                  "mode":mode,"recursive":recursive,"roi_nm":roi,"index":n,"labels":labels,"labels_capped":len(labels)==200,"labels_scope":"unique_cell_definitions; not ROI-clipped or array-expanded"}
                        boxes=[p.bbox() for p in group]
                        metadata["bounds_nm"]=[min(b.left for b in boxes)*factor,min(b.bottom for b in boxes)*factor,max(b.right for b in boxes)*factor,max(b.top for b in boxes)*factor]
                        if mode=="polygon":metadata["source_cells"]=[origins[n]]
                        else:metadata["source_cells_scope"]="definitions encountered in selected Cell/layer"
                        _,added=lib.add(pts,f"{name} · {mode} {n+1}",info.layer,info.datatype,True,sid,metadata)
                        report["added"]+=int(added);report["duplicates"]+=int(not added)
                        if report["samples"]%50==0:progress(f"{name} · {info.layer}/{info.datatype} · 已处理 {report['samples']:,} 个样本")
                progress(f"已完成 Cell {cell_no+1}/{len(selected)} · {name}")
        return report
    finally:lib.close()
