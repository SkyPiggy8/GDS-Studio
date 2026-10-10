from __future__ import annotations
import copy
import itertools
import json
import math
from pathlib import Path
import gdstk
from PySide6.QtCore import Qt, QSize, QTimer, QMimeData
from PySide6.QtGui import (QAction,QActionGroup,QColor,QIcon,QPainter,QPixmap,QPen,QUndoCommand,QUndoStack,QKeySequence,QShortcut)
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QListWidget,QListWidgetItem,QTreeWidget,QTreeWidgetItem,QSplitter,QScrollArea,QFrame,QTabWidget,QToolBar,QFileDialog,QMessageBox,QInputDialog,QTableWidget,QTableWidgetItem,QHeaderView,QApplication,QAbstractItemView,QCheckBox)
from .model import Document,Shape,Layer,demo
from .catalog import REGISTRY
from .canvas import LayoutCanvas,path_for
from .geometry import bounds,boolean,offset,validate,transform
from .io import save_project,load_project,export_gds,inspect_cells,import_gds
from .dialogs import ArrayDialog,SweepDialog,LayerDialog,number,source_browser
from .image_dialog import TraceDialog


class DocumentCommand(QUndoCommand):
    def __init__(self,window,before,after,label):
        super().__init__(label);self.window=window;self.before=before;self.after=after;self.initial=True
    def undo(self):self.window.restore(self.before)
    def redo(self):
        if self.initial:self.initial=False
        else:self.window.restore(self.after)


def heading(text,muted=False):
    label=QLabel(text);label.setWordWrap(True);label.setObjectName("muted" if muted else "sectionLabel");return label


def icon_for(pattern):
    pix=QPixmap(60,50);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path=path_for(pattern.generate(pattern.defaults()));b=path.boundingRect()
    if b.width()>0 and b.height()>0:
        scale=min(48/b.width(),38/b.height());painter.translate(30,25);painter.scale(scale,scale);painter.translate(-b.center())
        pen=QPen(QColor("#2c7da8"),1);pen.setCosmetic(True);painter.setPen(pen);painter.setBrush(QColor("#73afd0"));painter.drawPath(path)
    painter.end();return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self,root):
        super().__init__();self.root=Path(root);self.project_path=None;self.document=demo();self.pending=None;self.updating=False;self.vertex_poly=0
        self.undo=QUndoStack(self);self.undo.setUndoLimit(80);self.undo.cleanChanged.connect(self.update_title)
        self.setWindowTitle("GDS Studio");self.resize(1510,940);self.setMinimumSize(1100,720)
        self.make_actions();self.make_ui();self.refresh([self.document.shapes[0].id],inspector=True)
        QTimer.singleShot(50,self.canvas.fit_all)
        self.autosave_timer=QTimer(self);self.autosave_timer.timeout.connect(self.autosave);self.autosave_timer.start(30000)
        self.statusBar().showMessage("双击左侧结构 → 在画布点击放置。滚轮缩放 · 空格拖动画布 · 所有尺寸以 nm 显示。")

    def make_actions(self):
        menu=self.menuBar()
        def action(text,callback,shortcut=None):
            a=QAction(text,self)
            a.triggered.connect(lambda checked=False:callback())
            if shortcut:a.setShortcut(QKeySequence(shortcut))
            return a
        self.action=action
        file=menu.addMenu("文件")
        self.new_action=action("新建空白版图",self.new_document,"Ctrl+N");file.addAction(self.new_action)
        file.addAction(action("打开工程…",self.open_project,"Ctrl+O"))
        self.save_action=action("保存工程",self.save,"Ctrl+S");file.addAction(self.save_action)
        file.addAction(action("工程另存为…",lambda:self.save(True),"Ctrl+Shift+S"));file.addSeparator()
        self.image_action=action("导入图片…",self.import_image,"Ctrl+I");file.addAction(self.image_action)
        file.addAction(action("导入 GDS…",self.open_gds));file.addSeparator()
        self.export_action=action("导出 GDS…",self.export,"Ctrl+E");file.addAction(self.export_action)
        file.addAction(action("导出画布 PNG…",self.export_png));file.addSeparator()
        file.addAction(action("恢复自动保存",self.recover));file.addAction(action("载入起始示例",self.load_demo))
        edit=menu.addMenu("编辑");self.undo_action=self.undo.createUndoAction(self,"撤销");self.undo_action.setShortcut(QKeySequence("Ctrl+Z"));edit.addAction(self.undo_action)
        self.redo_action=self.undo.createRedoAction(self,"重做");self.redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"));edit.addAction(self.redo_action)
        edit.addSeparator()
        edit.addAction(action("复制",self.copy_selection,"Ctrl+C"));edit.addAction(action("粘贴",self.paste,"Ctrl+V"))
        edit.addAction(action("原地偏移复制",self.duplicate,"Ctrl+D"));edit.addAction(action("删除",self.delete,"Delete"))
        edit.addAction(action("全选",lambda:self.canvas.select_ids([s.id for s in self.document.shapes if not self.document.layer_info(s.layer,s.datatype).locked]),"Ctrl+A"))
        shape=menu.addMenu("图形")
        self.array_action=action("复制阵列…",self.array);shape.addAction(self.array_action)
        self.sweep_action=action("参数扫描…",self.sweep);shape.addAction(self.sweep_action)
        shape.addAction(action("旋转 90°",self.rotate,"Ctrl+R"));shape.addAction(action("镜像",self.mirror,"Ctrl+M"))
        shape.addAction(action("左边缘对齐",self.align_left));shape.addAction(action("展开为多边形",self.bake))
        shape.addSeparator()
        for label,op in [("合并 Union","or"),("相减（第一对象减其余）","not"),("交集 Intersection","and"),("异或 XOR","xor")]:shape.addAction(action(label,lambda op=op:self.boolean_op(op)))
        shape.addAction(action("边缘扩张 / 收缩…",self.bias))
        samples=menu.addMenu("样本库");self.samples_action=action("打开版图样本库",self.open_samples,"Ctrl+L");samples.addAction(self.samples_action)
        view=menu.addMenu("视图");self.fit_action=action("适应全部",lambda:self.canvas.fit_all(),"F");view.addAction(self.fit_action)
        view.addAction(action("放大",lambda:self.canvas.zoom(1.2),"Ctrl++"));view.addAction(action("缩小",lambda:self.canvas.zoom(1/1.2),"Ctrl+-"))
        help_=menu.addMenu("帮助");help_.addAction(action("操作说明",self.help));help_.addAction(action("论文与官方参考",lambda:source_browser(self)))

    def make_ui(self):
        toolbar=QToolBar("绘图工具",self);toolbar.setMovable(False);self.addToolBar(toolbar)
        self.tool_group=QActionGroup(self);self.tool_group.setExclusive(True);self.tool_actions={}
        for key,label,shortcut in [("select","选择","V"),("rectangle","矩形","R"),("polygon","多边形","P"),("freehand","手绘","B"),("vertex","顶点","E"),("measure","测量","M")]:
            a=QAction(label,self);a.setCheckable(True);a.setShortcut(QKeySequence(shortcut));a.setToolTip(f"{label} · {shortcut}")
            a.triggered.connect(lambda checked,k=key:self.choose_tool(k));self.tool_group.addAction(a);toolbar.addAction(a);self.tool_actions[key]=a
        self.tool_actions["select"].setChecked(True);toolbar.addSeparator();toolbar.addAction(self.fit_action);toolbar.addAction(self.array_action);toolbar.addAction(self.sweep_action)
        spacer=QWidget();spacer.setSizePolicy(QWidget().sizePolicy().Policy.Expanding,QWidget().sizePolicy().Policy.Preferred);toolbar.addWidget(spacer)
        toolbar.addAction(self.samples_action);toolbar.addAction(self.image_action);toolbar.addAction(self.save_action);toolbar.addAction(self.export_action)
        wrapper=QWidget();outer=QVBoxLayout(wrapper);outer.setContentsMargins(10,10,10,8);outer.setSpacing(8)
        self.splitter=QSplitter();self.splitter.setChildrenCollapsible(False)
        left=QFrame();left.setObjectName("sidePanel");left_layout=QVBoxLayout(left);left_layout.setContentsMargins(10,12,10,8)
        title=QLabel("结构库");title.setObjectName("panelTitle");left_layout.addWidget(title)
        self.tabs=QTabWidget();left_layout.addWidget(self.tabs,1)
        lib=QWidget();lib_l=QVBoxLayout(lib);lib_l.setContentsMargins(0,10,0,0)
        self.search=QLineEdit();self.search.setPlaceholderText("搜索形状 / 英文名称");self.search.textChanged.connect(self.filter_catalog);lib_l.addWidget(self.search)
        self.category=QComboBox();self.category.addItem("全部结构")
        self.category.addItems(list(dict.fromkeys(p.category for p in REGISTRY.values())));self.category.currentTextChanged.connect(self.filter_catalog);lib_l.addWidget(self.category)
        self.catalog=QListWidget();self.catalog.setIconSize(QSize(60,50));self.catalog.setSpacing(1)
        self.catalog.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.catalog.setTextElideMode(Qt.TextElideMode.ElideRight)
        for key,p in REGISTRY.items():
            item=QListWidgetItem(icon_for(p),f"{p.name}\n{p.category}");item.setData(Qt.ItemDataRole.UserRole,key);item.setToolTip(p.description);self.catalog.addItem(item)
        self.catalog.itemClicked.connect(self.choose_pattern);self.catalog.itemDoubleClicked.connect(self.prepare_place);lib_l.addWidget(self.catalog,1)
        self.library_count=heading(f"{len(REGISTRY)} 类可调结构",True);lib_l.addWidget(self.library_count)
        place=QPushButton("在画布放置");place.setObjectName("primaryButton");place.clicked.connect(lambda:self.prepare_place(self.catalog.currentItem()));lib_l.addWidget(place)
        self.tabs.addTab(lib,"结构")
        tree=QWidget();tree_l=QVBoxLayout(tree);tree_l.setContentsMargins(0,10,0,0)
        self.layers=QTreeWidget();self.layers.setHeaderLabels(["图层","显示","锁定"]);self.layers.setColumnWidth(0,125);self.layers.setColumnWidth(1,48)
        self.layers.itemChanged.connect(self.layer_changed);self.layers.itemDoubleClicked.connect(self.layer_color);tree_l.addWidget(self.layers,1)
        add=QPushButton("添加图层");add.clicked.connect(self.add_layer);tree_l.addWidget(add)
        tree_l.addWidget(heading("画布对象"));self.objects=QListWidget();self.objects.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self.objects.itemSelectionChanged.connect(self.objects_selected);tree_l.addWidget(self.objects,2)
        self.tabs.addTab(tree,"图层 / 对象");left.setMinimumWidth(230);left.setMaximumWidth(380);self.splitter.addWidget(left)
        center=QWidget();center_l=QVBoxLayout(center);center_l.setContentsMargins(0,0,0,0);center_l.setSpacing(0)
        options=QHBoxLayout();options.setContentsMargins(12,3,12,8);self.doc_label=QLabel();self.doc_label.setObjectName("muted");options.addWidget(self.doc_label,1)
        options.addWidget(QLabel("网格"));self.grid=number(1,.1,10000);self.grid.setFixedWidth(90);self.grid.setSuffix(" nm");self.grid.valueChanged.connect(self.set_grid);options.addWidget(self.grid)
        self.constraint=QComboBox();self.constraint.addItems(["横平竖直","允许 45°","自由方向"]);self.constraint.currentIndexChanged.connect(self.set_constraint);options.addWidget(self.constraint);center_l.addLayout(options)
        self.canvas=LayoutCanvas();center_l.addWidget(self.canvas,1);self.splitter.addWidget(center)
        self.canvas.selectionChanged.connect(self.selection_changed);self.canvas.edited.connect(self.commit_canvas)
        self.canvas.toolChanged.connect(self.sync_tool)
        self.canvas.shapeDrawn.connect(self.add_drawn);self.canvas.placeRequested.connect(self.place)
        self.canvas.notice.connect(lambda s:self.statusBar().showMessage(s,10000));self.canvas.coordinates.connect(self.update_coordinates)
        for key,dx,dy in [(Qt.Key.Key_Left,-1,0),(Qt.Key.Key_Right,1,0),(Qt.Key.Key_Up,0,1),(Qt.Key.Key_Down,0,-1)]:
            shortcut=QShortcut(QKeySequence(key),self.canvas);shortcut.setContext(Qt.ShortcutContext.WidgetShortcut);shortcut.activated.connect(lambda dx=dx,dy=dy:self.nudge(dx,dy))
        self.inspector=QFrame();self.inspector.setObjectName("sidePanel");right_l=QVBoxLayout(self.inspector);right_l.setContentsMargins(15,12,15,12)
        t=QLabel("参数与属性");t.setObjectName("panelTitle");right_l.addWidget(t)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);right_l.addWidget(self.scroll,1);self.inspector.setMinimumWidth(290);self.inspector.setMaximumWidth(440);self.splitter.addWidget(self.inspector)
        self.splitter.setSizes([252,936,310]);outer.addWidget(self.splitter,1);self.setCentralWidget(wrapper)
        self.coordinate_label=QLabel("X 0 · Y 0 nm");self.statusBar().addPermanentWidget(self.coordinate_label)

    def filter_catalog(self,*args):
        query=self.search.text().strip().lower();category=self.category.currentText();count=0
        for i in range(self.catalog.count()):
            item=self.catalog.item(i);p=REGISTRY[item.data(Qt.ItemDataRole.UserRole)]
            visible=(category=="全部结构" or p.category==category) and query in f"{p.name} {p.key} {p.tags} {p.category}".lower()
            item.setHidden(not visible);count+=visible
        self.library_count.setText(f"{count} / {len(REGISTRY)} 类结构")

    def selected(self):
        ids=set(self.canvas.selected_ids());return [s for s in self.document.shapes if s.id in ids]

    def open_samples(self):
        from .library_window import SampleWindow
        if not hasattr(self,"sample_window"):self.sample_window=SampleWindow(self)
        self.sample_window.show();self.sample_window.raise_();self.sample_window.activateWindow()

    def add_library_shapes(self,shapes):
        point=self.canvas.mapToScene(self.canvas.viewport().rect().center())
        x0,y0,x1,y1=bounds([p for s in shapes for p in s.world_polygons()])
        for s in shapes:s.x+=point.x()-(x0+x1)/2;s.y+=-point.y()-(y0+y1)/2
        self.mutate("加入样本库结构",lambda:self.document.shapes.extend(shapes),[s.id for s in shapes])
        self.canvas.fit_all()

    def editable(self):
        return [s for s in self.selected() if not self.document.layer_info(s.layer,s.datatype).locked]

    def choose_pattern(self,item):
        if not item:return
        self.pending=Shape.from_pattern(item.data(Qt.ItemDataRole.UserRole));self.canvas.select_ids([]);self.show_inspector()

    def prepare_place(self,item):
        if not item:
            self.statusBar().showMessage("先从左侧选择一种结构",5000);return
        key=item.data(Qt.ItemDataRole.UserRole)
        if not self.pending or self.pending.pattern!=key:self.choose_pattern(item)
        self.canvas.set_tool("place",key)
        self.tool_group.setExclusive(False)
        for a in self.tool_actions.values():a.setChecked(False)
        self.tool_group.setExclusive(True)
        self.statusBar().showMessage(f"点击画布放置 {REGISTRY[key].name}，可连续放置；Esc 退出。")

    def choose_tool(self,key):
        self.tool_actions[key].setChecked(True);self.canvas.set_tool(key);self.canvas.setFocus()
        tips={"polygon":"逐点绘制，Enter / 双击 / 右键闭合；Esc 取消。","freehand":"按住左键画封闭轮廓，松开后自动规整。","vertex":"先选择展开后的多边形，再拖动圆形顶点。","select":"拖动移动，框选多选；右下角方块缩放。","rectangle":"拖出矩形区域。","measure":"拖动两点测量距离。"}
        self.statusBar().showMessage(tips[key])

    def sync_tool(self,key):
        self.tool_group.setExclusive(False)
        for name,action in self.tool_actions.items():action.setChecked(name==key)
        self.tool_group.setExclusive(True)

    def refresh(self,ids=None,inspector=False):
        self.updating=True;self.document.ensure_layers();self.canvas.set_document(self.document,ids)
        self.doc_label.setText(f"{self.document.name}   /   {len(self.document.shapes):,} 个对象")
        self.grid.setValue(self.document.grid);self.constraint.setCurrentIndex({"orthogonal":0,"octilinear":1,"free":2}[self.document.constraint])
        self.layers.blockSignals(True);self.layers.clear()
        for l in self.document.layers:
            item=QTreeWidgetItem([f"{l.number}/{l.datatype}  {l.name}","",""]);item.setData(0,Qt.ItemDataRole.UserRole,(l.number,l.datatype))
            item.setForeground(0,QColor(l.color));item.setCheckState(1,Qt.CheckState.Checked if l.visible else Qt.CheckState.Unchecked);item.setCheckState(2,Qt.CheckState.Checked if l.locked else Qt.CheckState.Unchecked);self.layers.addTopLevelItem(item)
        self.layers.blockSignals(False);self.objects.blockSignals(True);self.objects.clear();selected=set(self.canvas.selected_ids())
        for s in self.document.shapes:
            item=QListWidgetItem(f"{s.name}   ·   {s.layer}/{s.datatype}");item.setData(Qt.ItemDataRole.UserRole,s.id);self.objects.addItem(item);item.setSelected(s.id in selected)
        self.objects.blockSignals(False);self.updating=False
        if inspector:self.show_inspector()
        self.update_title()

    def commit(self,before,label,ids=None,inspector=False):
        self.document.ensure_layers();after=self.document.to_dict()
        if before!=after:self.undo.push(DocumentCommand(self,before,after,label))
        self.refresh(ids,inspector)

    def mutate(self,label,fn,ids=None,inspector=False):
        before=self.document.to_dict()
        try:
            fn();self.commit(before,label,ids,inspector)
        except Exception as exc:
            self.document=Document.from_dict(before);self.refresh(inspector=True);self.error(str(exc))

    def restore(self,state):
        ids=self.canvas.selected_ids();self.document=Document.from_dict(state);self.refresh(ids,True)

    def commit_canvas(self,before,label):self.commit(before,label,inspector=True)

    def selection_changed(self,ids):
        if self.updating:return
        self.objects.blockSignals(True)
        for i in range(self.objects.count()):self.objects.item(i).setSelected(self.objects.item(i).data(Qt.ItemDataRole.UserRole) in ids)
        self.objects.blockSignals(False);self.show_inspector()

    def objects_selected(self):
        if not self.updating:self.canvas.select_ids([i.data(Qt.ItemDataRole.UserRole) for i in self.objects.selectedItems()])

    def show_inspector(self):
        old=self.scroll.takeWidget()
        if old:old.deleteLater()
        panel=QWidget();panel.setObjectName("inspectorContent");layout=QVBoxLayout(panel);layout.setContentsMargins(0,3,0,8);layout.setSpacing(10);self.scroll.setWidget(panel)
        selected=self.selected();s=selected[0] if len(selected)==1 else self.pending if not selected else None
        if s is None:
            layout.addWidget(heading("选择一个结构开始编辑" if not selected else f"已选择 {len(selected)} 个对象",True))
            if selected:
                b=QPushButton("复制为阵列");b.clicked.connect(self.array);layout.addWidget(b)
                b=QPushButton("合并为多边形");b.clicked.connect(lambda:self.boolean_op("or"));layout.addWidget(b)
            else:
                layout.addWidget(heading("双击左侧结构并在画布点击放置。也可以使用矩形、多边形或手绘工具。",True))
                b=QPushButton("导入论文截图");b.clicked.connect(self.import_image);layout.addWidget(b)
            layout.addStretch();return
        pending=not selected;locked=not pending and self.document.layer_info(s.layer,s.datatype).locked
        title=QLabel(s.name);title.setObjectName("panelTitle");layout.addWidget(title)
        layout.addWidget(heading("待放置 · 参数会用于下一次放置" if pending else "参数修改即时更新 · 支持撤销",True))
        form=QFormLayout();form.setHorizontalSpacing(12);form.setVerticalSpacing(9)
        if not pending:
            name=QLineEdit(s.name);name.editingFinished.connect(lambda:self.change_property(s.id,"name",name.text()));form.addRow("名称",name)
        layerbox=QComboBox()
        for l in self.document.layers:layerbox.addItem(f"{l.number}/{l.datatype} · {l.name}",(l.number,l.datatype))
        index=layerbox.findData((s.layer,s.datatype));layerbox.setCurrentIndex(max(0,index))
        layerbox.currentIndexChanged.connect(lambda i:self.change_layer(s,layerbox.itemData(i),pending));form.addRow("图层",layerbox)
        if s.pattern:
            pattern=REGISTRY[s.pattern]
            layout.addWidget(heading(pattern.description,True))
            for key,p in pattern.parameters.items():
                if p.integer:box=QSpinBox();box.setRange(int(p.minimum),int(p.maximum));box.setValue(int(s.params[key]));box.setKeyboardTracking(False)
                else:box=number(s.params[key],p.minimum,p.maximum);box.setSingleStep(1)
                box.setObjectName(f"param_{key}")
                box.valueChanged.connect(lambda value,k=key:self.change_param(s,k,value,pending));form.addRow(p.label,box)
        if not pending:
            for key,label,value,minimum,maximum in [("x","X 位置 · nm",s.x,-2e8,2e8),("y","Y 位置 · nm",s.y,-2e8,2e8),("angle","旋转 · °",s.angle,-36000,36000),("sx","X 缩放",s.sx,.01,1000),("sy","Y 缩放",s.sy,.01,1000)]:
                box=number(value,minimum,maximum);box.setObjectName(f"property_{key}");box.valueChanged.connect(lambda v,k=key:self.change_property(s.id,k,v));form.addRow(label,box)
        layout.addLayout(form)
        x0,y0,x1,y1=bounds(s.world_polygons());self.size_label=heading(f"外接尺寸  {x1-x0:.2f} × {y1-y0:.2f} nm",True);layout.addWidget(self.size_label)
        if locked:layout.addWidget(heading("此图层已锁定。请在「图层 / 对象」解除锁定。",True))
        else:
            if not pending:
                row=QHBoxLayout()
                for text,fn in [("复制",self.duplicate),("旋转",self.rotate),("镜像",self.mirror)]:b=QPushButton(text);b.clicked.connect(fn);row.addWidget(b)
                layout.addLayout(row)
                bake=QPushButton("展开为多边形 / 编辑顶点");bake.clicked.connect(self.bake);layout.addWidget(bake)
                if not s.pattern and s.x==s.y==s.angle==0 and s.sx==s.sy==1 and not s.mirror:self.vertex_table(layout,s)
            else:
                button=QPushButton("放置此结构");button.setObjectName("primaryButton");button.clicked.connect(lambda:self.prepare_place(self.catalog.currentItem()));layout.addWidget(button)
        if s.pattern:
            p=REGISTRY[s.pattern];layout.addWidget(heading("效应提示"));layout.addWidget(heading(p.effect,True))
            b=QPushButton("查看参考来源");b.clicked.connect(lambda:source_browser(self,p.sources));layout.addWidget(b)
        if s.metadata.get("source_image"):
            layout.addWidget(heading("图片标定"));layout.addWidget(heading(f"{'已标定' if s.metadata.get('calibrated') else '未标定草图'} · {s.metadata.get('nm_per_pixel',1):.6g} nm / px",True))
        if locked:
            for i in range(form.rowCount()):
                field=form.itemAt(i,QFormLayout.ItemRole.FieldRole)
                if field and field.widget():field.widget().setEnabled(False)
        layout.addStretch()

    def vertex_table(self,layout,s):
        layout.addWidget(heading("顶点坐标 · nm"))
        combo=QComboBox()
        for i in range(len(s.polygons)):combo.addItem(f"轮廓 {i+1}",i)
        self.vertex_poly=min(self.vertex_poly,max(0,len(s.polygons)-1));combo.setCurrentIndex(self.vertex_poly);layout.addWidget(combo)
        table=QTableWidget();table.setColumnCount(2);table.setHorizontalHeaderLabels(["X","Y"]);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setMaximumHeight(235);table.setMinimumHeight(140)
        def fill(index):
            self.vertex_poly=index;table.blockSignals(True);poly=s.polygons[index];table.setRowCount(len(poly))
            for i,(x,y) in enumerate(poly):table.setItem(i,0,QTableWidgetItem(f"{x:g}"));table.setItem(i,1,QTableWidgetItem(f"{y:g}"))
            table.blockSignals(False)
        fill(self.vertex_poly);combo.currentIndexChanged.connect(fill)
        def changed(item):
            before=self.document.to_dict()
            try:
                current=next(x for x in self.document.shapes if x.id==s.id)
                poly=copy.deepcopy(current.polygons[self.vertex_poly]);poly[item.row()][item.column()]=float(item.text());current.polygons[self.vertex_poly]=validate(poly)
                self.commit(before,"编辑顶点",inspector=False)
            except Exception as exc:
                self.restore(before);self.error(str(exc))
        table.itemChanged.connect(changed);layout.addWidget(table)
        row=QHBoxLayout();insert=QPushButton("插入顶点");remove=QPushButton("删除顶点");row.addWidget(insert);row.addWidget(remove);layout.addLayout(row)
        def edit_vertex(add):
            index=max(0,table.currentRow());pi=self.vertex_poly
            def fn():
                current=next(x for x in self.document.shapes if x.id==s.id);poly=copy.deepcopy(current.polygons[pi])
                if add:
                    a,b=poly[index],poly[(index+1)%len(poly)];poly.insert(index+1,[(a[0]+b[0])/2,(a[1]+b[1])/2])
                    # Keep collinear point deliberately for subsequent manual movement.
                    current.polygons[pi]=poly
                else:poly.pop(index);current.polygons[pi]=validate(poly)
            self.mutate("插入顶点" if add else "删除顶点",fn,inspector=True)
        insert.clicked.connect(lambda:edit_vertex(True));remove.clicked.connect(lambda:edit_vertex(False))

    def change_param(self,s,key,value,pending):
        if pending:
            before=s.params[key];s.params[key]=value
            try:s.local_polygons()
            except Exception as exc:s.params[key]=before;self.error(str(exc));self.show_inspector()
            x0,y0,x1,y1=bounds(s.world_polygons());self.size_label.setText(f"外接尺寸  {x1-x0:.2f} × {y1-y0:.2f} nm")
            return
        def fn():
            current=next(x for x in self.document.shapes if x.id==s.id);current.params[key]=value;current.local_polygons()
        self.mutate("修改结构参数",fn)
        current=next(x for x in self.document.shapes if x.id==s.id)
        x0,y0,x1,y1=bounds(current.world_polygons());self.size_label.setText(f"外接尺寸  {x1-x0:.2f} × {y1-y0:.2f} nm")

    def change_property(self,id,key,value):
        self.mutate("修改属性",lambda:setattr(next(s for s in self.document.shapes if s.id==id),key,value))

    def change_layer(self,s,data,pending):
        if not data:return
        if pending:s.layer,s.datatype=data;return
        def fn():
            current=next(x for x in self.document.shapes if x.id==s.id);current.layer,current.datatype=data
        self.mutate("修改图层",fn)

    def place(self,key,x,y):
        s=copy.deepcopy(self.pending) if self.pending and self.pending.pattern==key else Shape.from_pattern(key)
        from .model import uid
        s.id=uid();s.x=x;s.y=y
        if self.document.layer_info(s.layer,s.datatype).locked:self.error("目标图层已锁定，请选择其他图层");return
        self.mutate("放置结构",lambda:self.document.shapes.append(s),[s.id],True)

    def add_drawn(self,polys,name):
        s=Shape(name=name,polygons=polys)
        if self.document.layer_info(1,0).locked:self.error("主图层已锁定，请先解锁");return
        self.mutate("绘制图形",lambda:self.document.shapes.append(s),[s.id],True)

    def duplicate(self):
        clones=[s.clone() for s in self.editable()]
        if clones:self.mutate("复制图形",lambda:self.document.shapes.extend(clones),[s.id for s in clones],True)

    def copy_selection(self):
        data=QMimeData();data.setData("application/x-gds-studio-shapes",json.dumps([vars(s) for s in self.selected()]).encode("utf-8"));QApplication.clipboard().setMimeData(data)
        self.statusBar().showMessage(f"已复制 {len(self.selected())} 个对象",5000)

    def paste(self):
        mime=QApplication.clipboard().mimeData()
        if not mime.hasFormat("application/x-gds-studio-shapes"):return
        try:
            shapes=[Shape(**s).clone() for s in json.loads(bytes(mime.data("application/x-gds-studio-shapes")))]
            shapes=[s for s in shapes if not self.document.layer_info(s.layer,s.datatype).locked]
            self.mutate("粘贴",lambda:self.document.shapes.extend(shapes),[s.id for s in shapes],True)
        except Exception as exc:self.error(str(exc))

    def delete(self):
        ids={s.id for s in self.editable()}
        if ids:self.mutate("删除图形",lambda:setattr(self.document,"shapes",[s for s in self.document.shapes if s.id not in ids]),[],True)

    def nudge(self,dx,dy):
        def fn():
            for s in self.editable():s.x+=dx*self.document.grid;s.y+=dy*self.document.grid
        self.mutate("微移图形",fn,inspector=True)

    def rotate(self):
        def fn():
            for s in self.editable():s.angle=(s.angle+90)%360
        self.mutate("旋转图形",fn,inspector=True)

    def mirror(self):
        def fn():
            for s in self.editable():s.mirror=not s.mirror
        self.mutate("镜像图形",fn,inspector=True)

    def align_left(self):
        shapes=self.editable()
        if len(shapes)<2:return
        target=min(bounds(s.world_polygons())[0] for s in shapes)
        def fn():
            for s in shapes:s.x+=target-bounds(s.world_polygons())[0]
        self.mutate("左边缘对齐",fn,inspector=True)

    def array(self):
        shapes=self.editable()
        if not shapes:self.error("先选中一个或多个对象");return
        dialog=ArrayDialog(self)
        allpolys=[p for s in shapes for p in s.world_polygons()];x0,y0,x1,y1=bounds(allpolys)
        dialog.dx.setValue(x1-x0+40);dialog.dy.setValue(y1-y0+40)
        if not dialog.exec():return
        rows,cols=dialog.rows.value(),dialog.cols.value()
        if rows*cols*len(shapes)>5000:self.error("一次最多复制 5000 个对象，请减少阵列数量");return
        clones=[s.clone(i*dialog.dx.value(),j*dialog.dy.value()) for j in range(rows) for i in range(cols) if i or j for s in shapes]
        self.mutate("复制阵列",lambda:self.document.shapes.extend(clones),[s.id for s in clones]+[s.id for s in shapes],True)

    def sweep(self):
        selected=self.selected();base=selected[0] if len(selected)==1 and selected[0].pattern else self.pending
        if not base or not base.pattern:self.error("先选择一种参数化结构");return
        p=REGISTRY[base.pattern];dialog=SweepDialog(p,self)
        if not dialog.exec():return
        try:
            k1,k2=dialog.key1.currentData(),dialog.key2.currentData()
            if k1==k2:raise ValueError("两个扫描参数需要不同")
            a=[float(x.strip()) for x in dialog.values1.text().replace("，",",").split(",") if x.strip()]
            b=[float(x.strip()) for x in dialog.values2.text().replace("，",",").split(",") if x.strip()] if k2 else [None]
            if not a or not b or len(a)*len(b)>400:raise ValueError("请输入 1–400 个参数组合")
            shapes=[]
            for v1,v2 in itertools.product(a,b):
                s=base.clone(0,0);s.params[k1]=v1
                if k2:s.params[k2]=v2
                s.local_polygons();s.name=f"{p.name} · {k1}={v1:g}"+(f" {k2}={v2:g}" if k2 else "")
                s.metadata["sweep"]={k1:v1}|({k2:v2} if k2 else {});shapes.append(s)
            boxes=[bounds(s.world_polygons()) for s in shapes];dx=max(b[2]-b[0] for b in boxes)+dialog.spacing.value();dy=max(b[3]-b[1] for b in boxes)+dialog.spacing.value()
            center=self.canvas.mapToScene(self.canvas.viewport().rect().center())
            for i,(s,box) in enumerate(zip(shapes,boxes)):
                s.x+=center.x()+(i%dialog.columns.value())*dx-box[0];s.y+=-center.y()+(i//dialog.columns.value())*dy-box[1]
            self.mutate("生成参数扫描",lambda:self.document.shapes.extend(shapes),[s.id for s in shapes],True);self.canvas.fit_all()
        except Exception as exc:self.error(str(exc))

    def bake(self):
        shapes=self.editable()
        if not shapes:return
        result=[]
        for s in shapes:
            for layer,datatype,polys in s.entries():
                for poly in polys:
                    # Fracture weakly-simple hole contours into simple editable pieces.
                    from shapely.geometry import Polygon
                    pieces=[poly] if Polygon(poly).is_valid else [p.points.tolist() for p in gdstk.Polygon(poly).fracture(max_points=5,precision=.1)]
                    for piece in pieces:result.append(Shape(name=s.name,polygons=[piece],layer=layer,datatype=datatype,metadata=copy.deepcopy(s.metadata)|{"expanded_from":s.pattern}))
        ids={s.id for s in shapes}
        def fn():self.document.shapes=[s for s in self.document.shapes if s.id not in ids]+result
        self.mutate("展开为多边形",fn,[s.id for s in result],True)
        if len(result)==1:self.choose_tool("vertex")
        else:self.statusBar().showMessage(f"已展开为 {len(result)} 个独立多边形；选中一个后可编辑顶点。",8000)

    def boolean_op(self,op):
        shapes=self.editable()
        if len(shapes)<2:self.error("请选择至少两个同层对象");return
        if len({(s.layer,s.datatype) for s in shapes})!=1 or any(len(list(s.entries()))!=1 for s in shapes):self.error("布尔操作需要同层对象；多层结构请先展开");return
        try:
            result=shapes[0].world_polygons()
            if op=="or":result=boolean([p for s in shapes for p in s.world_polygons()])
            else:
                for s in shapes[1:]:result=boolean(result,s.world_polygons(),op)
            ids={s.id for s in shapes};new=[Shape(name="布尔结果",polygons=[p],layer=shapes[0].layer,datatype=shapes[0].datatype) for p in result]
            def fn():self.document.shapes=[s for s in self.document.shapes if s.id not in ids]+new
            self.mutate("布尔运算",fn,[s.id for s in new],True)
        except Exception as exc:self.error(str(exc))

    def bias(self):
        shapes=self.editable()
        if not shapes:return
        value,ok=QInputDialog.getDouble(self,"边缘扩张 / 收缩","偏置 · nm（正值扩张，负值收缩）",1,-10000,10000,3)
        if not ok:return
        try:
            new=[]
            for s in shapes:
                for layer,datatype,polys in s.entries():
                    new.extend(Shape(name=s.name+" · bias",polygons=[p],layer=layer,datatype=datatype,metadata=copy.deepcopy(s.metadata)|{"bias_nm":value}) for p in offset(polys,value))
            if not new:raise ValueError("收缩后图形为空，未应用修改")
            ids={s.id for s in shapes}
            def fn():self.document.shapes=[s for s in self.document.shapes if s.id not in ids]+new
            self.mutate("边缘偏置",fn,[s.id for s in new],True)
        except Exception as exc:self.error(str(exc))

    def set_grid(self,value):
        if not self.updating:self.mutate("调整网格",lambda:setattr(self.document,"grid",value))

    def set_constraint(self,index):
        if not self.updating:self.mutate("调整绘制约束",lambda:setattr(self.document,"constraint",("orthogonal","octilinear","free")[index]))

    def layer_changed(self,item,col):
        if self.updating:return
        key=item.data(0,Qt.ItemDataRole.UserRole)
        value=item.checkState(col)==Qt.CheckState.Checked
        def apply():
            layer=next((l for l in self.document.layers if (l.number,l.datatype)==key),None)
            if layer is None:return
            def fn():
                if col==1:layer.visible=value
                if col==2:layer.locked=value
            self.mutate("修改图层状态",fn,inspector=True)
        # QTreeWidget still accesses the item after itemChanged returns. Do not
        # destroy its C++ item by rebuilding the tree inside that signal.
        QTimer.singleShot(0,apply)

    def layer_color(self,item,col):
        if col!=0:return
        from PySide6.QtWidgets import QColorDialog
        key=item.data(0,Qt.ItemDataRole.UserRole);l=next(l for l in self.document.layers if (l.number,l.datatype)==key)
        color=QColorDialog.getColor(QColor(l.color),self,"图层颜色")
        if color.isValid():self.mutate("修改图层颜色",lambda:setattr(l,"color",color.name()))

    def add_layer(self):
        dialog=LayerDialog(self)
        if not dialog.exec():return
        l=Layer(dialog.number.value(),dialog.datatype.value(),dialog.name.text() or "图层")
        if any((x.number,x.datatype)==(l.number,l.datatype) for x in self.document.layers):self.error("该 Layer / Datatype 已存在");return
        self.mutate("添加图层",lambda:self.document.layers.append(l),inspector=True)

    def update_coordinates(self,x,y,scale):self.coordinate_label.setText(f"X {x:.1f}   Y {y:.1f} nm   ·   {scale:.2f} px/nm")

    def update_title(self,*args):self.setWindowTitle(f"{'● ' if not self.undo.isClean() else ''}{self.document.name} — GDS Studio")

    def error(self,message):QMessageBox.warning(self,"无法完成操作",message)

    def confirm_unsaved(self):
        if self.undo.isClean():return True
        result=QMessageBox.question(self,"保存修改","当前工程有未保存的修改。",QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if result==QMessageBox.StandardButton.Save:return self.save()
        return result==QMessageBox.StandardButton.Discard

    def replace_document(self,doc,path=None):
        self.document=doc;self.project_path=Path(path) if path else None;self.pending=None;self.undo.clear();self.vertex_poly=0;self.refresh([],True);self.choose_tool("select");self.canvas.fit_all()

    def new_document(self):
        if self.confirm_unsaved():self.replace_document(Document())

    def load_demo(self):
        if self.confirm_unsaved():self.replace_document(demo())

    def open_project(self):
        if not self.confirm_unsaved():return
        path,_=QFileDialog.getOpenFileName(self,"打开工程",str(self.root/"examples"),"GDS Studio 工程 (*.gsproj)")
        if path:
            try:self.replace_document(load_project(path),path)
            except Exception as exc:self.error(str(exc))

    def save(self,as_new=False):
        path=self.project_path
        if as_new or not path:
            path,_=QFileDialog.getSaveFileName(self,"保存工程",str(self.root/"examples"/"my_layout.gsproj"),"GDS Studio 工程 (*.gsproj)")
            if not path:return False
        try:
            path=Path(path)
            if path.suffix.lower()!=".gsproj":path=path.with_suffix(".gsproj")
            save_project(path,self.document);self.project_path=path;self.undo.setClean();self.statusBar().showMessage(f"工程已保存 · {path.name}",7000);return True
        except Exception as exc:self.error(str(exc));return False

    def open_gds(self):
        if not self.confirm_unsaved():return
        path,_=QFileDialog.getOpenFileName(self,"导入 GDS",str(self.root/"examples"),"GDSII (*.gds *.gdsii)")
        if not path:return
        try:
            if Path(path).stat().st_size>=20*1024*1024:
                self.open_samples();self.sample_window.register_sources([path]);self.sample_window.tabs.setCurrentIndex(1)
                self.statusBar().showMessage("较大文件已交给样本库后台建立层级索引",10000);return
            lib,cells=inspect_cells(path)
            if not cells:raise ValueError("GDS 没有顶层 Cell")
            cell=cells[0]
            if len(cells)>1:
                cell,ok=QInputDialog.getItem(self,"选择顶层 Cell","导入时展开该 Cell 的层级与阵列",cells,0,False)
                if not ok:return
            self.replace_document(import_gds(path,cell,lib));self.statusBar().showMessage("GDS 已导入：保留图层与几何，层级已展开；文字标签不作为检测轮廓。",10000)
        except Exception as exc:self.error(str(exc))

    def import_image(self):
        path,_=QFileDialog.getOpenFileName(self,"导入图片",str(self.root),"图片 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if not path:return
        try:
            dialog=TraceDialog(path,self)
            if not dialog.exec():return
            shapes=dialog.result_shapes;center=self.canvas.mapToScene(self.canvas.viewport().rect().center())
            allpolys=[p for s in shapes for p in s.world_polygons()];x0,y0,x1,y1=bounds(allpolys)
            for s in shapes:s.x=center.x()-(x0+x1)/2;s.y=-center.y()-(y0+y1)/2
            if self.document.layer_info(1,0).locked:raise ValueError("主图层已锁定，请先解锁")
            self.mutate("导入图片轮廓",lambda:self.document.shapes.extend(shapes),[s.id for s in shapes],True);self.canvas.fit_all();self.choose_tool("select")
        except Exception as exc:self.error(str(exc))

    def export(self):
        path,_=QFileDialog.getSaveFileName(self,"导出 GDS",str(self.root/"examples"/"my_layout.gds"),"GDSII (*.gds)")
        if not path:return
        try:
            if not Path(path).suffix:path+=".gds"
            report=export_gds(path,self.document)
            uncalibrated=sum(s.metadata.get("calibrated") is False for s in self.document.shapes)
            self.statusBar().showMessage(f"已导出 {report['polygon_count']} 个多边形，回读验证通过 · 附带样本 manifest"+(f" · {uncalibrated} 个轮廓仍未标定" if uncalibrated else ""),15000)
        except Exception as exc:self.error(str(exc))

    def export_png(self):
        path,_=QFileDialog.getSaveFileName(self,"导出画布预览",str(self.root/"examples"/"preview.png"),"PNG (*.png)")
        if path:
            if not self.canvas.grab().save(path):self.error("图片保存失败")

    def autosave(self):
        if self.undo.isClean():return
        try:save_project(self.root/"userdata"/"recovery.gsproj",self.document)
        except OSError:self.statusBar().showMessage("自动保存失败，请检查目录写入权限",6000)

    def recover(self):
        path=self.root/"userdata"/"recovery.gsproj"
        if not path.exists():self.error("还没有自动保存记录。修改后的工程每 30 秒自动保存。 ");return
        if self.confirm_unsaved():
            try:self.replace_document(load_project(path));self.undo.resetClean();self.update_title()
            except Exception as exc:self.error(str(exc))

    def help(self):
        QMessageBox.information(self,"GDS Studio 操作说明","结构：单击调整待放置参数，双击后在画布点击放置。\n\n画布：滚轮缩放，空格或中键拖动平移；V 选择，R 矩形，P 多边形，B 手绘，E 顶点，M 测量，F 适应。\n\n编辑：Ctrl+D 复制，Delete 删除，Ctrl+Z 撤销，Ctrl+Shift+Z 重做。方向键按网格微移。\n\n顶点：先展开为多边形，再拖动顶点或编辑坐标。多边形 Enter / 双击 / 右键闭合。\n\n图片：裁剪 → 两点实际距离标定 → 调整阈值 → 预览 → 导入。\n\n文件：.gsproj 保留参数与标定；.gds 用于外部检测，另附 .manifest.json。隐藏层也会导出。")

    def closeEvent(self,event):
        if self.confirm_unsaved():
            self.autosave_timer.stop()
            if hasattr(self,"sample_window"):self.sample_window.close()
            event.accept()
        else:event.ignore()
