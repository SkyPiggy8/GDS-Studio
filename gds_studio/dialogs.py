from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QFormLayout,QVBoxLayout,QHBoxLayout,QLabel,QSpinBox,QDoubleSpinBox,QComboBox,QDialogButtonBox,QTextBrowser,QLineEdit)
from .sources import SOURCES


def number(value,minimum=.1,maximum=1e7):
    box=QDoubleSpinBox();box.setDecimals(3);box.setRange(minimum,maximum);box.setValue(value);box.setKeyboardTracking(False)
    return box


class ArrayDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("复制为阵列");self.resize(360,260)
        layout=QVBoxLayout(self);layout.addWidget(QLabel("以所选图形组为单元，按原点间距复制。"))
        form=QFormLayout();self.rows=QSpinBox();self.rows.setRange(1,100);self.rows.setValue(3)
        self.cols=QSpinBox();self.cols.setRange(1,100);self.cols.setValue(3)
        self.dx=number(250,-1e7);self.dy=number(200,-1e7)
        for label,box in [("列数",self.cols),("行数",self.rows),("X 原点间距 · nm",self.dx),("Y 原点间距 · nm",self.dy)]:form.addRow(label,box)
        layout.addLayout(form);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)


class SweepDialog(QDialog):
    def __init__(self,pattern,parent=None):
        super().__init__(parent);self.pattern=pattern;self.setWindowTitle("生成参数扫描样本");self.resize(420,330)
        layout=QVBoxLayout(self);layout.addWidget(QLabel(f"{pattern.name} · 两个参数的全组合扫描"))
        form=QFormLayout();self.key1=QComboBox();self.key2=QComboBox()
        self.key2.addItem("不使用",None)
        for k,p in pattern.parameters.items():self.key1.addItem(p.label,k);self.key2.addItem(p.label,k)
        self.values1=QLineEdit("8, 12, 16, 20");self.values2=QLineEdit("12, 16, 24")
        if "width" in pattern.parameters:self.key1.setCurrentIndex(self.key1.findData("width"))
        if "gap" in pattern.parameters:self.key2.setCurrentIndex(self.key2.findData("gap"))
        self.spacing=number(120);self.columns=QSpinBox();self.columns.setRange(1,100);self.columns.setValue(4)
        for label,w in [("参数一",self.key1),("取值（逗号分隔）",self.values1),("参数二",self.key2),("取值（逗号分隔）",self.values2),("样本边界留白 · nm",self.spacing),("排列列数",self.columns)]:form.addRow(label,w)
        layout.addLayout(form);note=QLabel("最多 400 个组合。导出 manifest 会记录每个样本的参数；默认尺寸为测试值。")
        note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)


class LayerDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle("添加图层")
        layout=QVBoxLayout(self);form=QFormLayout();self.name=QLineEdit("新图层")
        self.number=QSpinBox();self.number.setRange(0,65535);self.number.setValue(4)
        self.datatype=QSpinBox();self.datatype.setRange(0,65535)
        for l,w in [("名称",self.name),("Layer",self.number),("Datatype",self.datatype)]:form.addRow(l,w)
        layout.addLayout(form);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)


def source_browser(parent,keys=None):
    import html
    dialog=QDialog(parent);dialog.setWindowTitle("结构与工艺参考");dialog.resize(800,680)
    layout=QVBoxLayout(dialog);browser=QTextBrowser();browser.setOpenExternalLinks(True)
    text="<h2>结构与工艺参考</h2><p>查阅日期：2026-10-10。图形是公开结构类型的测试实现；参数并非晶圆厂 3 nm 设计规则。</p>"
    text+="<p>锤头、Serif、SRAF 用于几何对照；软件没有曝光、抗蚀剂或蚀刻物理求解器。图形效应提示中涉及具体库结构的用途，是基于一般机制的设计推断。</p>"
    for key in keys or SOURCES:
        if key not in SOURCES:continue
        title,url,note=SOURCES[key];text+=f'<h3>{html.escape(title)}</h3><p>{html.escape(note)}</p><p><a href="{html.escape(url)}">打开来源</a></p>'
    browser.setHtml(text);layout.addWidget(browser);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.exec()
