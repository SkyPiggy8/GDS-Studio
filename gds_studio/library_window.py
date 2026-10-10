"""Sample management UI. Heavy layout parsing and extraction run in processes."""
import hashlib
import json
import multiprocessing as mp
import queue
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtGui import QIcon,QImage,QPixmap,QPainter,QColor,QPen
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,
    QListWidget,QListWidgetItem,QSplitter,QTabWidget,QFileDialog,QMessageBox,QInputDialog,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,
    QCheckBox,QPlainTextEdit,QGraphicsView,QGraphicsScene,QGroupBox)
from .library import Library,add_document,file_hash
from .model import Document,Shape
from .catalog import REGISTRY
from .canvas import path_for
from .dataset import render_mask
from .jobs import run_job
from .io import load_project


def button(text,fn,parent_layout,primary=False):
    b=QPushButton(text);b.clicked.connect(lambda checked=False:fn())
    if primary:b.setObjectName("primaryButton")
    parent_layout.addWidget(b);return b


def thumbnail(polygons):
    mask,_=render_mask(polygons,144,12)
    # White canvas with a restrained blue foreground.
    import numpy as np
    rgb=np.full((144,144,3),250,dtype=np.uint8);rgb[mask>0]=[54,127,165]
    return QIcon(QPixmap.fromImage(QImage(rgb.data,144,144,432,QImage.Format.Format_RGB888).copy()))


def provenance_text(sample):
    lines=[f"共 {sample['origin_count']} 条来源记录"]
    kinds={"gds":"原始版图","paper":"论文 PDF","image":"图片","catalog":"内置结构","project":"版图工程","editor":"手工编辑"}
    for n,origin in enumerate(sample["origins"],1):
        m=origin["metadata"];shape=m.get("shape_metadata",{});source=origin["source_metadata"]
        lines += ["",f"来源 {n} · {kinds.get(origin['kind'],origin['kind'])}",origin["path"]]
        if m.get("cell"):lines.append(f"Cell：{m['cell']}  ·  图层 {m.get('layer',sample['layer'])}/{m.get('datatype',sample['datatype'])}")
        if m.get("roi_nm"):lines.append("区域（nm）："+", ".join(f"{v:g}" for v in m["roi_nm"]))
        page=shape.get("page",source.get("page"));figure=shape.get("figure","")
        if page:lines.append(f"论文第 {page} 页  {figure}")
        if shape.get("doi"):lines.append("DOI："+shape["doi"])
        if shape.get("source_image"):lines.append("原图："+shape["source_image"])
        crop=shape.get("trace_roi_px",shape.get("roi_px"))
        if crop:lines.append("裁剪（px）："+", ".join(str(v) for v in crop))
        if shape.get("calibrated") is False:lines.append("尺寸尚未标定")
        if shape.get("library_sample_id"):
            lines.append(f"由样本 #{shape['library_sample_id']} 修正，原始来源已保留")
            for previous in shape.get("library_origins",[])[:5]:lines.append("原始来源："+previous["path"])
        if m.get("labels"):lines.append("文字备注（Cell 定义）："+" / ".join(l["text"] for l in m["labels"][:8]))
    if sample["origin_count"]>len(sample["origins"]):lines.append("\n其余来源请在导出清单中查看。")
    return "\n".join(lines)


class SampleWindow(QMainWindow):
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor;self.root=editor.root;self.database=self.root/"userdata"/"library.sqlite"
        self.library=Library(self.database);self.offset=0;self.page_size=80;self.current_id=None;self.process=None;self.job_kind=None;self.sources={};self.current_source=None;self.job_serial=0
        self.setWindowTitle("GDS Studio · 版图样本库");self.resize(1460,930);self.setMinimumSize(1120,740)
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.poll)
        self.make_ui();self.seed();self.refresh()

    def make_ui(self):
        root=QWidget();layout=QVBoxLayout(root);layout.setContentsMargins(18,14,18,12)
        top=QHBoxLayout();title=QLabel("版图样本库");title.setObjectName("panelTitle");top.addWidget(title);top.addStretch()
        self.collect_button=button("收集当前选中 / 画布",self.collect_editor,top)
        self.paper_button=button("导入图片 / 论文 PDF",self.import_paper,top)
        self.project_button=button("导入工程",self.import_project,top)
        self.export_button=button("导出数据集与分层图谱",self.export_data,top,True);layout.addLayout(top)
        subtitle=QLabel("提取结构 · 保留来源 · 比对去重 · 手工修正 · 分层渲染");subtitle.setObjectName("muted");layout.addWidget(subtitle)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1);self.setCentralWidget(root)
        self.make_gallery();self.make_sources()
        self.status=QLabel("就绪");self.status.setWordWrap(True);layout.addWidget(self.status)
        self.cancel_button=button("取消后台任务",self.cancel_job,layout);self.cancel_button.hide()

    def make_gallery(self):
        page=QWidget();layout=QVBoxLayout(page);filter_=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText("搜索名称 / 标签");self.search.returnPressed.connect(self.reset_page);filter_.addWidget(self.search,1)
        button("搜索",self.reset_page,filter_);self.layer_filter=QComboBox();self.layer_filter.currentIndexChanged.connect(self.reset_page);filter_.addWidget(self.layer_filter)
        self.count=QLabel();filter_.addWidget(self.count);layout.addLayout(filter_)
        splitter=QSplitter();splitter.setChildrenCollapsible(False);layout.addWidget(splitter,1)
        left=QWidget();ll=QVBoxLayout(left);ll.setContentsMargins(0,0,0,0)
        self.gallery=QListWidget();self.gallery.setViewMode(QListWidget.ViewMode.IconMode);self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.gallery.setMovement(QListWidget.Movement.Static);self.gallery.setIconSize(QSize(136,136));self.gallery.setGridSize(QSize(172,196));self.gallery.setSpacing(6)
        self.gallery.currentItemChanged.connect(self.select_sample);self.gallery.itemDoubleClicked.connect(lambda *_:self.edit_sample());ll.addWidget(self.gallery,1)
        pager=QHBoxLayout();button("上一页",lambda:self.page(-1),pager);self.page_label=QLabel();pager.addWidget(self.page_label,1);button("下一页",lambda:self.page(1),pager);ll.addLayout(pager);splitter.addWidget(left)
        right=QWidget();rl=QVBoxLayout(right);form=QFormLayout()
        self.name=QLineEdit();self.tags=QLineEdit();self.tags.setPlaceholderText("如 T型, hammerhead, M1")
        self.review=QComboBox();self.review.addItems(["待修正 / 未审核","已人工审核"])
        form.addRow("名称",self.name);form.addRow("标签",self.tags);form.addRow("状态",self.review);rl.addLayout(form)
        self.dimensions=QLabel();self.dimensions.setWordWrap(True);rl.addWidget(self.dimensions)
        actions=QHBoxLayout();self.attributes_button=button("保存属性",self.save_attributes,actions);button("送入画布修正",self.edit_sample,actions,True);rl.addLayout(actions)
        self.provenance=QPlainTextEdit();self.provenance.setReadOnly(True);self.provenance.setMaximumHeight(190);rl.addWidget(self.provenance)
        button("在整个样本库中查找重复 / 相似",self.compare,rl)
        self.matches=QTableWidget(0,3);self.matches.setHorizontalHeaderLabels(["样本","关系","相似度"]);self.matches.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.matches.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.matches.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);self.matches.itemSelectionChanged.connect(self.preview_match);rl.addWidget(self.matches,1)
        self.preview=QGraphicsView();self.preview_scene=QGraphicsScene(self);self.preview.setScene(self.preview_scene);self.preview.setMinimumHeight(140);self.preview.setRenderHint(QPainter.RenderHint.Antialiasing);rl.addWidget(self.preview)
        hint=QLabel("尺寸匹配保留 nm；同形匹配忽略整体尺寸并允许 90° 旋转与镜像。未标定图片只参与同形检索。相似度是轮廓重叠率，不等于重复。")
        hint.setObjectName("muted");hint.setWordWrap(True);rl.addWidget(hint);right.setMinimumWidth(385);splitter.addWidget(right);splitter.setSizes([930,460]);self.tabs.addTab(page,"样本图谱")

    def make_sources(self):
        page=QWidget();layout=QVBoxLayout(page);top=QHBoxLayout()
        self.add_sources_button=button("添加 GDS / OAS 文件…",self.add_sources,top,True);top.addStretch();self.source_summary=QLabel("保留 Cell 层级，提取时才遍历几何");top.addWidget(self.source_summary);layout.addLayout(top)
        splitter=QSplitter();layout.addWidget(splitter,1)
        self.source_list=QListWidget();self.source_list.currentItemChanged.connect(self.select_source);splitter.addWidget(self.source_list)
        selection=QWidget();sl=QVBoxLayout(selection);sl.addWidget(QLabel("Cell 定义（可多选）"));self.cells=QListWidget();self.cells.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);sl.addWidget(self.cells,2)
        controls=QHBoxLayout();button("全部 Cell",lambda:self.cells.selectAll(),controls);button("仅顶层",self.select_tops,controls);sl.addLayout(controls)
        sl.addWidget(QLabel("图层（可多选）"));self.source_layers=QListWidget();self.source_layers.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);sl.addWidget(self.source_layers,1);button("全部图层",lambda:self.source_layers.selectAll(),sl);splitter.addWidget(selection)
        options=QWidget();ol=QVBoxLayout(options);form=QFormLayout()
        self.mode=QComboBox()
        for text,key in [("单个多边形 / 路径","polygon"),("同层连通结构","connected"),("指定区域 · 每层一个样本","region"),("Cell 结构 · 每层一个样本","cell")]:self.mode.addItem(text,key)
        form.addRow("提取单位",self.mode);self.recursive=QCheckBox("包含子 Cell 与阵列实例（按实际位置）");form.addRow(self.recursive)
        self.use_roi=QCheckBox("限定区域，坐标为 nm（每个所选 Cell 的局部坐标）");form.addRow(self.use_roi)
        self.roi=[]
        for label,value in [("左 X",0),("下 Y",0),("右 X",1000),("上 Y",1000)]:
            spin=QDoubleSpinBox();spin.setRange(-2e8,2e8);spin.setDecimals(2);spin.setValue(value);form.addRow(label,spin);self.roi.append(spin)
        self.limit=QSpinBox();self.limit.setRange(100,1000000);self.limit.setValue(20000);self.limit.setSingleStep(1000);form.addRow("几何遍历上限",self.limit)
        self.sample_limit=QSpinBox();self.sample_limit.setRange(10,100000);self.sample_limit.setValue(10000);form.addRow("本批样本上限",self.sample_limit);ol.addLayout(form)
        self.extract_button=button("提取并入库",self.extract,ol,True)
        explanation=QLabel("默认只读取 Cell 自身的图形，重复阵列不会被展开。需要跨 Cell 的完整区域时，勾选包含子 Cell。\n\n连通模式合并接触或重叠轮廓；相互分离的 line-space 建议按 Cell / 区域收集。文字作为来源备注，排除在几何匹配之外。\n\n达到上限会撤回整批写入，请缩小范围后重试。")
        explanation.setWordWrap(True);explanation.setObjectName("muted");ol.addWidget(explanation);ol.addStretch();options.setMinimumWidth(350);splitter.addWidget(options);splitter.setSizes([330,480,450]);self.tabs.addTab(page,"大版图提取")

    def seed(self):
        if not self.library.db.execute("SELECT value FROM meta WHERE key='catalog_seed'").fetchone():
            shapes=[Shape.from_pattern(k,metadata={"calibrated":True,"source":"illustrative parametric catalog; not foundry rules"}) for k in REGISTRY]
            add_document(self.library,Document(shapes=shapes),"builtin-catalog-v1","内置可调结构","catalog",{"node":"illustrative, not a process design kit"})
            self.library.db.execute("INSERT INTO meta VALUES('catalog_seed','1')");self.library.db.commit()
        if not self.library.db.execute("SELECT value FROM meta WHERE key='example_seed_v2'").fetchone():
            for path in (self.root/"examples").glob("*.gsproj"):
                add_document(self.library,load_project(path),file_hash(path),path,"project",{"bundled_example":True})
            self.library.db.execute("INSERT INTO meta VALUES('example_seed_v2','1')");self.library.db.commit()

    def reset_page(self,*_):self.offset=0;self.refresh()

    def refresh(self,focus=None):
        if focus is not None:
            self.search.clear();self.layer_filter.blockSignals(True);self.layer_filter.setCurrentIndex(0);self.layer_filter.blockSignals(False)
            s=self.library.get(focus,origins_limit=0)
            rank=self.library.db.execute("SELECT count(*) FROM samples WHERE layer<? OR (layer=? AND datatype<?) OR (layer=? AND datatype=? AND id<?)",(s["layer"],s["layer"],s["datatype"],s["layer"],s["datatype"],focus)).fetchone()[0]
            self.offset=(rank//self.page_size)*self.page_size
        layer=self.layer_filter.currentData();self.layer_filter.blockSignals(True);self.layer_filter.clear();self.layer_filter.addItem("全部图层",None)
        for pair in self.library.layers():self.layer_filter.addItem(f"图层 {pair[0]}/{pair[1]}",pair)
        index=self.layer_filter.findData(layer);self.layer_filter.setCurrentIndex(max(0,index));self.layer_filter.blockSignals(False)
        layer=self.layer_filter.currentData();query=self.search.text().strip();total=self.library.count(query,layer)
        self.offset=min(self.offset,max(0,((total-1)//self.page_size)*self.page_size))
        self.gallery.clear()
        for s in self.library.list(query,layer,self.offset,self.page_size):
            data=self.library.get(s["id"],origins_limit=0);state="已审核" if s["review"]=="reviewed" else "待审核";scale="" if s["calibrated"] else " · 未标定"
            item=QListWidgetItem(thumbnail(data["polygons"]),f"#{s['id']}  {s['name'][:18]}\n{s['layer']}/{s['datatype']} · {state}{scale}")
            item.setData(Qt.ItemDataRole.UserRole,s["id"]);item.setToolTip(f"{s['name']}\n{s['width']:.2f} × {s['height']:.2f} {'nm' if s['calibrated'] else '临时单位'}");self.gallery.addItem(item)
        self.count.setText(f"{total:,} 个样本");self.page_label.setText(f"第 {self.offset//self.page_size+1} / {max(1,(total+self.page_size-1)//self.page_size)} 页 · 每页 {self.page_size}")
        if self.gallery.count():
            row=next((i for i in range(self.gallery.count()) if self.gallery.item(i).data(Qt.ItemDataRole.UserRole)==focus),0);self.gallery.setCurrentRow(row)

    def page(self,direction):
        total=self.library.count(self.search.text().strip(),self.layer_filter.currentData())
        if 0<=self.offset+direction*self.page_size<total:self.offset+=direction*self.page_size;self.refresh()

    def select_sample(self,item,*_):
        self.current_id=item.data(Qt.ItemDataRole.UserRole) if item else None;self.matches.setRowCount(0);self.preview_scene.clear()
        if self.current_id is None:self.provenance.clear();return
        s=self.library.get(self.current_id,origins_limit=20);self.name.setText(s["name"]);self.tags.setText(s["tags"]);self.review.setCurrentIndex(s["review"]=="reviewed")
        self.dimensions.setText(f"{s['width']:.3g} × {s['height']:.3g} {'nm' if s['calibrated'] else '临时单位 · 未标定'}  ·  {s['components']} 个连通分量  ·  {s['holes']} 个孔")
        self.provenance.setPlainText(provenance_text(s))

    def save_attributes(self):
        if self.current_id is None:return
        self.library.update(self.current_id,self.name.text().strip() or "未命名",self.tags.text().strip(),"reviewed" if self.review.currentIndex() else "draft");self.refresh()

    def edit_sample(self):
        if self.current_id is None:return
        s=self.library.get(self.current_id,origins_limit=20)
        shape=Shape(name=s["name"],polygons=s["polygons"],layer=s["layer"],datatype=s["datatype"],metadata={"calibrated":bool(s["calibrated"]),"library_sample_id":s["id"],"library_origins":s["origins"]})
        self.editor.add_library_shapes([shape]);self.editor.raise_();self.status.setText("已送入画布。修改后用「收集当前选中 / 画布」保存修正版，原始样本和来源仍保留。")

    def compare(self):
        if self.current_id is None:return
        s=self.library.get(self.current_id,origins_limit=0);results=self.library.matches(s["polygons"],bool(s["calibrated"]),exclude=s["id"],approximate=True)
        self.matches.setRowCount(len(results))
        for row,r in enumerate(results):
            for col,text in enumerate([f"#{r['id']} {r['name']}",r["relation"],f"{r['score']*100:.1f}%"]):
                item=QTableWidgetItem(text if col else f"{text} · {r['layer']}/{r['datatype']}");item.setData(Qt.ItemDataRole.UserRole,r["id"]);self.matches.setItem(row,col,item)
        self.status.setText(f"找到 {len(results)} 个结果 · 精确关系按几何指纹判断，近似结果仅显示候选")
        if results:self.matches.selectRow(0)

    def preview_match(self):
        selected=self.matches.selectedItems()
        if not selected:return
        other=self.library.get(selected[0].data(Qt.ItemDataRole.UserRole),origins_limit=0);current=self.library.get(self.current_id,origins_limit=0)
        self.preview_scene.clear()
        from .matching import geometry,variants,similarity
        from .geometry import transform
        # Separate previews avoid suggesting a non-computed overlay alignment.
        for i,s in enumerate([current,other]):
            path=path_for(s["polygons"]);b=path.boundingRect();f=130/max(b.width(),b.height())
            item=self.preview_scene.addPath(path,QPen(QColor("#3581a7"),0),QColor("#7fb5cd"));item.setScale(f);item.setPos(i*180-b.left()*f,-b.top()*f)
            label=self.preview_scene.addText(f"#{s['id']}");label.setPos(i*180,140)
        self.preview.fitInView(self.preview_scene.itemsBoundingRect().adjusted(-10,-10,10,10),Qt.AspectRatioMode.KeepAspectRatio)

    def collect_editor(self):
        try:
            shapes=self.editor.selected() or self.editor.document.shapes
            if not shapes:raise ValueError("画布没有图形")
            d=Document(name=self.editor.document.name,shapes=shapes)
            identity=hashlib.sha256(json.dumps(d.to_dict(),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            report=add_document(self.library,d,identity,str(self.editor.project_path or "当前画布"),"editor")
            self.refresh(report["ids"][0] if report["ids"] else None);self.compare();self.status.setText(f"入库完成 · 新样本 {report['added']} · 重复 {report['duplicates']}（已保留来源） · 下方显示比对结果")
        except Exception as exc:self.error(str(exc))

    def import_project(self):
        paths,_=QFileDialog.getOpenFileNames(self,"导入已有工程",str(self.root),"GDS Studio (*.gsproj)")
        try:
            added=duplicates=0
            for path in paths:
                r=add_document(self.library,load_project(path),file_hash(path),path,"project");added+=r["added"];duplicates+=r["duplicates"]
            self.refresh();self.status.setText(f"工程入库 · 新样本 {added} · 重复 {duplicates}")
        except Exception as exc:self.error(str(exc))

    def import_paper(self):
        path,_=QFileDialog.getOpenFileName(self,"导入图形 / 论文",str(self.root),"图形与论文 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.pdf)")
        if not path:return
        try:
            source_path=path;metadata={};kind="image"
            if Path(path).suffix.lower()==".pdf":
                from PySide6.QtPdf import QPdfDocument
                pdf=QPdfDocument(self);error=pdf.load(path)
                if error!=QPdfDocument.Error.None_:raise ValueError(f"PDF 无法打开：{error}")
                page,ok=QInputDialog.getInt(self,"选择论文页","页码（从 1 开始）",1,1,pdf.pageCount())
                if not ok:return
                dpi,ok=QInputDialog.getInt(self,"渲染清晰度","DPI（建议 200–300）",240,72,600)
                if not ok:return
                size=pdf.pagePointSize(page-1);pixels=QSize(round(size.width()*dpi/72),round(size.height()*dpi/72))
                if pixels.width()*pixels.height()>36000000:raise ValueError("页面过大，请降低 DPI")
                image=pdf.render(page-1,pixels);pages=self.root/"userdata"/"paper_pages";pages.mkdir(parents=True,exist_ok=True)
                target=pages/f"{file_hash(path)[:16]}-page-{page}-{dpi}.png"
                if image.isNull() or not image.save(str(target)):raise ValueError("PDF 页面渲染失败")
                metadata={"pdf_path":path,"page":page,"dpi":dpi};path=str(target);kind="paper"
            from .image_dialog import TraceDialog
            dialog=TraceDialog(path,self)
            if not dialog.exec():return
            grouped,ok=QInputDialog.getItem(self,"收集方式","把裁剪区收集为：",["一个完整结构样本","多个独立轮廓样本"],0,False)
            if not ok:return
            shapes=dialog.result_shapes
            for s in shapes:s.metadata.update(metadata)
            if grouped=="一个完整结构样本":
                shapes=[Shape(name=Path(source_path).stem,polygons=[p for s in shapes for p in s.polygons],metadata={**shapes[0].metadata,"grouped_crop":True})]
            r=add_document(self.library,Document(shapes=shapes),file_hash(source_path),source_path,kind,metadata)
            self.refresh(r["ids"][0] if r["ids"] else None);self.compare();self.status.setText(f"图形入库 · 新样本 {r['added']} · 重复 {r['duplicates']} · 未标定样本可送入画布修正")
        except Exception as exc:self.error(str(exc))

    def add_sources(self):
        paths,_=QFileDialog.getOpenFileNames(self,"添加版图来源",str(self.root),"版图 (*.gds *.gds2 *.oas *.oasis)")
        self.register_sources(paths)

    def register_sources(self,paths):
        first=None
        for path in paths:
            path=str(path)
            if path in self.sources:continue
            if first is None:first=self.source_list.count()
            self.sources[path]=None;item=QListWidgetItem(Path(path).name);item.setToolTip(path);item.setData(Qt.ItemDataRole.UserRole,path);self.source_list.addItem(item)
        if first is not None:self.source_list.setCurrentRow(first)

    def select_source(self,item,*_):
        if not item:return
        path=item.data(Qt.ItemDataRole.UserRole)
        if self.process:
            self.status.setText("正在处理后台任务，请完成或取消后再选择来源");return
        self.current_source=path
        if self.sources[path] is not None:self.show_index(self.sources[path])
        else:self.start_job("index",{"path":path})

    def show_index(self,result):
        self.cells.clear();self.source_layers.clear()
        for c in result["cells"]:
            n=sum(c["layers"].values());item=QListWidgetItem(f"{'● ' if c['top'] else ''}{c['name']}  ·  {n:,} 个本层元素")
            item.setData(Qt.ItemDataRole.UserRole,c);self.cells.addItem(item)
        for l in result["layers"]:
            item=QListWidgetItem(f"{l['layer']}/{l['datatype']}  {l['name']}");item.setData(Qt.ItemDataRole.UserRole,l);self.source_layers.addItem(item)
        self.cells.selectAll();self.source_layers.selectAll()
        self.source_summary.setText(f"{result['bytes']/1048576:.1f} MB · {len(result['cells']):,} Cells · {len(result['layers'])} 层 · 精度 {result['dbu_nm']:g} nm")

    def select_tops(self):
        for n in range(self.cells.count()):self.cells.item(n).setSelected(self.cells.item(n).data(Qt.ItemDataRole.UserRole)["top"])

    def extract(self):
        if not self.current_source or not self.sources.get(self.current_source):return
        cells=[i.data(Qt.ItemDataRole.UserRole)["name"] for i in self.cells.selectedItems()];layers=[i.data(Qt.ItemDataRole.UserRole)["index"] for i in self.source_layers.selectedItems()]
        if not cells or not layers:self.error("请至少选择一个 Cell 和一个图层");return
        options={"cells":cells,"layers":layers,"mode":self.mode.currentData(),"recursive":self.recursive.isChecked(),"limit":self.limit.value(),"sample_limit":self.sample_limit.value()}
        if self.use_roi.isChecked():options["roi"]=[s.value() for s in self.roi]
        if options["mode"]=="region" and not self.use_roi.isChecked():self.error("指定区域模式需要勾选并填写区域");return
        self.start_job("extract",{"path":self.current_source,"database":str(self.database),"options":options})

    def export_data(self):
        parent=QFileDialog.getExistingDirectory(self,"选择导出目录的上级文件夹",str(self.root))
        if not parent:return
        name,ok=QInputDialog.getText(self,"数据集目录","新目录名称",text="layout-dataset")
        if not ok:return
        if not name.strip() or Path(name).name!=name or name in (".",".."):self.error("请输入有效的目录名称");return
        self.start_job("export",{"database":str(self.database),"directory":str(Path(parent)/name)})

    def start_job(self,kind,args):
        if self.process:self.error("已有后台任务，请先完成或取消");return
        self.job_serial+=1;ctx=mp.get_context("spawn");self.job_queue=ctx.Queue();self.cancel_event=ctx.Event();self.job_kind=kind;self.job_path=args.get("path");self.job_result=False
        self.process=ctx.Process(target=run_job,args=(kind,args,self.job_queue,self.cancel_event),daemon=True);self.process.start()
        for control in (self.source_list,self.collect_button,self.paper_button,self.project_button,self.attributes_button):control.setEnabled(False)
        self.cancel_button.show();self.extract_button.setEnabled(False);self.add_sources_button.setEnabled(False);self.export_button.setEnabled(False);self.timer.start();self.status.setText("正在后台处理，画布仍可操作…")

    def poll(self):
        if not self.process:return
        try:
            while True:
                kind,data=self.job_queue.get_nowait()
                if kind=="progress":self.status.setText(data)
                elif kind=="done":
                    self.job_result=True
                    if self.job_kind=="index":self.sources[self.job_path]=data;self.show_index(data);self.status.setText("层级索引完成，请选择提取方式")
                    elif self.job_kind=="extract":self.refresh();self.status.setText(f"完成 · 新样本 {data['added']:,} · 重复 {data['duplicates']:,} · 文字备注 {data['text_seen']:,} · 来源已保留");self.tabs.setCurrentIndex(0)
                    else:self.status.setText(f"已导出 {data['samples']:,} 个样本、{data['layers']} 个图层：{data['directory']}")
                elif kind=="error":self.job_result=True;self.status.setText(data)
                elif kind=="trace":
                    import logging
                    logging.error("Library worker: %s",data)
        except queue.Empty:pass
        if not self.process.is_alive():
            # Queue feeder may deliver the final event just after process exit.
            serial=self.job_serial;self.process.join(timeout=0);QTimer.singleShot(100,lambda:self.finish_job() if self.job_serial==serial else None)

    def finish_job(self):
        if not self.process:return
        if self.process.is_alive():return
        try:
            if not self.job_result:
                kind,data=self.job_queue.get(timeout=.1)
                if kind=="done":
                    if self.job_kind=="index":self.sources[self.job_path]=data;self.show_index(data)
                    else:self.refresh()
                    self.status.setText(str(data));self.job_result=True
                elif kind=="error":self.status.setText(data);self.job_result=True
        except queue.Empty:pass
        if not self.job_result:self.status.setText("任务已停止，本批事务已撤回")
        self.timer.stop();self.process.close();self.process=None;self.job_queue.close();self.cancel_button.hide();self.extract_button.setEnabled(True);self.add_sources_button.setEnabled(True);self.export_button.setEnabled(True)
        for control in (self.source_list,self.collect_button,self.paper_button,self.project_button,self.attributes_button):control.setEnabled(True)

    def cancel_job(self):
        if not self.process:return
        serial=self.job_serial;self.cancel_event.set();self.status.setText("正在取消…");QTimer.singleShot(700,lambda:self.force_cancel() if self.job_serial==serial else None)

    def force_cancel(self):
        if self.process and self.process.is_alive():self.process.terminate();self.status.setText("已取消。未提交的样本写入已撤回。")

    def error(self,message):QMessageBox.warning(self,"样本库",message)

    def closeEvent(self,event):
        if self.process:
            self.cancel_event.set();self.process.terminate();self.process.join(timeout=1);self.process.close();self.process=None;self.job_queue.close();self.timer.stop()
        event.accept()
