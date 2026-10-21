import pytest
from shapely.geometry import Polygon
from gds_studio.opc import OPCOptions,correct,preview_opc
from gds_studio.model import Document,Shape
from gds_studio.geometry import rect,bounds


def test_line_end_serif_and_bias_are_valid_and_reproducible():
    p=[rect(0,0,200,30)];opts=OPCOptions()
    output,report=correct(p,opts)
    assert not report['errors'] and report['end_caps']==2 and report['serifs']==4
    assert bounds(output)==pytest.approx((-3,-2,203,32))
    assert all(Polygon(p).is_valid for p in output)
    assert p==[rect(0,0,200,30)]
    assert output==correct(p,opts)[0]


def test_bridge_gap_hole_and_obstacle_guard():
    _,r=correct([rect(0,0,200,30),rect(0,34,200,30)],OPCOptions())
    assert r['errors']
    _,r=correct([rect(0,0,200,30),rect(0,40,200,30)],OPCOptions(min_gap_nm=10))
    assert any('间距' in e for e in r['errors'])
    a=Shape(polygons=[rect(0,0,200,30)]);b=Shape(polygons=[rect(0,40,200,30)])
    d=Document(shapes=[a,b]);before=d.to_dict();result,reports=preview_opc(d,[a],OPCOptions())
    assert any('未选中' in e for r in reports for e in r['errors']);assert d.to_dict()==before
    assert result[0].metadata['opc']['method']=='uncalibrated_rule_based'


def test_non_manhattan_and_invalid_parameters():
    _,r=correct([[[0,0],[100,0],[50,100]]],OPCOptions())
    assert r['skipped_non_manhattan']==1 and r['serifs']==0
    for options in (OPCOptions(bias_nm=float('nan')),OPCOptions(min_gap_nm=-1)):
        with pytest.raises(ValueError):correct([rect(0,0,100,30)],options)
