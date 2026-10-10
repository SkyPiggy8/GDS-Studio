"""Core editor workflows exercised through real dialogs' parameter interfaces."""
from test_ui import app,window
from gds_studio.dialogs import ArrayDialog,SweepDialog
from gds_studio.model import Document,Shape
from gds_studio.geometry import rect,bounds
from PySide6.QtWidgets import QInputDialog
from PySide6.QtCore import Qt


def test_array_and_undo(window,monkeypatch):
    w=window;w.replace_document(Document(shapes=[Shape.from_pattern("hammerhead")]))
    w.canvas.select_ids([w.document.shapes[0].id])
    def exec_(dialog):dialog.rows.setValue(2);dialog.cols.setValue(3);dialog.dx.setValue(250);dialog.dy.setValue(100);return 1
    monkeypatch.setattr(ArrayDialog,"exec",exec_);w.array()
    assert len(w.document.shapes)==6
    assert {(s.x,s.y) for s in w.document.shapes}=={(x,y) for x in [0,250,500] for y in [0,100]}
    w.undo.undo();assert len(w.document.shapes)==1


def test_sweep_all_combinations_and_metadata(window,monkeypatch):
    w=window;w.replace_document(Document(shapes=[Shape.from_pattern("line_space")]))
    w.canvas.select_ids([w.document.shapes[0].id])
    def exec_(dialog):dialog.values1.setText("8,12");dialog.values2.setText("10,20,30");return 1
    monkeypatch.setattr(SweepDialog,"exec",exec_);w.sweep()
    assert len(w.document.shapes)==7
    shapes=w.document.shapes[1:]
    assert {(s.params["width"],s.params["gap"]) for s in shapes}=={(a,b) for a in [8,12] for b in [10,20,30]}
    assert all("sweep" in s.metadata for s in shapes)
    w.undo.undo();assert len(w.document.shapes)==1


def test_bool_bias_and_hole_bake(window,monkeypatch):
    w=window;w.replace_document(Document(shapes=[Shape(polygons=[rect(0,0,20,20)]),Shape(polygons=[rect(10,0,20,20)])]))
    w.canvas.select_ids([s.id for s in w.document.shapes]);w.boolean_op("or")
    assert len(w.document.shapes)==1;assert bounds(w.document.shapes[0].world_polygons())==(0,0,30,20)
    monkeypatch.setattr(QInputDialog,"getDouble",lambda *args:(2.,True));w.bias()
    assert bounds(w.document.shapes[0].world_polygons())==(-2,-2,32,22)
    w.replace_document(Document(shapes=[Shape.from_pattern("ring")]))
    w.canvas.select_ids([w.document.shapes[0].id]);w.bake()
    from shapely.geometry import Polygon
    assert all(Polygon(s.polygons[0]).is_valid for s in w.document.shapes)
    union=Polygon(w.document.shapes[0].polygons[0])
    for s in w.document.shapes[1:]:union=union.union(Polygon(s.polygons[0]))
    assert len(union.interiors)==1


def test_library_filter_and_pending_parameters(window):
    w=window;w.search.setText("hammerhead")
    assert sum(not w.catalog.item(i).isHidden() for i in range(w.catalog.count()))==1
    w.search.clear();w.category.setCurrentText("缺陷对照")
    assert sum(not w.catalog.item(i).isHidden() for i in range(w.catalog.count()))==4
