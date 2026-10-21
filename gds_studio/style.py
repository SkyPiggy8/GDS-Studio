"""Cool Morandi desktop styling with readable focus and selection states."""
STYLE = """
QMainWindow, QDialog { background: #E7ECEC; }
QWidget { color: #29373D; font-family: 'Microsoft YaHei', 'Segoe UI'; font-size: 12px; }
QMenuBar, QMenu, QToolBar { background: #F7F8F7; }
QMenuBar { padding: 3px 8px; border-bottom: 1px solid #C8D2D4; }
QMenuBar::item { padding: 6px 12px; border-radius: 4px; }
QMenuBar::item:selected, QMenu::item:selected { background: #DCE5E8; color: #293E48; }
QMenu { border: 1px solid #B9C7CA; padding: 5px; }
QMenu::item { padding: 8px 30px; border-radius: 4px; }
QMenu::separator { height: 1px; background: #D6DFE0; margin: 4px 8px; }
QToolBar { spacing: 4px; padding: 10px 12px; border-bottom: 1px solid #B9C7CA; }
QToolBar::separator { background: #CDD7D9; width: 1px; margin: 7px 7px; }
QToolButton { border: 1px solid transparent; padding: 8px 11px; border-radius: 6px; color: #435961; }
QToolButton:hover { background: #E8EEEF; border-color: #C4D0D3; }
QToolButton:checked { background: #536D78; color: #FFFFFF; border-color: #536D78; font-weight: 600; }
QPushButton { background: #F8FAF9; border: 1px solid #BCCACD; padding: 8px 12px; border-radius: 6px; color: #3C535D; }
QPushButton:hover { background: #E4ECEC; border-color: #8FA4AC; }
QPushButton:pressed { background: #D3E0E2; }
QPushButton:focus, QToolButton:focus { border: 1px solid #536D78; }
QPushButton:disabled { color: #849399; background: #EDF1F0; border-color: #D5DFE0; }
QPushButton#primaryButton, QPushButton#move_to_coordinate { background: #536D78; border-color: #536D78; color: #FFFFFF; font-weight: 600; }
QPushButton#primaryButton:hover, QPushButton#move_to_coordinate:hover { background: #425C67; border-color: #425C67; }
QPushButton#primaryButton:disabled, QPushButton#move_to_coordinate:disabled { background: #A6B6BC; border-color: #A6B6BC; color: #F7F8F7; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #FCFDFC; border: 1px solid #C2CFD1; padding: 6px 8px; border-radius: 5px; min-height: 19px; selection-background-color: #C4D6DD; selection-color: #243942; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #95A9B0; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #536D78; background: #FFFFFF; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background: #EDF1F0; color: #7B8D93; }
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button { width: 17px; }
QComboBox::drop-down { border: none; width: 23px; }
QComboBox QAbstractItemView { background: #F7F8F7; border: 1px solid #B9C7CA; selection-background-color: #DCE5E8; selection-color: #29373D; }
QListWidget, QTreeWidget, QTableWidget { border: none; background: #F7F8F7; outline: none; selection-background-color: #DCE5E8; selection-color: #293E48; alternate-background-color: #EDF1F0; gridline-color: #D7E0E1; }
QListWidget::item { padding: 8px 9px; border: 1px solid transparent; border-radius: 6px; margin: 3px 3px; }
QListWidget::item:hover { background: #ECF1F1; border-color: #D8E1E2; }
QListWidget::item:selected { background: #DCE5E8; border-color: #A5B9C1; color: #293E48; }
QTreeWidget::item { padding: 6px 2px; }
QTableWidget::item { padding: 4px; }
QHeaderView::section { background: #E6ECEC; padding: 7px; border: none; border-bottom: 1px solid #C7D3D6; color: #4F666F; }
QFrame#sidePanel { background: #F7F8F7; border: 1px solid #C4D0D2; border-radius: 8px; }
QWidget#canvasPanel { background: #F0F3F2; border-radius: 8px; }
QLabel#panelTitle { font-size: 16px; font-weight: 600; color: #344D58; padding-bottom: 5px; }
QLabel#dialogTitle { font-size: 22px; font-weight: 600; color: #344D58; }
QLabel#muted { color: #62737A; }
QLabel#sectionLabel { color: #536D78; font-weight: 600; padding-top: 12px; padding-bottom: 3px; }
QScrollArea { border: none; background: #F7F8F7; }
QWidget#inspectorContent { background: #F7F8F7; }
QTabWidget::pane { border: none; background: #F7F8F7; }
QTabBar::tab { padding: 9px 14px; margin-right: 3px; background: #EAF0F0; border-bottom: 2px solid transparent; color: #62737A; }
QTabBar::tab:selected { color: #344D58; border-bottom-color: #6F8994; background: #F7F8F7; font-weight: 600; }
QTabBar::tab:hover { background: #E0E9EB; }
QGroupBox { background: #F7F8F7; border: 1px solid #C4D0D2; border-radius: 7px; margin-top: 14px; padding: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #536D78; }
QSplitter::handle { background: #E7ECEC; width: 8px; }
QSplitter::handle:hover { background: #C8D6DA; }
QStatusBar { background: #DFE6E7; border-top: 1px solid #BCCBCD; color: #4F646D; padding: 3px 8px; }
QStatusBar::item { border: none; }
QScrollBar:vertical { width: 9px; background: transparent; margin: 3px 0; }
QScrollBar::handle:vertical { background: #BECBCD; min-height: 30px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: #91A6AE; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 9px; background: transparent; }
QScrollBar::handle:horizontal { background: #BECBCD; min-width: 30px; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QCheckBox { spacing: 6px; color: #4F646D; }
QCheckBox::indicator { width: 14px; height: 14px; }
QToolTip { border: 1px solid #A9BDC3; background: #F7F8F7; padding: 7px; color: #344D58; }
"""
