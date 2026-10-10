import json
from pathlib import Path
import pytest
import klayout.db as k
from gds_studio.geometry import rect,transform,boolean
from gds_studio.matching import fingerprints,similarity,geometry
from gds_studio.library import Library
from gds_studio.layout_source import index_layout,extract_layout
from gds_studio.dataset import export_library,render_mask


def test_matching_preserves_dimensions_holes_topology_and_fragmentation():
    t=[rect(0,0,30,10),rect(10,10,10,30)];fp=fingerprints(t)
    translated=transform(t,600,-200)
    assert fingerprints(translated)["strict"]==fp["strict"]
    assert fingerprints(boolean(t))["strict"]==fp["strict"]
    rotated=transform(t,angle=90,mirror=True)
    assert fingerprints(rotated)["strict"]!=fp["strict"]
    assert fingerprints(rotated)["congruent"]==fp["congruent"]
    larger=transform(rotated,sx=3,sy=3)
    assert fingerprints(larger)["congruent"]!=fp["congruent"]
    assert fingerprints(larger)["same_shape"]==fp["same_shape"]
    assert similarity(t,larger)==pytest.approx(1)
    stretched=transform(t,sx=2,sy=1)
    assert fingerprints(stretched)["same_shape"]!=fp["same_shape"]
    hole=boolean([rect(0,0,40,40)],[rect(10,10,20,20)],"not")
    assert fingerprints(hole)["holes"]==1
    assert fingerprints(hole)["strict"]!=fingerprints([rect(0,0,40,40)])["strict"]
    mask,report=render_mask(hole);assert mask[128,128]==0 and mask[30,30]==255


def test_database_dedup_keeps_sources_and_uncalibrated_policy(tmp_path):
    lib=Library(tmp_path/"lib.sqlite");t=[rect(0,0,20,40)]
    with lib.transaction():
        a=lib.source("a","A.gds","gds");b=lib.source("b","B.gds","gds")
        id,added=lib.add(t,"rect",1,0,True,a,{"cell":"A"});assert added
        same,added=lib.add(transform(t,80,30),"rect duplicate",1,0,True,b,{"cell":"B"});assert not added and same==id
        unscaled,_=lib.add(t,"unscaled",1,0,False,b,{"image":"paper"})
        bigger,_=lib.add(transform(t,sx=2,sy=2),"bigger",2,0,True,a,{})
    assert len(lib.get(id)["origins"])==2
    matches=lib.matches(t,calibrated=False,exclude=unscaled)
    assert matches and all(r["relation"].startswith("同形") for r in matches)
    assert any(r["id"]==bigger for r in lib.matches(t))
    lib.close()


@pytest.fixture
def hierarchical(tmp_path):
    layout=k.Layout();layout.dbu=.001;li=layout.layer(1,0);aux=layout.layer(2,4)
    child=layout.create_cell("CHILD");child.shapes(li).insert(k.Box(0,0,20,20));child.shapes(li).insert(k.Box(20,0,40,20));child.shapes(li).insert(k.Box(100,0,120,20));child.shapes(li).insert(k.Text("annotation",k.Trans(0,0)))
    child.shapes(aux).insert(k.Path([k.Point(0,0),k.Point(40,40)],10))
    top=layout.create_cell("TOP");top.insert(k.CellInstArray(child.cell_index(),k.Trans(100,200),k.Vector(400,0),k.Vector(0,400),1000,1000))
    p=tmp_path/"含中文.gds";layout.write(str(p));return p


def test_extraction_definitions_recursive_roi_connected_and_limits(hierarchical,tmp_path):
    index=index_layout(hierarchical);assert len(index["cells"])==2 and len(index["layers"])==2
    path=tmp_path/"lib.sqlite"
    result=extract_layout(hierarchical,path,{"cells":["CHILD"],"layers":[0],"mode":"connected"})
    assert result["samples"]==2 and result["text_seen"]==1
    lib=Library(path);assert sorted(s["width"] for s in lib.list())==[20,40]
    before=lib.count()
    with pytest.raises(ValueError,match="上限"):
        extract_layout(hierarchical,path,{"cells":["CHILD"],"mode":"polygon","limit":1})
    assert lib.count()==before
    r=extract_layout(hierarchical,path,{"cells":["TOP"],"layers":[0],"mode":"region","recursive":True,"roi":[100,200,140,220]})
    assert r["samples"]==1 and r["geometry_seen"]==2 and r["text_seen"]==1
    sample=next(lib.get(s["id"]) for s in lib.list() if lib.get(s["id"])["area"]==800)
    assert any(o["metadata"]["roi_nm"]==[100,200,140,220] for o in sample["origins"])
    assert sample["area"]==800
    lib.close()


def test_cell_mode_keeps_line_space_and_path_conversion(hierarchical,tmp_path):
    path=tmp_path/"lib.sqlite"
    r=extract_layout(hierarchical,path,{"cells":["CHILD"],"mode":"cell"})
    assert r["samples"]==2
    lib=Library(path);assert {s["datatype"] for s in lib.list()}=={0,4}
    assert lib.get(lib.list()[0]["id"])["components"]==2
    lib.close()


def test_export_provenance_atlas_units_and_leakage_groups(tmp_path):
    db=tmp_path/"lib.sqlite";lib=Library(db)
    with lib.transaction():
        a=lib.source("a","a.gds","gds");b=lib.source("b","b.gds","gds")
        lib.add([rect(0,0,20,40)],"R",1,0,True,a,{"cell":"A"})
        lib.add([rect(0,0,40,80)],"scaled R",1,0,True,b,{"cell":"B"})
        lib.add([rect(0,0,30,30)],"square",2,0,False,b,{"page":2})
    lib.close();out=tmp_path/"dataset";r=export_library(db,out);assert r["samples"]==3
    manifest=json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    assert len({s["leakage_group"] for s in manifest["samples"]})==1
    assert manifest["samples"][-1]["nm_per_pixel"] is None
    assert len(list((out/"atlas").glob("*.png")))==2
    for s in manifest["samples"]:
        layout=k.Layout();layout.read(str(out/s["gds"]));region=k.Region(layout.top_cell().begin_shapes_rec(layout.layer(s["layer"],s["datatype"])))
        assert region.area()*(layout.dbu*1000)**2==pytest.approx(s["area"],rel=.01)
    with pytest.raises(ValueError):export_library(db,out)
    with pytest.raises(InterruptedError):export_library(db,tmp_path/"cancelled",cancelled=lambda:True)
    assert not (tmp_path/"cancelled").exists()


def test_extraction_cancel_rolls_back(hierarchical,tmp_path):
    path=tmp_path/"lib.sqlite"
    with pytest.raises(InterruptedError):extract_layout(hierarchical,path,{},cancelled=lambda:True)
    lib=Library(path);assert lib.count()==0;lib.close()
