STYLE = """
QMainWindow, QDialog { background: #f5f7f9; }
QWidget { color: #243746; font-family: 'Segoe UI', 'Microsoft YaHei UI'; font-size: 12px; }
QMenuBar, QMenu, QToolBar { background: #ffffff; }
QMenuBar { padding: 4px; border-bottom: 1px solid #e1e7ec; }
QMenuBar::item { padding: 5px 12px; }
QMenu::item { padding: 7px 28px; }
QMenu::item:selected { background: #e8f2f8; }
QToolBar { spacing: 5px; padding: 9px 12px; border-bottom: 1px solid #dde5eb; }
QToolButton { border: 1px solid transparent; padding: 7px 10px; border-radius: 5px; }
QToolButton:hover { background: #edf3f7; }
QToolButton:checked { background: #dfedf6; color: #185d85; border-color: #bdd8e8; }
QPushButton { background: #ffffff; border: 1px solid #d4dfe7; padding: 7px 12px; border-radius: 5px; }
QPushButton:hover { background: #edf4f8; border-color: #a8c6d8; }
QPushButton:pressed { background: #dcebf4; }
QPushButton:disabled { color: #9aaab6; background: #f2f5f7; }
QPushButton#primaryButton { background: #267ca8; border-color: #267ca8; color: white; font-weight: 600; }
QPushButton#primaryButton:hover { background: #206d96; }
QPushButton#primaryButton:disabled { background: #b5c9d4; border-color: #b5c9d4; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #fff; border: 1px solid #d9e2e9; padding: 5px 7px; border-radius: 4px; min-height: 19px; selection-background-color: #b8daed; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #73acca; }
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button { width: 16px; }
QComboBox::drop-down { border: none; width: 22px; }
QListWidget, QTreeWidget, QTableWidget { border: none; background: white; outline: none; selection-background-color: #e5f0f7; selection-color: #225b7c; }
QListWidget::item { padding: 7px 8px; border-radius: 4px; margin: 2px 4px; }
QListWidget::item:hover { background: #f1f6f9; }
QListWidget::item:selected { background: #e3f0f7; }
QTreeWidget::item { padding: 5px 2px; }
QHeaderView::section { background: #f1f5f8; padding: 6px; border: none; }
QFrame#sidePanel { background: white; border: 1px solid #e0e7ed; border-radius: 6px; }
QLabel#panelTitle { font-size: 16px; font-weight: 600; color: #213d50; }
QLabel#dialogTitle { font-size: 22px; font-weight: 600; }
QLabel#muted { color: #748896; }
QLabel#sectionLabel { color: #6a7f8e; font-weight: 600; padding-top: 9px; }
QScrollArea { border: none; background: white; }
QWidget#inspectorContent { background: white; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 10px 13px; background: #f4f7f9; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #206b96; border-bottom-color: #2c85b0; background: white; }
QGroupBox { background: white; border: 1px solid #dce5eb; border-radius: 6px; margin-top: 12px; padding: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QSplitter::handle { background: #f1f4f7; width: 6px; }
QStatusBar { background: #ffffff; border-top: 1px solid #e0e7ed; color: #667e8d; }
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: #cfdae2; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { border: 1px solid #ccdce6; background: #ffffff; padding: 6px; color: #234257; }
"""
