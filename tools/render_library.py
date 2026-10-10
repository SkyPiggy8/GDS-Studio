"""Capture application-owned native Windows sample-manager views."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from gds_studio.window import MainWindow
from gds_studio.style import STYLE


def main():
    root=Path(__file__).resolve().parents[1];app=QApplication([]);app.setFont(QFont("Microsoft YaHei UI",9));app.setStyle("Fusion");app.setStyleSheet(STYLE)
    w=MainWindow(root);w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);w.show();w.open_samples();s=w.sample_window;s.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
    app.processEvents();s.refresh(8);s.compare();app.processEvents();s.grab().save(str(root/"examples"/"library-preview.png"))
    s.search.setText("论文");s.reset_page();app.processEvents();s.grab().save(str(root/"examples"/"paper-library-preview.png"))
    s.close();w.undo.setClean();w.close();app.processEvents()


if __name__=="__main__":main()
