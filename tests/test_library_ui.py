import time
import json
import pytest
from PySide6.QtCore import QSizeF
from PySide6.QtGui import QPdfWriter,QPainter
from PySide6.QtWidgets import QFileDialog,QInputDialog
from test_ui import app,window
from gds_studio.geometry import rect
from gds_studio.model import Shape,Document
from gds_studio.library_window import SampleWindow
from gds_studio.image_dialog import TraceDialog


def test_gallery_collect_compare_edit_and_save(window,app):
    w=window;w.open_samples();s=w.sample_window;s.error=lambda message:w.errors.append(message);app.processEvents()
    assert s.gallery.count()>20
    w.replace_document(Document(shapes=[Shape(polygons=[rect(0,0,27,83)],name="new rectangle")]))
    s.collect_editor();assert s.current_id is not None and s.name.text()=="new rectangle"
    assert s.matches.rowCount()>0
    s.name.setText("人工修正");s.tags.setText("test, line");s.review.setCurrentIndex(1);s.save_attributes()
    s.search.setText("test");s.reset_page();assert s.gallery.count()==1
    assert s.review.currentIndex()==1
    s.edit_sample();assert len(w.document.shapes)==2 and w.document.shapes[-1].metadata["library_sample_id"]==s.current_id
    w.undo.undo();assert len(w.document.shapes)==1
    s.close()


def wait_job(s,app,timeout=20):
    deadline=time.monotonic()+timeout
    while s.process and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    assert s.process is None,s.status.text()


def test_background_index_extract_and_cancel(window,app,tmp_path):
    from gds_studio.io import export_gds
    source=tmp_path/"source.gds";export_gds(source,Document(shapes=[Shape(polygons=[rect(0,0,20,40)])]))
    window.open_samples();s=window.sample_window;s.error=lambda message:window.errors.append(message)
    s.register_sources([str(source)]);wait_job(s,app)
    assert len(s.sources[str(source)]["cells"])==2 and s.cells.count()==2
    s.mode.setCurrentIndex(3);s.extract();wait_job(s,app)
    assert "完成" in s.status.text()
    s.start_job("index",{"path":str(source)});s.cancel_job();wait_job(s,app)
    assert s.extract_button.isEnabled()
    s.close()


def test_pdf_page_render_and_metadata_in_library(window,app,tmp_path,monkeypatch):
    pdf=tmp_path/"paper.pdf";writer=QPdfWriter(str(pdf));writer.setResolution(72);p=QPainter(writer);p.drawRect(100,100,200,100);p.end()
    monkeypatch.setattr(QFileDialog,"getOpenFileName",lambda *a,**k:(str(pdf),""))
    def integer(*a,**k):return (240 if "DPI" in a[2] else 1,True)
    monkeypatch.setattr(QInputDialog,"getInt",integer)
    monkeypatch.setattr(QInputDialog,"getItem",lambda *a,**k:("一个完整结构样本",True))
    def fake_exec(dialog):
        dialog.timer.stop();dialog.result_shapes=[Shape(polygons=[rect(0,0,20,40)],metadata={"calibrated":False,"trace_roi_px":[1,2,30,40]})];return 1
    monkeypatch.setattr(TraceDialog,"exec",fake_exec)
    window.open_samples();s=window.sample_window;s.error=lambda message:window.errors.append(message);s.import_paper()
    assert not window.errors
    sample=s.library.get(s.current_id);assert not sample["calibrated"]
    origin=sample["origins"][0];assert origin["kind"]=="paper" and origin["source_metadata"]["page"]==1
    assert list((tmp_path/"userdata"/"paper_pages").glob("*.png"))
    s.close()
