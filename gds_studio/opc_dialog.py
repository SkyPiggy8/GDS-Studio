from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QPen,QPainter
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QPushButton,QDialogButtonBox,QGraphicsView,QGraphicsScene)
from .dialogs import number
from .opc import OPCOptions,preview_opc
from .canvas import path_for


class OPCDialog(QDialog):
    def __init__(self,doc,shapes,parent=None):
        super().__init__(parent);self.doc=doc;self.shapes=shapes;self.result_shapes=[];self.setWindowTitle('实验性 OPC · 未标定');self.resize(800,640)
        layout=QVBoxLayout(self)
        note=QLabel('实验参数，不代表 7 nm 晶圆厂规则。蓝线为原图，橙色为校正掩模。\n预览通过后可替换所选图案，支持撤销；不代表晶圆成像结果。')
        note.setWordWrap(True);layout.addWidget(note);row=QHBoxLayout();form=QFormLayout();self.fields={}
        for key,label in [('bias_nm','边缘偏置（正扩张 / 负收缩）'),('end_extension_nm','长矩形线端延伸'),('hammerhead_nm','线端横向扩张'),('serif_nm','外凸角 serif 半宽'),('min_gap_nm','同层最小间距检查')]:
            box=number(getattr(OPCOptions(),key),-1000 if key=='bias_nm' else 0,1000);box.setSuffix(' nm');box.setSingleStep(.1)
            box.valueChanged.connect(self.invalidate);self.fields[key]=box;form.addRow(label,box)
        row.addLayout(form);layout.addLayout(row)
        self.view=QGraphicsView();self.scene=QGraphicsScene(self);self.view.setScene(self.scene);self.view.setRenderHint(QPainter.RenderHint.Antialiasing);layout.addWidget(self.view,1)
        self.report=QLabel();self.report.setWordWrap(True);layout.addWidget(self.report)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel)
        self.apply_button=self.buttons.button(QDialogButtonBox.StandardButton.Apply);self.apply_button.setText('应用并替换所选图案');self.apply_button.setEnabled(False);self.apply_button.clicked.connect(self.accept)
        preview=QPushButton('重新预览');preview.clicked.connect(self.generate);self.buttons.addButton(preview,QDialogButtonBox.ButtonRole.ActionRole)
        self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons);QTimer.singleShot(0,self.generate)

    def invalidate(self):
        self.result_shapes=[]
        if hasattr(self,'apply_button'):self.apply_button.setEnabled(False);self.report.setText('参数已改变，请重新预览')

    def generate(self):
        self.invalidate();self.scene.clear()
        try:
            self.result_shapes,reports=preview_opc(self.doc,self.shapes,OPCOptions(**{k:b.value() for k,b in self.fields.items()}))
            path=path_for([p for s in self.result_shapes for p in s.world_polygons()]);pen=QPen(QColor('#cf8a35'),1);pen.setCosmetic(True)
            self.scene.addPath(path,pen,QColor(238,162,61,110))
            target=path_for([p for s in self.shapes for _,_,ps in s.entries() for p in ps]);pen=QPen(QColor('#2374a1'),1);pen.setCosmetic(True);self.scene.addPath(target,pen)
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-10,-10,10,10),Qt.AspectRatioMode.KeepAspectRatio)
            errors=[f"{r['layer']}/{r['datatype']}: {e}" for r in reports for e in r['errors']]
            skipped=sum(r['skipped_non_manhattan'] for r in reports)
            self.report.setText(('未通过：'+'；'.join(errors)) if errors else f'几何检查通过；{len(self.result_shapes)} 个图层结果。非正交轮廓 {skipped} 个仅进行偏置。尚未进行光刻成像或完整 MRC / DRC。')
            self.apply_button.setEnabled(bool(self.result_shapes) and not errors)
        except (ValueError,RuntimeError) as exc:
            self.result_shapes=[];self.report.setText(str(exc));self.apply_button.setEnabled(False)
