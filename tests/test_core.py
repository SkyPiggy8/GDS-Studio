import copy
import math
import numpy as np
import pytest
import gdstk
import klayout.db as kdb
from gds_studio.catalog import REGISTRY
from gds_studio.geometry import boolean,offset,regularize,rect,bounds,validate
from gds_studio.model import Document,Shape,demo
from gds_studio.io import export_gds,import_gds,save_project,load_project,read_gds_unicode
from gds_studio.tracing import TraceOptions,trace_image,calibrated_scale


@pytest.mark.parametrize("key",list(REGISTRY))
def test_patterns_gds_klayout_roundtrip(key,tmp_path):
    s=Shape.from_pattern(key,x=37,y=-21,angle=90)
    d=Document(shapes=[s]);d.ensure_layers();path=tmp_path/f"{key}.gds"
    report=export_gds(path,d)
    assert report["gds_readback_verified"]
    layout=kdb.Layout();layout.read(str(path));assert layout.dbu==pytest.approx(.0001)
    actual={}
    for layer_index in layout.layer_indices():
        info=layout.get_info(layer_index)
        region=kdb.Region(layout.top_cell().begin_shapes_rec(layer_index))
        actual[(info.layer,info.datatype)]=region.area()*.1**2
    expected={}
    for layer,datatype,polys in s.entries():expected[(layer,datatype)]=sum(p.area() for p in gdstk.boolean([gdstk.Polygon(p) for p in polys],[],"or",precision=.1))
    assert actual.keys()==expected.keys()
    for spec in expected:assert actual[spec]==pytest.approx(expected[spec],rel=.002,abs=.1)
    imported=import_gds(path);assert imported.shapes
    p1=[p for _,_,ps in s.entries() for p in ps];p2=[p for shape in imported.shapes for p in shape.world_polygons()]
    assert bounds(p1)==pytest.approx(bounds(p2),abs=.1)


def test_project_preserves_editable_params_and_layers(tmp_path):
    d=demo();d.shapes[0].params["width"]=8;d.shapes[0].metadata={"calibrated":True,"nm_per_pixel":.25}
    d.layers[0].visible=False;d.layers[1].locked=True;d.grid=.5;path=tmp_path/"工程.gsproj"
    save_project(path,d);loaded=load_project(path)
    assert loaded.to_dict()==d.to_dict()


def test_hole_trace_and_units(tmp_path):
    image=np.full((120,120,3),255,np.uint8);image[10:110,10:110]=0;image[40:80,40:80]=255
    options=TraceOptions(nm_per_pixel=.5,calibrated=True,tolerance=0)
    polys,mask,report=trace_image(image,options)
    assert polys and report["rejected"]==0
    d=Document(shapes=[Shape(polygons=polys)]);path=tmp_path/"ring.gds";export_gds(path,d)
    layout=kdb.Layout();layout.read(str(path));region=kdb.Region(layout.top_cell().begin_shapes_rec(layout.layer(1,0)))
    # At image center the known hole must remain empty after independent GDS read.
    point=kdb.Region(kdb.Box(290,290,310,310));assert (region & point).is_empty()
    assert not (region & kdb.Region(kdb.Box(70,70,80,80))).is_empty()


def test_trace_crop_polarity_scale_and_nested_island():
    image=np.full((150,180,3),255,np.uint8)
    image[30:120,40:140]=0;image[50:100,60:120]=255;image[65:85,80:100]=0
    polys,_,report=trace_image(image,TraceOptions(nm_per_pixel=2,roi=(20,20,140,120),tolerance=0))
    assert len(polys)==2;assert report["roi_origin_px"]==[20,20]
    assert bounds(polys)==pytest.approx((40,40,238,218),abs=.1)
    inverted=255-image
    dark,_,_=trace_image(image,TraceOptions(tolerance=0));light,_,_=trace_image(inverted,TraceOptions(dark=False,tolerance=0))
    assert sum(gdstk.Polygon(p).area() for p in dark)==pytest.approx(sum(gdstk.Polygon(p).area() for p in light))
    assert calibrated_scale([0,0],[3,4],100)==20
    with pytest.raises(ValueError):calibrated_scale([0,0],[0,0],100)


@pytest.mark.parametrize("mode",["orthogonal","octilinear"])
def test_handdrawn_closed_valid_constrained(mode):
    p=regularize([[0,0],[50,2],[52,50],[1,48]],mode,1,3)
    validate(p)
    for a,b in zip(p,p[1:]+p[:1]):
        dx,dy=abs(b[0]-a[0]),abs(b[1]-a[1])
        assert dx<1e-6 or dy<1e-6 or (mode=="octilinear" and abs(dx-dy)<1e-6)


def test_boolean_and_offset():
    a=[rect(0,0,10,10)];b=[rect(5,0,10,10)]
    area=lambda polys:sum(gdstk.Polygon(p).area() for p in polys)
    assert area(boolean(a,b,"or"))==150
    assert area(boolean(a,b,"and"))==50
    assert area(boolean(a,b,"not"))==50
    assert area(boolean(a,b,"xor"))==100
    assert area(offset(a,1))==144
    assert not offset(a,-10)


def test_gds_unit_conversion_and_multiple_top_cells(tmp_path):
    lib=gdstk.Library(unit=1e-6,precision=1e-9);cell=lib.new_cell("A");cell.add(gdstk.rectangle((0,0),(1,2),layer=7,datatype=3))
    lib.new_cell("B").add(gdstk.rectangle((0,0),(3,4)));path=tmp_path/"microns.gds";lib.write_gds(path)
    with pytest.raises(ValueError):import_gds(path)
    d=import_gds(path,"A");assert bounds(d.shapes[0].world_polygons())==pytest.approx((0,0,1000,2000))
    assert d.shapes[0].layer==7 and d.shapes[0].datatype==3


def test_reject_invalid_geometry_and_params(tmp_path):
    with pytest.raises(ValueError):validate([[0,0],[10,10],[0,10],[10,0]])
    with pytest.raises(ValueError):export_gds(tmp_path/"empty.gds",Document())
    with pytest.raises(ValueError):REGISTRY["contact_array"].generate({"count":2.5})
    data=demo().to_dict();data["grid"]=float("nan")
    with pytest.raises(ValueError):Document.from_dict(data)


def test_export_all_visible_and_hidden_layers(tmp_path):
    d=Document(shapes=[Shape.from_pattern("via_enclosure")]);d.ensure_layers();d.layers[0].visible=False
    path=tmp_path/"multilayer.gds";export_gds(path,d);lib=read_gds_unicode(path)
    assert {p.layer for p in lib["TOP"].get_polygons()}=={1,2}


def test_unicode_paths_are_supported(tmp_path):
    folder=tmp_path/"版图样本";folder.mkdir();path=folder/"锤头测试.gds"
    d=Document(shapes=[Shape.from_pattern("hammerhead")]);export_gds(path,d)
    loaded=import_gds(path);assert len(loaded.shapes)==1
    assert bounds(loaded.shapes[0].world_polygons())==pytest.approx(bounds(d.shapes[0].world_polygons()))
