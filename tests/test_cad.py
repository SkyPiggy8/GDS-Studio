import pytest
from gds_studio.cad import top_left, move_top_left, is_editable, dimension_points, drive_dimension
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


def ref(s,index,kind='point',poly=0):
    return dict(shape=s.id,entry=0,poly=poly,index=index,count=len(s.world_polygons()[poly]),kind=kind)


def test_edge_cd_drive_preserves_rectangle_and_first_edge():
    s=Shape(polygons=[[[0,0],[100,0],[100,80],[0,80]]],angle=90,x=-50)
    d=Document(shapes=[s]);refs=[ref(s,3,'edge'),ref(s,1,'edge')]
    fixed=dimension_points(d,refs)[0]
    drive_dimension(d,refs,30)
    assert dimension_points(d,refs)[3]==pytest.approx(30)
    assert dimension_points(d,refs)[0]==pytest.approx(fixed)
    assert not s.pattern and s.angle==0
    assert all(abs(a[0]-b[0])<1e-6 or abs(a[1]-b[1])<1e-6 for a,b in zip(s.polygons[0],s.polygons[0][1:]+s.polygons[0][:1]))


def test_point_dimension_orthogonal_propagation_and_whole_object():
    s=Shape(polygons=[[[0,0],[100,0],[100,80],[0,80]]]);d=Document(shapes=[s])
    refs=[ref(s,0),ref(s,1)]
    drive_dimension(d,refs,250,'horizontal')
    assert s.polygons[0]==[[0,0],[250,0],[250,80],[0,80]]
    t=Shape(polygons=[[[0,0],[30,0],[30,80],[0,80]]],x=500);d.shapes.append(t)
    refs=[ref(s,1,'edge'),ref(t,3,'edge')]
    drive_dimension(d,refs,50,whole=True)
    assert t.x==300 and dimension_points(d,refs)[3]==50
    assert t.polygons[0][1]==[30,0]


def test_dimension_rejects_nonparallel_locked_and_stale_references():
    s=Shape(polygons=[[[0,0],[100,0],[100,80],[0,80]]]);d=Document(shapes=[s])
    with pytest.raises(ValueError,match='平行'):dimension_points(d,[ref(s,0,'edge'),ref(s,1,'edge')])
    refs=[ref(s,3,'edge'),ref(s,1,'edge')];d.layers[0].locked=True
    before=d.to_dict()
    with pytest.raises(ValueError,match='锁定'):drive_dimension(d,refs,60)
    assert d.to_dict()==before
    s.polygons[0].append([0,40])
    with pytest.raises(ValueError,match='改变'):dimension_points(d,refs)
