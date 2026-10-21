import logging
import sys
from pathlib import Path
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QApplication,QMessageBox
from .style import STYLE
from .catalog import load_plugins


def workspace_root():
    return Path(sys.executable).parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent.parent


def main():
    from multiprocessing import freeze_support
    freeze_support()
    root=workspace_root();logs=root/"userdata";logs.mkdir(exist_ok=True)
    logging.basicConfig(filename=logs/"studio.log",level=logging.INFO,encoding="utf-8")
    app=QApplication(sys.argv);app.setApplicationName("GDS Studio");app.setOrganizationName("GDS Studio")
    # Explicitly register installed Windows fonts, including in packaged / offscreen runs.
    for font_path in (Path('C:/Windows/Fonts/msyh.ttc'),Path('C:/Windows/Fonts/segoeui.ttf')):
        if font_path.exists():QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Microsoft YaHei",9));app.setStyle("Fusion");app.setStyleSheet(STYLE)
    # Release Python-owned MIME data before Qt and Python shutdown ordering.
    def release_clipboard():
        clipboard=app.clipboard()
        if clipboard.ownsClipboard() and clipboard.mimeData().hasFormat("application/x-gds-studio-shapes"):
            clipboard.clear()
    app.aboutToQuit.connect(release_clipboard)
    def error_hook(type_,value,tb):
        logging.error("Unhandled UI error",exc_info=(type_,value,tb));QMessageBox.critical(None,"发生错误",f"{value}\n\n详细记录：{logs / 'studio.log'}")
    sys.excepthook=error_hook
    errors=load_plugins(root/"user_plugins")
    from .window import MainWindow
    window=MainWindow(root)
    library_check="--library-self-check" in sys.argv
    self_check="--self-check" in sys.argv or library_check
    if self_check:
        from PySide6.QtCore import Qt
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
    window.show()
    if len(sys.argv)>1 and not self_check:
        from .io import load_project
        try:window.replace_document(load_project(sys.argv[1]),sys.argv[1])
        except Exception as exc:window.error(str(exc))
    if library_check:
        from PySide6.QtCore import QTimer
        import json,time
        index=sys.argv.index("--library-self-check");out=Path(sys.argv[index+1]);out.mkdir(parents=True,exist_ok=True)
        window.open_samples();manager=window.sample_window;manager.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
        source=sys.argv[index+2] if len(sys.argv)>index+2 else str(root/"examples"/"starter.gds")
        state={"stage":"index","deadline":time.monotonic()+45};manager.register_sources([source]);manager.tabs.setCurrentIndex(1)
        timer=QTimer(window)
        def verify_library():
            try:
                if time.monotonic()>state["deadline"]:raise TimeoutError(manager.status.text())
                if manager.process:return
                if state["stage"]=="index":
                    if not manager.sources.get(source):raise ValueError(manager.status.text())
                    manager.grab().save(str(out/"library-source-preview.png"))
                    manager.select_tops();manager.recursive.setChecked(True);manager.mode.setCurrentIndex(2);manager.use_roi.setChecked(True)
                    for spin,value in zip(manager.roi,[0,0,1000,1000]):spin.setValue(value)
                    manager.extract();state["stage"]="extract"
                else:
                    if "完成" not in manager.status.text():raise ValueError(manager.status.text())
                    manager.tabs.setCurrentIndex(0);manager.refresh();manager.grab().save(str(out/"library-gallery-preview.png"))
                    report={"sample_count":manager.library.count(),"layers":manager.library.layers(),"source":manager.sources[source],"extraction_status":manager.status.text(),"database":str(manager.database),"worker_process_verified":True}
                    (out/"library-check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
                    timer.stop();manager.close();window.undo.setClean();window.close();app.quit()
            except Exception:
                logging.exception("Library self check failed");timer.stop();manager.close();app.exit(1)
        timer.timeout.connect(verify_library);timer.start(150)
    elif self_check:
        from PySide6.QtCore import QTimer
        def check():
            import json
            from .io import export_gds
            try:
                index=sys.argv.index("--self-check");out=Path(sys.argv[index+1]);out.mkdir(parents=True,exist_ok=True)
                window.canvas.fit_all();report=export_gds(out/"desktop-check.gds",window.document)
                report["screenshot_saved"]=window.grab().save(str(out/"desktop-check.png"))
                report["plugin_errors"]=errors
                (out/"desktop-check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
                window.undo.setClean();window.close();app.quit()
            except Exception:
                logging.exception("Self check failed");app.exit(1)
        QTimer.singleShot(180,check)
    elif errors:QMessageBox.warning(window,"插件未加载","\n".join(errors))
    sys.exit(app.exec())
