from __future__ import annotations
import copy
import math
import numpy as np
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool, QTimer, QPointF, QRectF
from PySide6.QtGui import QImage, QPixmap, QPen, QColor
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QComboBox,QSpinBox,QDoubleSpinBox,QCheckBox,QGraphicsView,QGraphicsScene,QDialogButtonBox,QSplitter,QGroupBox)
from .tracing import read_image, TraceOptions, trace_image, trace_shapes, calibrated_scale
from .canvas import path_for


def pixmap_bgr(image):
    rgb=np.ascontiguousarray(image[:,:,::-1]);h,w=rgb.shape[:2]
    return QPixmap.fromImage(QImage(rgb.data,w,h,rgb.strides[0],QImage.Format.Format_RGB888).copy())


class ImageView(QGraphicsView):
    pointsChanged=Signal(list)
    roiChanged=Signal(tuple)

    def __init__(self,image,parent=None):
        super().__init__(parent);self.scene_=QGraphicsScene(self);self.setScene(self.scene_)
        self.image_item=self.scene_.addPixmap(pixmap_bgr(image));self.image_rect=self.image_item.boundingRect()
        self.mode="calibrate";self.points=[];self.start=None;self.overlay=[]
        self.setMinimumSize(340,280);self.setBackgroundBrush(QColor("#e9eef2"))
        self.setDragMode(QGraphicsView.DragMode.NoDrag);self.setCursor(Qt.CursorShape.CrossCursor)

    def fit(self):self.fitInView(self.image_rect,Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self,event):
        scale=abs(self.transform().m11())
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if .02<scale*factor<30:self.scale(factor,factor)

    def point(self,event):
        p=self.mapToScene(event.position().toPoint())
        return QPointF(max(0,min(self.image_rect.right()-1,p.x())),max(0,min(self.image_rect.bottom()-1,p.y())))

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return super().mousePressEvent(event)
        p=self.point(event)
        if self.mode=="calibrate":
            if len(self.points)==2:self.points=[]
            self.points.append([p.x(),p.y()]);self.redraw();self.pointsChanged.emit(self.points)
        elif self.mode=="crop":self.start=p
        else:return super().mousePressEvent(event)
        event.accept()

    def mouseMoveEvent(self,event):
        if self.start:self.redraw(QRectF(self.start,self.point(event)).normalized());event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self.start:
            r=QRectF(self.start,self.point(event)).normalized();self.start=None
            if r.width()>=2 and r.height()>=2:
                roi=(int(r.x()),int(r.y()),int(r.width()),int(r.height()));self.roiChanged.emit(roi)
            event.accept()
        else:super().mouseReleaseEvent(event)

    def redraw(self,roi=None):
        for item in self.overlay:self.scene_.removeItem(item)
        self.overlay=[];pen=QPen(QColor("#e9a63c"),2);pen.setCosmetic(True)
        radius=5/max(.01,abs(self.transform().m11()))
        for x,y in self.points:self.overlay.append(self.scene_.addEllipse(x-radius,y-radius,2*radius,2*radius,pen))
        if len(self.points)==2:self.overlay.append(self.scene_.addLine(*self.points[0],*self.points[1],pen))
        if roi:self.overlay.append(self.scene_.addRect(roi,pen))


class WorkerSignals(QObject):
    done=Signal(int,object)
    failed=Signal(int,str)


class TraceWorker(QRunnable):
    def __init__(self,token,image,options):
        super().__init__();self.token=token;self.image=image;self.options=options;self.signals=WorkerSignals()
    def run(self):
        try:self.signals.done.emit(self.token,(trace_image(self.image,self.options),self.options))
        except Exception as exc:self.signals.failed.emit(self.token,str(exc))


class TraceDialog(QDialog):
    def __init__(self,path,parent=None):
        super().__init__(parent);self.setWindowTitle("图片 → 可编辑版图");self.resize(1180,760)
        self.path=path;self.image=read_image(path);self.options=TraceOptions();self.result_shapes=[]
        self.token=0;self.workers={};self.polys=[];self.report={};self.trace_item=None;self.completed_options=None
        self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.run_trace)
        layout=QVBoxLayout(self);layout.setContentsMargins(24,20,24,20);layout.setSpacing(12)
        title=QLabel("从图片提取轮廓");title.setObjectName("dialogTitle");layout.addWidget(title)
        layout.addWidget(QLabel("先裁剪掉文字和比例尺，再点选两个位置并输入实际距离。蓝色轮廓就是将要导入的几何。"))
        row=QHBoxLayout();self.mode=QComboBox();self.mode.addItems(["点选两点标定","框选图形区域","平移查看"])
        self.mode.currentIndexChanged.connect(self.change_mode);row.addWidget(self.mode)
        self.distance=QDoubleSpinBox();self.distance.setRange(.1,1e8);self.distance.setDecimals(3);self.distance.setValue(100);self.distance.setSuffix(" nm")
        self.distance.valueChanged.connect(self.invalidate_scale);row.addWidget(QLabel("两点实际距离"));row.addWidget(self.distance)
        apply=QPushButton("应用标定");apply.clicked.connect(self.apply_calibration);row.addWidget(apply)
        clear=QPushButton("取消裁剪");clear.clicked.connect(self.clear_roi);row.addWidget(clear)
        fit=QPushButton("适应图片");fit.clicked.connect(self.fit_views);row.addWidget(fit);row.addStretch();layout.addLayout(row)
        split=QSplitter();self.source=ImageView(self.image);self.preview=ImageView(self.image);self.preview.mode="pan";self.preview.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        split.addWidget(self.source);split.addWidget(self.preview);layout.addWidget(split,1)
        self.source.pointsChanged.connect(self.points_changed);self.source.roiChanged.connect(self.set_roi)
        controls=QHBoxLayout()
        self.threshold=QSpinBox();self.threshold.setRange(0,255);self.threshold.setValue(150)
        self.polarity=QComboBox();self.polarity.addItems(["深色图形 / 浅色背景","浅色图形 / 深色背景"])
        self.area=QDoubleSpinBox();self.area.setRange(0,100000);self.area.setValue(20);self.area.setSuffix(" px²")
        self.tolerance=QDoubleSpinBox();self.tolerance.setRange(0,50);self.tolerance.setValue(1.5);self.tolerance.setSuffix(" px")
        self.constraint=QComboBox();self.constraint.addItems(["保留轮廓方向","横平竖直","允许 45°"])
        self.opening=QComboBox();self.opening.addItems(["关闭去噪","2 px 去噪","3 px 去噪"])
        for label,widget in [("阈值",self.threshold),("识别颜色",self.polarity),("过滤小区域",self.area),("轮廓简化",self.tolerance),("边方向",self.constraint),("形态学",self.opening)]:
            box=QVBoxLayout();box.addWidget(QLabel(label));box.addWidget(widget);controls.addLayout(box)
            (widget.currentIndexChanged if isinstance(widget,QComboBox) else widget.valueChanged).connect(self.schedule)
        layout.addLayout(controls)
        self.scale_label=QLabel("未标定 · 请在左图点选两个位置，然后应用标定");layout.addWidget(self.scale_label)
        self.info=QLabel("准备提取…");self.info.setWordWrap(True);layout.addWidget(self.info)
        self.nominal=QCheckBox("以未标定草图导入（临时按 1 nm / px，之后需要校正）");self.nominal.toggled.connect(self.update_accept);layout.addWidget(self.nominal)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel);self.accept_button=buttons.addButton("导入到画布",QDialogButtonBox.ButtonRole.AcceptRole)
        self.accept_button.setObjectName("primaryButton");self.accept_button.clicked.connect(self.accept_trace);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.accept_button.setEnabled(False);QTimer.singleShot(30,self.fit_views);self.schedule()

    def change_mode(self,index):
        self.source.mode=("calibrate","crop","pan")[index]
        self.source.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if index==2 else QGraphicsView.DragMode.NoDrag)

    def fit_views(self):self.source.fit();self.preview.fit()

    def invalidate_scale(self,*args):
        self.options.calibrated=False;self.options.nm_per_pixel=1.
        self.scale_label.setText("标定已变化 · 请点击「应用标定」");self.schedule()

    def points_changed(self,points):
        self.invalidate_scale()
        if len(points)==2:
            d=math.dist(*points);self.scale_label.setText(f"已选择两点 · 像素距离 {d:.2f} px · 输入实际距离并应用标定")

    def apply_calibration(self):
        try:
            if len(self.source.points)!=2:raise ValueError("请先在左图选取两个标定点")
            self.options.nm_per_pixel=calibrated_scale(*self.source.points,self.distance.value());self.options.calibrated=True
            self.scale_label.setText(f"已标定 · {self.options.nm_per_pixel:.6g} nm / px · 两点实际距离 {self.distance.value():g} nm")
            self.schedule()
        except ValueError as exc:self.info.setText(str(exc))

    def set_roi(self,roi):
        self.options.roi=roi;self.source.redraw(QRectF(*roi));self.schedule()

    def clear_roi(self):self.options.roi=None;self.source.redraw();self.schedule()

    def schedule(self,*args):
        self.token+=1;self.timer.start(250);self.accept_button.setEnabled(False)

    def run_trace(self):
        o=copy.deepcopy(self.options);o.threshold=self.threshold.value();o.dark=self.polarity.currentIndex()==0
        o.min_area=self.area.value();o.tolerance=self.tolerance.value();o.constraint=("free","orthogonal","octilinear")[self.constraint.currentIndex()]
        o.opening=(0,2,3)[self.opening.currentIndex()]
        token=self.token;worker=TraceWorker(token,self.image,o);self.workers[token]=worker
        worker.signals.done.connect(self.show_trace);worker.signals.failed.connect(self.trace_failed)
        self.info.setText("正在提取与简化轮廓…");self.pool.clear();self.pool.start(worker)

    def show_trace(self,token,result):
        self.workers.pop(token,None)
        if token!=self.token:return
        (polys,mask,report),o=result;self.polys=polys;self.report=report;self.completed_options=o
        if self.trace_item:self.preview.scene_.removeItem(self.trace_item)
        # Transform GDS nm back to source-image pixels for an aligned overlay.
        x,y=(o.roi[:2] if o.roi else (0,0));height=mask.shape[0]
        converted=[[[px/o.nm_per_pixel+x,py/o.nm_per_pixel-(height-1+y)] for px,py in p] for p in polys]
        path=path_for(converted);pen=QPen(QColor("#228ab9"),1.5);pen.setCosmetic(True)
        self.trace_item=self.preview.scene_.addPath(path,pen,QColor(54,158,202,110))
        self.preview.image_item.setOpacity(.45)
        self.info.setText(f"识别到 {len(polys)} 个轮廓 · {report['rejected']} 个轮廓因自交或退化未导入。阈值识别会包含同色文字，请用裁剪排除。")
        self.update_accept()

    def trace_failed(self,token,message):
        self.workers.pop(token,None)
        if token==self.token:self.polys=[];self.info.setText(message);self.update_accept()

    def update_accept(self):
        self.accept_button.setEnabled(bool(self.polys) and not self.timer.isActive() and self.completed_options is not None and (self.completed_options.calibrated or self.nominal.isChecked()) and not self.workers.get(self.token))

    def accept_trace(self):
        if not self.accept_button.isEnabled():return
        self.result_shapes=trace_shapes(self.polys,self.completed_options,self.path,self.report)
        self.options=copy.deepcopy(self.completed_options)
        self.options.calibration_points_px=copy.deepcopy(self.source.points)
        for s in self.result_shapes:s.metadata["calibration_points_px"]=self.source.points;s.metadata["calibration_distance_nm"]=self.distance.value() if self.options.calibrated else None
        self.accept()

    def done(self,result):
        self.timer.stop();self.token+=1;self.pool.clear();super().done(result)
