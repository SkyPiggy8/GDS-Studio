import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import math
import time
from pathlib import Path
import pytest
from PySide6.QtCore import Qt,QPointF,QPoint,QEvent
from PySide6.QtGui import QFont,QFontDatabase,QMouseEvent
from PySide6.QtWidgets import QApplication,QDoubleSpinBox
from PySide6.QtTest import QTest
from gds_studio.window import MainWindow
from gds_studio.model import Document,Shape
from gds_studio.canvas import LayoutCanvas
from gds_studio.style import STYLE
from gds_studio.image_dialog import TraceDialog
from gds_studio.geometry import bounds


@pytest.fixture(scope="session")
def app():
    a=QApplication.instance() or QApplication([])
    for path in [r"C:\Windows\Fonts\msyh.ttc",r"C:\Windows\Fonts\segoeui.ttf"]:
        if Path(path).exists():QFontDatabase.addApplicationFont(path)
    a.setFont(QFont("Microsoft YaHei",9));a.setStyleSheet(STYLE)
    yield a
    a.clipboard().clear()
    a.closeAllWindows()
    a.processEvents()


@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);w.errors=[];w.error=lambda text:w.errors.append(text)
    w.show();app.processEvents();w.canvas.fit_all();app.processEvents()
    yield w
    assert not w.errors
    w.undo.setClean();w.close();app.processEvents()


def test_live_param_copy_undo_redo(window,app):
    w=window;id=w.document.shapes[0].id;w.canvas.select_ids([id])
    unchanged=w.canvas.items_by_id[w.document.shapes[1].id]
    spin=w.findChild(QDoubleSpinBox,"param_width");assert spin is not None
    spin.setValue(8);app.processEvents();assert w.document.shapes[0].params["width"]==8
    assert w.canvas.items_by_id[w.document.shapes[1].id] is unchanged
    w.duplicate();assert len(w.document.shapes)==9
    w.undo.undo();assert len(w.document.shapes)==8
    w.undo.undo();assert w.document.shapes[0].params["width"]==12
    w.undo.redo();assert w.document.shapes[0].params["width"]==8
    w.undo.redo();assert len(w.document.shapes)==9


def test_place_pending_params_and_project_history(window,app):
    w=window
    item=next(w.catalog.item(i) for i in range(w.catalog.count()) if w.catalog.item(i).data(Qt.ItemDataRole.UserRole)=="hammerhead")
    w.catalog.setCurrentItem(item);w.choose_pattern(item)
    w.findChild(QDoubleSpinBox,"param_width").setValue(20)
    w.prepare_place(item);point=w.canvas.mapFromScene(QPointF(300,-500))
    QTest.mouseClick(w.canvas.viewport(),Qt.MouseButton.LeftButton,pos=point);app.processEvents()
    assert len(w.document.shapes)==9 and w.document.shapes[-1].params["width"]==20
    assert w.document.shapes[-1].x==pytest.approx(300,abs=2)
    w.undo.undo();assert len(w.document.shapes)==8


def test_rotation_mirror_multilayer_bake_and_delete(window,app):
    w=window;w.replace_document(Document(shapes=[Shape.from_pattern("via_enclosure")]))
    w.canvas.select_ids([w.document.shapes[0].id]);w.rotate();w.mirror();assert w.document.shapes[0].angle==90 and w.document.shapes[0].mirror
    w.bake();assert len(w.document.shapes)==2;assert {s.layer for s in w.document.shapes}=={1,2}
    assert all(not s.pattern for s in w.document.shapes)
    w.delete();assert not w.document.shapes
    w.undo.undo();assert len(w.document.shapes)==2


def test_polygon_and_rect_draw(window,app):
    w=window;w.replace_document(Document());w.canvas.fit_all();w.choose_tool("rectangle")
    a=w.canvas.mapFromScene(QPointF(100,-100));b=w.canvas.mapFromScene(QPointF(300,-200))
    QTest.mousePress(w.canvas.viewport(),Qt.MouseButton.LeftButton,pos=a)
    QTest.mouseMove(w.canvas.viewport(),b)
    QTest.mouseRelease(w.canvas.viewport(),Qt.MouseButton.LeftButton,pos=b);app.processEvents()
    assert len(w.document.shapes)==1
    assert bounds(w.document.shapes[0].world_polygons())==pytest.approx((100,100,300,200),abs=2)
    w.choose_tool("polygon")
    for p in [(400,-100),(500,-100),(500,-220),(400,-220)]:QTest.mouseClick(w.canvas.viewport(),Qt.MouseButton.LeftButton,pos=w.canvas.mapFromScene(QPointF(*p)))
    QTest.keyClick(w.canvas,Qt.Key.Key_Return);app.processEvents();assert len(w.document.shapes)==2
    QTest.keyClick(w.canvas,Qt.Key.Key_Escape);assert w.canvas.tool=="select" and w.tool_actions["select"].isChecked()


def mouse_drag(view,start,end):
    QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=start)
    event=QMouseEvent(QEvent.Type.MouseMove,QPointF(end),QPointF(view.viewport().mapToGlobal(end)),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(),event)
    QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=end)


def test_move_resize_and_vertex_drag(window,app):
    w=window;w.replace_document(Document(shapes=[Shape(polygons=[[[0,0],[100,0],[100,100],[0,100]]])]))
    s=w.document.shapes[0];w.canvas.select_ids([s.id]);w.canvas.fit_all();app.processEvents()
    start=w.canvas.mapFromScene(QPointF(50,-50));end=w.canvas.mapFromScene(QPointF(80,-70));mouse_drag(w.canvas,start,end);app.processEvents()
    assert s.x==pytest.approx(30,abs=2) and s.y==pytest.approx(20,abs=2)
    item=w.canvas.items_by_id[s.id];corner=item.mapToScene(item.outline.boundingRect().bottomRight());start=w.canvas.mapFromScene(corner)
    end=w.canvas.mapFromScene(corner+QPointF(30,20));mouse_drag(w.canvas,start,end);app.processEvents()
    box=bounds(s.world_polygons());assert box[2]-box[0]>125 and box[3]-box[1]>115
    w.bake();s=w.document.shapes[0];w.choose_tool("vertex");app.processEvents()
    x,y=s.polygons[0][0];start=w.canvas.mapFromScene(QPointF(x,-y));end=w.canvas.mapFromScene(QPointF(x-15,-y))
    mouse_drag(w.canvas,start,end);app.processEvents();assert s.polygons[0][0][0]<x-10
    w.undo.undo();assert w.document.shapes[0].polygons[0][0][0]==pytest.approx(x)


def test_freehand_to_valid_polygon(window,app):
    w=window;w.replace_document(Document());w.choose_tool("freehand")
    view=w.canvas;points=[view.mapFromScene(QPointF(x,y)) for x,y in [(100,-100),(250,-100),(250,-250),(100,-250),(100,-100)]]
    QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=points[0])
    for p in points[1:]:
        event=QMouseEvent(QEvent.Type.MouseMove,QPointF(p),QPointF(view.viewport().mapToGlobal(p)),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier);QApplication.sendEvent(view.viewport(),event)
    QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=points[-1]);app.processEvents()
    assert len(w.document.shapes)==1;assert len(w.document.shapes[0].polygons[0])==4


def test_anchor_coordinate_move_and_undo(window,app):
    from gds_studio.cad import top_left
    from PySide6.QtWidgets import QPushButton
    w=window;s=w.document.shapes[1];w.canvas.select_ids([s.id])
    old=top_left([s]);w.findChild(QDoubleSpinBox,"anchor_x").setValue(-71.2)
    w.findChild(QDoubleSpinBox,"anchor_y").setValue(82.3)
    w.findChild(QPushButton,"move_to_coordinate").click();app.processEvents()
    assert top_left(w.selected())==pytest.approx((-71.2,82.3))
    w.undo.undo();assert top_left(w.selected())==pytest.approx(old)
    w.choose_tool("move");p=w.canvas.mapFromScene(QPointF(100,-200))
    QTest.mouseClick(w.canvas.viewport(),Qt.MouseButton.LeftButton,pos=p);app.processEvents()
    assert top_left(w.selected())==pytest.approx((100,200),abs=2)


def test_layer_lock_visibility_and_clipboard(window,app):
    w=window;id=w.document.shapes[0].id;w.canvas.select_ids([id]);w.copy_selection();w.paste();assert len(w.document.shapes)==9
    item=w.layers.topLevelItem(0);item.setCheckState(2,Qt.CheckState.Checked);app.processEvents()
    assert w.document.layers[0].locked;assert not w.canvas.selected_ids()
    item=w.layers.topLevelItem(0);item.setCheckState(1,Qt.CheckState.Unchecked);app.processEvents()
    assert not w.canvas.items_by_id[id].isVisible()
    w.undo.undo();assert w.canvas.items_by_id[id].isVisible()


def wait_preview(dialog,app):
    end=time.monotonic()+5
    while time.monotonic()<end:
        app.processEvents();QTest.qWait(20)
        if dialog.polys and not dialog.timer.isActive() and not dialog.workers.get(dialog.token):return
    raise AssertionError(dialog.info.text())


def test_image_calibration_and_aligned_overlay(app,tmp_path):
    import numpy as np,cv2
    image=np.full((200,300,3),255,np.uint8);image[40:150,70:250]=0
    path=tmp_path/"图片.png";cv2.imencode(".png",image)[1].tofile(path)
    dialog=TraceDialog(path);dialog.show();app.processEvents();dialog.fit_views()
    dialog.source.points=[[70,40],[170,40]];dialog.points_changed(dialog.source.points)
    dialog.distance.setValue(50);dialog.apply_calibration();wait_preview(dialog,app)
    assert dialog.options.calibrated and dialog.options.nm_per_pixel==.5
    assert dialog.accept_button.isEnabled()
    box=dialog.trace_item.boundingRect();assert box.left()==pytest.approx(70,abs=2);assert box.top()==pytest.approx(40,abs=2)
    dialog.set_roi((50,20,220,150));wait_preview(dialog,app)
    box=dialog.trace_item.boundingRect();assert box.left()==pytest.approx(70,abs=2);assert box.top()==pytest.approx(40,abs=2)
    dialog.accept_trace();assert len(dialog.result_shapes)==1;assert dialog.result_shapes[0].metadata["calibrated"]
    dialog.close();app.processEvents()
