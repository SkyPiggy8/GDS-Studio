"""Atomic project writes and verified GDS I/O. Display nm, GDS user unit nm."""
from __future__ import annotations
import json
import os
import tempfile
import shutil
from pathlib import Path
import gdstk
import numpy as np
from .model import Document, Shape, Layer
from .geometry import clean, PRECISION


def atomic_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".gds-studio-",suffix=".json",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def save_project(path,document): atomic_json(path,document.to_dict())


def load_project(path):
    with open(path,encoding="utf-8") as f: return Document.from_dict(json.load(f))


def read_gds_unicode(path):
    """GDSTK uses narrow CRT paths on Windows. Stage using Python's Unicode I/O."""
    fd,staged=tempfile.mkstemp(prefix="gds-studio-",suffix=".gds");os.close(fd)
    try:
        shutil.copyfile(path,staged)
        return gdstk.read_gds(staged,unit=1e-9)
    finally:
        if os.path.exists(staged):os.unlink(staged)


def export_gds(path,document,sidecar=True):
    if not document.shapes: raise ValueError("版图为空，请先放置或绘制图形")
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    lib=gdstk.Library(name="GDS_STUDIO",unit=1e-9,precision=1e-10)
    top=lib.new_cell("TOP")
    records=[]; expected_area=0; expected_specs=set()
    for i,s in enumerate(document.shapes):
        cell=lib.new_cell(f"P{i:05d}")
        count=0
        for layer,datatype,polys in s.entries():
            if not 0<=layer<=65535 or not 0<=datatype<=65535: raise ValueError("图层编号必须在 0–65535 之间")
            for points in polys:
                points=clean(points)
                if np.abs(np.asarray(points)).max()>214748360:
                    raise ValueError("坐标超出 0.1 nm 数据库精度的 GDS 范围")
                rounded=np.round(np.array(points)/PRECISION)*PRECISION
                polygon=gdstk.Polygon(clean(rounded.tolist()),layer=layer,datatype=datatype)
                cell.add(polygon); count+=1; expected_area+=polygon.area(); expected_specs.add((layer,datatype))
        if not count: raise ValueError(f"{s.name}没有可导出的面积，请检查参数")
        top.add(gdstk.Reference(cell))
        records.append({"cell":cell.name,"id":s.id,"name":s.name,"pattern":s.pattern,"params":s.params,"metadata":s.metadata})
    fd,tmp=tempfile.mkstemp(prefix=".gds-studio-",suffix=".gds",dir=path.parent);os.close(fd)
    fd,staged=tempfile.mkstemp(prefix="gds-studio-",suffix=".gds");os.close(fd)
    try:
        lib.write_gds(staged,max_points=199)
        reread=gdstk.read_gds(staged,unit=1e-9)
        polygons=reread["TOP"].get_polygons()
        actual_area=sum(p.area() for p in polygons)
        if not polygons or not np.isclose(actual_area,expected_area,rtol=1e-8,atol=.1):
            raise ValueError("GDS 回读面积不一致，导出未写入目标文件")
        if {(p.layer,p.datatype) for p in polygons}!=expected_specs:
            raise ValueError("GDS 回读图层不一致")
        shutil.copyfile(staged,tmp)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
        if os.path.exists(staged):os.unlink(staged)
    report={"units":"nm","precision_nm":.1,"polygon_count":len(polygons),"cell_count":len(lib.cells),"area_nm2":actual_area,"gds_readback_verified":True,"patterns":records,"document_metadata":document.metadata}
    if sidecar: atomic_json(path.with_suffix(".manifest.json"),report)
    return report


def inspect_cells(path):
    from .layout_source import read_layout
    lib=read_layout(path)
    return lib,[c.name for c in lib.top_cells()]


def import_gds(path,cell_name=None,lib=None,max_polygons=50000):
    from .layout_source import read_layout,contour
    import klayout.db as kdb
    lib=lib if isinstance(lib,kdb.Layout) else read_layout(path)
    tops=lib.top_cells()
    if cell_name is None:
        if len(tops)!=1: raise ValueError("文件有多个顶层 Cell，请选择要导入的 Cell")
        cell=tops[0]
    else: cell=lib.cell(cell_name)
    if cell is None:raise ValueError("Cell 不存在")
    doc=Document(name=Path(path).stem,shapes=[],layers=[],metadata={"source_gds":str(path),"source_cell":cell.name,"hierarchy":"flattened on import","labels":"not imported"})
    for li in lib.layer_indices():
        info=lib.get_info(li);it=cell.begin_shapes_rec(li)
        it.shape_flags=kdb.Shapes.SPolygons|kdb.Shapes.SBoxes|kdb.Shapes.SPaths
        while not it.at_end():
            if len(doc.shapes)>=max_polygons:raise ValueError(f"画布超过 {max_polygons:,} 个轮廓，请使用「样本库 → 大版图提取」按层或区域收集")
            p=it.shape().polygon.transformed(it.trans())
            doc.shapes.append(Shape(name=f"{cell.name} · {len(doc.shapes)+1}",polygons=[contour(p,lib.dbu*1000)],layer=info.layer,datatype=info.datatype,metadata={"source":"gds","source_cell":it.cell().name}))
            it.next()
    doc.ensure_layers()
    return doc
