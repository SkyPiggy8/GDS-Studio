import pytest
from gds_studio.cad import top_left, move_top_left, is_editable
from gds_studio.model import Shape, Document


def test_top_left_transformed_multilayer_rigid_move():
    a=Shape.from_pattern("via_enclosure",x=-28,y=42,angle=90,sx=2,mirror=True)
    b=Shape(polygons=[[[0,0],[20,0],[20,30],[0,30]]],x=100,y=-20)
    before=[[p for _,_,polys in s.entries() for p in polys] for s in (a,b)]
    ax,ay=top_left([a,b]);move_top_left([a,b],-500,123.4)
    assert top_left([a,b])==pytest.approx((-500,123.4))
    for s,polys in zip((a,b),before):
        after=[p for _,_,ps in s.entries() for p in ps]
        for p,q in zip(polys,after):
            for (x,y),(u,v) in zip(p,q):
                assert (u-x,v-y)==pytest.approx((-500-ax,123.4-ay))


def test_auxiliary_layer_lock():
    d=Document();s=Shape.from_pattern("via_enclosure")
    d.layers[1].locked=True
    assert not is_editable(d,s)
