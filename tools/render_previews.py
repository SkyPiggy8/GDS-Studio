"""Render application-owned screenshots using the native Windows Qt renderer."""
import sys
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from gds_studio.window import MainWindow
from gds_studio.style import STYLE
from gds_studio.image_dialog import TraceDialog

root=Path(__file__).resolve().parents[1]
app=QApplication([]);app.setStyle("Fusion");app.setFont(QFont("Microsoft YaHei UI",9));app.setStyleSheet(STYLE)
w=MainWindow(root);w.show();app.processEvents();w.canvas.fit_all();w.canvas.select_ids([w.document.shapes[0].id]);app.processEvents()
w.grab().save(str(root/"examples"/"ui-preview.png"))
dialog=TraceDialog(root/"examples"/"trace_input.png",w);dialog.show();app.processEvents();dialog.fit_views()
dialog.source.points=[[35,140],[230,140]];dialog.source.redraw();dialog.points_changed(dialog.source.points);dialog.distance.setValue(97.5);dialog.apply_calibration()
def capture_trace():
    if not dialog.polys or dialog.timer.isActive() or dialog.workers.get(dialog.token):QTimer.singleShot(100,capture_trace);return
    dialog.grab().save(str(root/"examples"/"image-import-preview.png"));dialog.reject();w.undo.setClean();w.close();app.quit()
QTimer.singleShot(100,capture_trace)
sys.exit(app.exec())
