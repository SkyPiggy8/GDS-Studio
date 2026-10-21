"""Qt scene adapter. One selectable graphics item per document shape."""
from __future__ import annotations
import math
import copy
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from .model import Shape
from .geometry import bounds, rect, validate, regularize, constrain_segment
from .cad import top_left, move_top_left, is_editable


def path_for(polys):
    path=QPainterPath();path.setFillRule(Qt.FillRule.WindingFill)
    for p in polys:
        if not p: continue
        contours=[p]
        if len({(x,y) for x,y in p})<len(p):
            # GDSTK encodes holes with a doubled cut line. Render actual rings
            # so this serialization seam doesn't appear as an artificial edge.
            from shapely import make_valid
            from shapely.geometry import Polygon
            from shapely.geometry.polygon import orient
            valid=make_valid(Polygon(p));contours=[]
            def collect(g):
                if g.geom_type=="Polygon":
                    g=orient(g,sign=1);contours.append(list(g.exterior.coords));contours.extend(list(r.coords) for r in g.interiors)
                elif hasattr(g,"geoms"):
                    for child in g.geoms:collect(child)
            collect(valid)
        for contour in contours:
            path.moveTo(contour[0][0],-contour[0][1])
            for x,y in contour[1:]:path.lineTo(x,-y)
            path.closeSubpath()
    return path


class LayoutItem(QGraphicsItem):
    def __init__(self,shape,doc):
        super().__init__(); self.model=shape;self.doc=doc;self.paths=[];self.outline=QPainterPath()
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable|QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptHoverEvents(True);self.rebuild()

    def rebuild(self):
        self.prepareGeometryChange();self.paths=[];self.outline=QPainterPath()
        for layer,datatype,polys in self.model.entries():
            info=self.doc.layer_info(layer,datatype)
            if not info.visible:continue
            # The model's translation is represented by QGraphicsItem.pos().
            local=[[[x-self.model.x,y-self.model.y] for x,y in p] for p in polys]
            path=path_for(local);self.paths.append((path,QColor(info.color)));self.outline.addPath(path)
        info=self.doc.layer_info(self.model.layer,self.model.datatype)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,is_editable(self.doc,self.model))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,is_editable(self.doc,self.model))
        self.setPos(self.model.x,-self.model.y)
        self.setVisible(bool(self.paths));self.update()
        self.signature=self.geometry_signature(self.model,self.doc)

    @staticmethod
    def geometry_signature(shape,doc):
        return (shape.pattern,copy.deepcopy(shape.params),copy.deepcopy(shape.polygons),shape.x,shape.y,shape.angle,shape.sx,shape.sy,shape.mirror,shape.layer,shape.datatype,
                tuple((l.number,l.datatype,l.color,l.visible,l.locked) for l in doc.layers))

    def boundingRect(self):return self.outline.boundingRect().adjusted(-2,-2,2,2)
    def shape(self):return self.outline

    def paint(self,painter,option,widget):
        for path,color in self.paths:
            color.setAlpha(190 if self.isSelected() else 160)
            pen=QPen(color.darker(115),1);pen.setCosmetic(True)
            painter.setPen(pen);painter.setBrush(color);painter.drawPath(path)
        if self.isSelected():
            pen=QPen(QColor("#1d638b"),1,Qt.PenStyle.DashLine);pen.setCosmetic(True)
            painter.setPen(pen);painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.outline.boundingRect())


class LayoutCanvas(QGraphicsView):
    selectionChanged=Signal(list)
    toolChanged=Signal(str)
    edited=Signal(dict,str)
    shapeDrawn=Signal(list,str)
    placeRequested=Signal(str,float,float)
    coordinates=Signal(float,float,float)
    notice=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.scene_=QGraphicsScene(self);self.setScene(self.scene_)
        self.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setBackgroundBrush(QColor("#f6f8fa"))
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scene_.selectionChanged.connect(self.on_selection)
        self.document=None;self.items_by_id={};self.tool="select";self.place_key=""
        self.points=[];self.pointer=QPointF();self.start_point=None
        self.pan_point=None;self.space_down=False;self.before=None;self.drag_action=None
        self.vertex=None;self.resize_model=None;self.resize_base=None
        self.setSceneRect(-100000,-100000,200000,200000)

    def set_document(self,doc,selected=None):
        self.document=doc
        selected=set(selected if selected is not None else self.selected_ids())
        self.scene_.blockSignals(True)
        wanted={s.id for s in doc.shapes}
        for id in list(self.items_by_id):
            if id not in wanted:
                item=self.items_by_id.pop(id);self.scene_.removeItem(item)
        for s in doc.shapes:
            item=self.items_by_id.get(s.id)
            if item is None:
                item=LayoutItem(s,doc);self.scene_.addItem(item);self.items_by_id[s.id]=item
            else:
                signature=LayoutItem.geometry_signature(s,doc);item.model=s;item.doc=doc
                if item.signature!=signature:item.rebuild()
            item.setSelected(s.id in selected)
        self.scene_.blockSignals(False);self.viewport().update()

    def selected_ids(self):return [i.model.id for i in self.scene_.selectedItems() if isinstance(i,LayoutItem)]

    def on_selection(self):
        self.selectionChanged.emit(self.selected_ids());self.viewport().update()

    def select_ids(self,ids):
        self.scene_.blockSignals(True)
        for id,item in self.items_by_id.items():item.setSelected(id in ids)
        self.scene_.blockSignals(False);self.on_selection()

    def set_tool(self,tool,key=""):
        self.tool=tool;self.place_key=key;self.points=[];self.start_point=None
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag if tool=="select" else QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor if tool in ("select","vertex") else Qt.CursorShape.CrossCursor)
        self.toolChanged.emit(tool)
        self.viewport().update()

    def fit_all(self):
        visible=[i.sceneBoundingRect() for i in self.items_by_id.values() if i.isVisible()]
        r=QRectF()
        for a in visible:r=r.united(a)
        if r.isEmpty():r=QRectF(0,-600,1000,600)
        self.fitInView(r.adjusted(-80,-80,80,80),Qt.AspectRatioMode.KeepAspectRatio)
        self.viewport().update()

    def zoom(self,factor,anchor=None):
        anchor=anchor or self.viewport().rect().center()
        old=self.mapToScene(anchor)
        scale=abs(self.transform().m11())
        factor=max(.002/scale,min(1000/scale,factor))
        self.scale(factor,factor)
        new=self.mapToScene(anchor);delta=new-old
        self.translate(delta.x(),delta.y());self.viewport().update()

    def wheelEvent(self,event):
        self.zoom(1.2 if event.angleDelta().y()>0 else 1/1.2,event.position().toPoint());event.accept()

    def snap(self,p):
        grid=self.document.grid if self.document else 1
        return QPointF(round(p.x()/grid)*grid,round(p.y()/grid)*grid)

    def drawBackground(self,painter,r):
        painter.fillRect(r,QColor("#f6f8fa"))
        if not self.document:return
        scale=abs(self.transform().m11());step=self.document.grid
        while step*scale<16:step*=10
        if step*scale>200:return
        pen=QPen(QColor("#e4e9ee"),1);pen.setCosmetic(True);painter.setPen(pen)
        x=math.floor(r.left()/step)*step
        while x<r.right():painter.drawLine(QPointF(x,r.top()),QPointF(x,r.bottom()));x+=step
        y=math.floor(r.top()/step)*step
        while y<r.bottom():painter.drawLine(QPointF(r.left(),y),QPointF(r.right(),y));y+=step
        pen=QPen(QColor("#bccad4"),1);pen.setCosmetic(True);painter.setPen(pen)
        painter.drawLine(QPointF(0,r.top()),QPointF(0,r.bottom()))
        painter.drawLine(QPointF(r.left(),0),QPointF(r.right(),0))

    def drawForeground(self,painter,r):
        scale=abs(self.transform().m11());radius=4/scale
        pen=QPen(QColor("#277fae"),1.5);pen.setCosmetic(True);painter.setPen(pen)
        painter.setBrush(QColor("#ffffff"))
        selected=self.selected_ids()
        if selected:
            x,y=top_left([self.items_by_id[i].model for i in selected])
            p=QPointF(x,-y)
            painter.drawLine(p+QPointF(-radius*2,0),p+QPointF(radius*2,0))
            painter.drawLine(p+QPointF(0,-radius*2),p+QPointF(0,radius*2))
        if self.tool=="select" and len(selected)==1:
            item=self.items_by_id[selected[0]]
            p=item.mapToScene(item.outline.boundingRect().bottomRight())
            painter.drawRect(QRectF(p.x()-radius,p.y()-radius,2*radius,2*radius))
        if self.tool=="vertex" and len(selected)==1:
            s=self.items_by_id[selected[0]].model
            if not s.pattern:
                for poly in s.world_polygons():
                    for x,y in poly:painter.drawEllipse(QPointF(x,-y),radius,radius)
        if self.points:
            pts=self.points+[self.pointer]
            painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawPolyline(QPolygonF(pts))
            for p in self.points:painter.drawEllipse(p,radius,radius)
        if self.start_point and self.tool in ("rectangle","measure"):
            if self.tool=="rectangle":painter.drawRect(QRectF(self.start_point,self.pointer).normalized())
            else:painter.drawLine(self.start_point,self.pointer)
        # Screen-space scale ruler; readable at every zoom level.
        painter.save();painter.resetTransform()
        target=100/scale;power=10**math.floor(math.log10(target));length=min((1,2,5,10),key=lambda x:abs(x*power-target))*power
        pixels=length*scale;x=28;y=self.viewport().height()-28
        painter.setPen(QPen(QColor("#566a79"),1));painter.drawLine(QPointF(x,y),QPointF(x+pixels,y))
        painter.drawLine(x,y-4,x,y+4);painter.drawLine(QPointF(x+pixels,y-4),QPointF(x+pixels,y+4))
        painter.drawText(x,y-8,f"{length:g} nm");painter.restore()

    def mousePressEvent(self,event):
        p=self.snap(self.mapToScene(event.position().toPoint()));self.pointer=p
        if event.button()==Qt.MouseButton.MiddleButton or (event.button()==Qt.MouseButton.LeftButton and self.space_down):
            self.pan_point=event.position().toPoint();self.setCursor(Qt.CursorShape.ClosedHandCursor);event.accept();return
        if event.button()==Qt.MouseButton.RightButton:
            if self.points:self.finish_polygon()
            else:self.set_tool("select")
            event.accept();return
        if event.button()!=Qt.MouseButton.LeftButton:return super().mousePressEvent(event)
        if self.tool=="place":
            self.placeRequested.emit(self.place_key,p.x(),-p.y());event.accept();return
        if self.tool=="move":
            shapes=[self.items_by_id[i].model for i in self.selected_ids()]
            if not shapes:
                item=self.itemAt(event.position().toPoint())
                if isinstance(item,LayoutItem) and is_editable(self.document,item.model):self.select_ids([item.model.id])
                self.notice.emit("已选择图案；再次点击目标位置放置左上角")
            elif all(is_editable(self.document,s) for s in shapes):
                before=self.document.to_dict();move_top_left(shapes,p.x(),-p.y())
                self.edited.emit(before,"按左上角移动")
            event.accept();return
        if self.tool in ("rectangle","measure"):
            self.start_point=p;event.accept();return
        if self.tool=="freehand":
            self.points=[p];self.start_point=p;event.accept();return
        if self.tool=="polygon":
            if self.points:p=QPointF(*constrain_segment([self.points[-1].x(),self.points[-1].y()],[p.x(),p.y()],self.document.constraint,self.document.grid))
            self.points.append(p);event.accept();self.viewport().update();return
        if self.tool=="vertex":
            selected=self.selected_ids()
            if len(selected)==1:
                s=self.items_by_id[selected[0]].model
                if s.pattern:
                    self.notice.emit("请先点击右侧「展开为多边形」，再拖动顶点");return
                if s.x or s.y or s.angle or s.sx!=1 or s.sy!=1 or s.mirror:
                    self.notice.emit("请先点击「展开为多边形」以应用变换");return
                nearest=None
                for pi,poly in enumerate(s.polygons):
                    for vi,(x,y) in enumerate(poly):
                        delta=self.mapFromScene(QPointF(x,-y))-event.position().toPoint()
                        distance=delta.manhattanLength()
                        if distance<14 and (nearest is None or distance<nearest[0]):nearest=(distance,pi,vi)
                if nearest:
                    self.before=self.document.to_dict();self.vertex=(s,nearest[1],nearest[2]);self.drag_action="vertex";event.accept();return
            # Allow picking an object while using vertex tool, but do not move it.
            item=self.itemAt(event.position().toPoint())
            if isinstance(item,LayoutItem):self.select_ids([item.model.id])
            event.accept();return
        selected=self.selected_ids()
        if self.tool=="select" and len(selected)==1:
            item=self.items_by_id[selected[0]];corner=item.mapToScene(item.outline.boundingRect().bottomRight())
            if (self.mapFromScene(corner)-event.position().toPoint()).manhattanLength()<14:
                self.before=self.document.to_dict();self.drag_action="resize";self.resize_model=item.model
                self.resize_base=(item.mapRectToScene(item.outline.boundingRect()),item.model.sx,item.model.sy,item.model.x,item.model.y)
                event.accept();return
        self.before=self.document.to_dict();self.drag_action="move"
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        p=self.snap(self.mapToScene(event.position().toPoint()));self.pointer=p
        self.coordinates.emit(p.x(),-p.y(),abs(self.transform().m11()))
        if self.pan_point is not None:
            delta=event.position().toPoint()-self.pan_point;self.pan_point=event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y());event.accept();return
        if self.drag_action=="vertex" and self.vertex:
            s,pi,vi=self.vertex;s.polygons[pi][vi]=[p.x(),-p.y()]
            self.items_by_id[s.id].rebuild();self.viewport().update();event.accept();return
        if self.drag_action=="resize" and self.resize_model:
            s=self.resize_model;r,sx,sy,x,y=self.resize_base
            fx=max(.01,min(100,(p.x()-r.left())/max(.1,r.width())))
            fy=max(.01,min(100,(p.y()-r.top())/max(.1,r.height())))
            angle=s.angle%180
            if abs(angle)<1e-6:s.sx=sx*fx;s.sy=sy*fy
            elif abs(angle-90)<1e-6:s.sx=sx*fy;s.sy=sy*fx
            else:s.sx=sx*max(fx,fy);s.sy=sy*max(fx,fy)
            s.x=x;s.y=y
            x0,y0,x1,y1=bounds(s.world_polygons())
            s.x+=r.left()-x0;s.y+=-r.top()-y1
            self.items_by_id[s.id].rebuild();self.viewport().update();event.accept();return
        if self.tool=="freehand" and self.start_point:
            if (p-self.points[-1]).manhattanLength()*abs(self.transform().m11())>3:self.points.append(p)
            self.viewport().update();event.accept();return
        if self.tool=="polygon" and self.points:
            p=QPointF(*constrain_segment([self.points[-1].x(),self.points[-1].y()],[p.x(),p.y()],self.document.constraint,self.document.grid));self.pointer=p
        if self.tool!="select":self.viewport().update();event.accept();return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        p=self.snap(self.mapToScene(event.position().toPoint()))
        if self.pan_point is not None:
            self.pan_point=None;self.setCursor(Qt.CursorShape.ArrowCursor);event.accept();return
        if self.drag_action=="vertex" and self.vertex:
            s,pi,vi=self.vertex
            try:s.polygons[pi]=validate(s.polygons[pi]);self.edited.emit(self.before,"调整顶点")
            except ValueError as exc:
                s.polygons[pi]=next(a for a in self.before["shapes"] if a["id"]==s.id)["polygons"][pi]
                self.items_by_id[s.id].rebuild();self.notice.emit(str(exc))
            self.vertex=None;self.drag_action=None;self.viewport().update();event.accept();return
        if self.drag_action=="resize":
            self.edited.emit(self.before,"缩放图形");self.resize_model=None;self.drag_action=None;event.accept();return
        if self.tool=="rectangle" and self.start_point:
            r=QRectF(self.start_point,p).normalized()
            if r.width()>0 and r.height()>0:self.shapeDrawn.emit([rect(r.left(),-r.bottom(),r.width(),r.height())],"矩形")
            self.start_point=None;self.viewport().update();event.accept();return
        if self.tool=="measure" and self.start_point:
            delta=p-self.start_point
            self.notice.emit(f"距离 {math.hypot(delta.x(),delta.y()):.2f} nm   Δx {delta.x():.2f} nm   Δy {-delta.y():.2f} nm")
            self.start_point=None;self.viewport().update();event.accept();return
        if self.tool=="freehand" and self.start_point:
            self.finish_polygon(freehand=True);self.start_point=None;event.accept();return
        super().mouseReleaseEvent(event)
        if self.drag_action=="move" and self.before:
            moved=[]
            for id,item in self.items_by_id.items():
                if item.isSelected():
                    item.model.x=item.pos().x();item.model.y=-item.pos().y();moved.append(item.model)
            if moved:
                x,y=top_left(moved);anchor=self.snap(QPointF(x,-y))
                move_top_left(moved,anchor.x(),-anchor.y())
                for s in moved:self.items_by_id[s.id].rebuild()
            if self.document.to_dict()!=self.before:self.edited.emit(self.before,"移动图形")
            self.drag_action=None

    def finish_polygon(self,freehand=False):
        pts=[[p.x(),-p.y()] for p in self.points]
        try:
            if freehand:poly=regularize(pts,self.document.constraint,self.document.grid,3/abs(self.transform().m11()))
            else:poly=regularize(pts,self.document.constraint,self.document.grid,.01)
            self.shapeDrawn.emit([poly],"手绘轮廓" if freehand else "多边形")
        except ValueError as exc:self.notice.emit(str(exc))
        self.points=[];self.start_point=None;self.viewport().update()

    def mouseDoubleClickEvent(self,event):
        if self.tool=="polygon":self.finish_polygon();event.accept()
        else:super().mouseDoubleClickEvent(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Space:self.space_down=True;event.accept();return
        if event.key()==Qt.Key.Key_Escape:self.set_tool("select");self.notice.emit("已取消绘制 / 放置");event.accept();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.points:self.finish_polygon();event.accept();return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key.Key_Space:self.space_down=False;event.accept();return
        super().keyReleaseEvent(event)
