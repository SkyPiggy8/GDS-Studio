"""Small, explicit driving-dimension dialog; the first reference stays fixed."""
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QComboBox,
    QCheckBox,QDialogButtonBox)
from .dialogs import number
from .cad import dimension_points, resolve


class DimensionDialog(QDialog):
    def __init__(self,doc,refs,old=None,parent=None):
        super().__init__(parent);self.deleted=False;self.setWindowTitle('智能尺寸 · 第一项固定');self.resize(390,270)
        layout=QVBoxLayout(self);note=QLabel('修改尺寸移动第二项。正交模式下保持相连边水平 / 竖直。\n不同对象可选择整体移动；仅测量时勾选保留标注。')
        note.setWordWrap(True);layout.addWidget(note);form=QFormLayout()
        self.mode=QComboBox()
        modes=[('实际距离','aligned')]
        if all(r['kind']=='point' for r in refs):modes += [('水平距离','horizontal'),('竖直距离','vertical')]
        for text,key in modes:self.mode.addItem(text,key)
        if old:self.mode.setCurrentIndex(max(0,self.mode.findData(old.get('mode','aligned'))))
        self.value=number(dimension_points(doc,refs,self.mode.currentData())[3],.1,2e8);self.value.setSuffix(' nm')
        self.value.setObjectName('dimension_value');form.addRow('方向',self.mode);form.addRow('尺寸',self.value)
        layout.addLayout(form)
        self.whole=QCheckBox('整体移动第二个对象（保持形状）')
        different=refs[0]['shape']!=refs[1]['shape'];self.whole.setEnabled(different);self.whole.setChecked(different);layout.addWidget(self.whole)
        self.reference=QCheckBox('仅保留测量标注');layout.addWidget(self.reference)
        self.reference.toggled.connect(lambda v:self.value.setEnabled(not v))
        self.mode.currentIndexChanged.connect(lambda:self.value.setValue(dimension_points(doc,refs,self.mode.currentData())[3]))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        if old:
            delete=buttons.addButton('删除标注',QDialogButtonBox.ButtonRole.DestructiveRole)
            delete.clicked.connect(self.delete_dimension)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def delete_dimension(self):
        self.deleted=True;self.accept()
