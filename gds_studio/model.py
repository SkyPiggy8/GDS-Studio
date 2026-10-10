"""Serializable document objects; intentionally independent of Qt."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import copy
import math
import uuid
from .catalog import REGISTRY
from .geometry import transform, rect, bounds, clean


def uid(): return uuid.uuid4().hex[:12]


@dataclass
class Layer:
    number: int
    datatype: int = 0
    name: str = "Metal"
    color: str = "#2f82b7"
    visible: bool = True
    locked: bool = False


@dataclass
class Shape:
    id: str = field(default_factory=uid)
    name: str = "多边形"
    pattern: str = ""
    params: dict = field(default_factory=dict)
    polygons: list = field(default_factory=list)
    x: float = 0
    y: float = 0
    angle: float = 0
    sx: float = 1
    sy: float = 1
    mirror: bool = False
    layer: int = 1
    datatype: int = 0
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_pattern(cls, key, **kwargs):
        p = REGISTRY[key]
        return cls(name=p.name, pattern=key, params=p.defaults(), **kwargs)

    def local_polygons(self):
        return REGISTRY[self.pattern].generate(self.params) if self.pattern else self.polygons

    def world_polygons(self):
        return transform(self.local_polygons(),self.x,self.y,self.angle,self.sx,self.sy,self.mirror)

    def entries(self):
        """Yield (layer, datatype, polygons), including auxiliary layers."""
        yield self.layer,self.datatype,self.world_polygons()
        if self.pattern in ("via_enclosure","line_cut","gate_active"):
            p=self.params
            w,g,h,n = p.get("width",12),p.get("gap",16),p.get("height",100),int(p.get("count",6))
            if self.pattern=="via_enclosure": polys=[rect(g,g,w,w)]
            elif self.pattern=="line_cut": polys=[rect(p.get("length",160)/2,-g,g,n*(w+g)+g)]
            else: polys=[rect(-g,h/3,n*(w+g)+g,w*2)]
            yield self.layer+1,self.datatype,transform(polys,self.x,self.y,self.angle,self.sx,self.sy,self.mirror)

    def bake(self):
        entries=list(self.entries())
        if len(entries)>1:
            raise ValueError("多层结构请先使用「展开为多边形」，保留每个图层")
        self.polygons=self.world_polygons(); self.pattern=""; self.params={}
        self.x=self.y=self.angle=0.; self.sx=self.sy=1.; self.mirror=False

    def clone(self, dx=24, dy=24):
        s=copy.deepcopy(self); s.id=uid(); s.x+=dx; s.y+=dy
        return s


@dataclass
class Document:
    name: str = "未命名版图"
    shapes: list[Shape] = field(default_factory=list)
    layers: list[Layer] = field(default_factory=lambda:[Layer(1,0,"主图形","#3285b5"),Layer(2,0,"辅助 / Cut","#d4973c"),Layer(3,0,"参考","#8b78b4")])
    grid: float = 1.
    constraint: str = "orthogonal"
    metadata: dict = field(default_factory=dict)

    def to_dict(self): return {"format":"gds-studio","version":1,"units":"nm",**asdict(self)}

    @classmethod
    def from_dict(cls, data):
        if data.get("format")!="gds-studio" or data.get("version")!=1 or data.get("units")!="nm":
            raise ValueError("工程格式不支持；需要 GDS Studio v1 / nm 工程")
        result=cls(name=data.get("name","未命名"),grid=float(data.get("grid",1)),constraint=data.get("constraint","orthogonal"),metadata=data.get("metadata",{}))
        if not math.isfinite(result.grid) or result.grid<=0: raise ValueError("无效的网格")
        result.layers=[Layer(**l) for l in data["layers"]]
        for l in result.layers:
            if not (0<=l.number<=65535 and 0<=l.datatype<=65535): raise ValueError("图层编号超出范围")
        for item in data["shapes"]:
            s=Shape(**item)
            if s.pattern and s.pattern not in REGISTRY: raise ValueError(f"缺少形状插件：{s.pattern}")
            if not all(math.isfinite(v) for v in (s.x,s.y,s.angle,s.sx,s.sy)) or min(s.sx,s.sy)<=0:
                raise ValueError("图形变换无效")
            if not (0<=s.layer<=65535 and 0<=s.datatype<=65535): raise ValueError("图层编号超出范围")
            for p in s.local_polygons(): clean(p)
            result.shapes.append(s)
        if len({s.id for s in result.shapes})!=len(result.shapes): raise ValueError("图形 ID 重复")
        return result

    def layer_info(self,number,datatype=0):
        return next((l for l in self.layers if (l.number,l.datatype)==(number,datatype)),Layer(number,datatype,f"Layer {number}/{datatype}"))

    def ensure_layers(self):
        existing={(l.number,l.datatype) for l in self.layers}
        colors=["#3285b5","#d4973c","#8b78b4","#4b9c7b","#ce6e69"]
        for s in self.shapes:
            for number,datatype,_ in s.entries():
                if (number,datatype) not in existing:
                    self.layers.append(Layer(number,datatype,f"Layer {number}/{datatype}",colors[len(existing)%len(colors)]));existing.add((number,datatype))


def demo():
    d=Document(name="检测结构 · 起始示例",metadata={"purpose":"inspection_test_patterns","dimensions":"illustrative, editable; not foundry rules"})
    keys=["line_space","hammerhead","tip_tip","contact_array","l_corner","serpentine","dogbone","ring"]
    for i,k in enumerate(keys): d.shapes.append(Shape.from_pattern(k,x=(i%4)*380,y=(i//4)*270))
    return d
