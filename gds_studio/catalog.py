"""Parametric test-pattern registry. No foundry PDK is implied by defaults."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import importlib.util
import math
from .geometry import rect, boolean, stroke


@dataclass(frozen=True)
class Parameter:
    label: str
    default: float
    minimum: float = .1
    maximum: float = 100000
    integer: bool = False


@dataclass
class Pattern:
    key: str
    name: str
    category: str
    description: str
    effect: str
    sources: tuple[str, ...]
    parameters: dict[str, Parameter]
    builder: object
    tags: str = ""

    def defaults(self):
        return {k: p.default for k, p in self.parameters.items()}

    def generate(self, params):
        values = self.defaults() | params
        for k, p in self.parameters.items():
            v = values[k]
            if not math.isfinite(v) or not p.minimum <= v <= p.maximum:
                raise ValueError(f"{p.label}需在 {p.minimum:g}–{p.maximum:g} 之间")
            if p.integer and v != int(v):
                raise ValueError(f"{p.label}必须是整数")
        return self.builder(values)


REGISTRY: dict[str, Pattern] = {}


def register(pattern):
    if pattern.key in REGISTRY:
        raise ValueError(f"重复的形状 ID: {pattern.key}")
    REGISTRY[pattern.key] = pattern


def P(label, default, maximum=100000, integer=False):
    return Parameter(label, default, 1 if integer else .1, maximum, integer)


W = P("线宽 / CD · nm", 12)
L = P("长度 · nm", 160)
H = P("高度 · nm", 100)
G = P("间距 · nm", 16)
N = P("数量", 6, 200, True)
COMMON = dict(width=W, length=L, height=H, gap=G, count=N)


def build(kind, p):
    w, l, h, g, n = (p.get(k, v.default) for k, v in COMMON.items())
    n = int(n)
    r = rect
    if kind == "rectangle": return [r(0,0,l,h)]
    if kind == "line": return [r(0,0,l,w)]
    if kind == "line_space": return [r(0,i*(w+g),l,w) for i in range(n)]
    if kind == "dense_iso": return [r(0,i*(w+g),l,w) for i in range(n)]+[r(l+3*g,0,l,w)]
    if kind == "tip_tip": return [r(0,i*(w+g),l,w) for i in range(n)]+[r(l+g,i*(w+g),l,w) for i in range(n)]
    if kind == "tip_side": return [r(0,i*(w+g),l,w) for i in range(n)]+[r(l+g,0,w,n*(w+g)-g)]
    if kind == "staggered": return [r((i%2)*g,i*(w+g),l,w) for i in range(n)]
    if kind == "hammerhead": return boolean([r(0,0,l,w),r(-w,-w,w,3*w),r(l,-w,w,3*w)])
    if kind == "dogbone": return boolean([r(0,0,l,w),r(-w,-w,3*w,3*w),r(l-w,-w,3*w,3*w)])
    if kind == "serif": return boolean([r(0,0,l,w)]+[r(x,y,w,w) for x in (-w/2,l-w/2) for y in (-w/2,w/2)])
    if kind == "sraf": return [r(0,0,l,w),r(0,-g-w/3,l,w/3),r(0,w+g,l,w/3)]
    if kind == "l_corner": return stroke([(0,0),(l,0),(l,h)],w)
    if kind == "u_corner": return stroke([(0,h),(0,0),(l,0),(l,h)],w)
    if kind == "t_junction": return boolean([r(0,h/2,l,w),r((l-w)/2,0,w,h)])
    if kind == "cross": return boolean([r(0,(h-w)/2,l,w),r((l-w)/2,0,w,h)])
    if kind == "h_bridge": return boolean([r(0,0,w,h),r(l-w,0,w,h),r(0,(h-w)/2,l,w)])
    if kind == "z_jog": return stroke([(0,0),(l/2,0),(l/2,h),(l,h)],w)
    if kind == "serpentine":
        pts=[]
        for i in range(n): pts.extend([(0 if i%2==0 else l,i*(w+g)),(l if i%2==0 else 0,i*(w+g))])
        return stroke(pts,w)
    if kind == "staircase":
        pts=[(0,0)]
        for i in range(n): pts.extend([((i+1)*g,i*g),((i+1)*g,(i+1)*g)])
        return stroke(pts,w)
    if kind == "diagonal": return stroke([(0,0),(l/math.sqrt(2),l/math.sqrt(2))],w)
    if kind == "chamfer": return stroke([(0,0),(l/2,0),(l/2+h/2,h/2),(l/2+h/2,h)],w)
    if kind == "y_junction": return boolean(stroke([(0,0),(0,h/2),(-l/2,h/2+l/2)],w)+stroke([(0,h/2),(l/2,h/2+l/2)],w))
    if kind == "square_contact": return [r(0,0,w,w)]
    if kind == "contact_array": return [r(i*(w+g),j*(w+g),w,w) for i in range(n) for j in range(int(p["rows"]))]
    if kind == "staggered_contact": return [r(i*(w+g)+(j%2)*(w+g)/2,j*(w+g),w,w) for i in range(n) for j in range(int(p["rows"]))]
    if kind == "slot_contact": return [r(0,0,l,w)]
    if kind == "via_enclosure": return [r(0,0,w+2*g,w+2*g)] # inner via emitted as a separate layer in model
    if kind == "ring":
        if min(l,h) <= 2*w: raise ValueError("环的宽、高需要大于两倍线宽")
        return boolean([r(0,0,l,h)],[r(w,w,l-2*w,h-2*w)],"not")
    if kind == "comb": return boolean([r(0,0,w,n*(w+g))]+[r(0,i*(w+g),l,w) for i in range(n)])
    if kind == "interdigital":
        return boolean([r(0,0,w,n*2*(w+g)),r(2*l,0,w,n*2*(w+g))]+[r(0,2*i*(w+g),l,w) for i in range(n)]+[r(l+g,(2*i+1)*(w+g),l-g,w) for i in range(n)])
    if kind == "notch":
        if w >= l or g >= h: raise ValueError("缺口宽和深需小于主体尺寸")
        return boolean([r(0,0,l,h)],[r((l-w)/2,h-g,w,g+w)],"not")
    if kind == "neck": return boolean([r(0,0,l,h),r(l+g,0,l,h),r(l,(h-w)/2,g,w)])
    if kind == "bridge_defect": return boolean(build("line_space",p)+[r(l/2,w,w,g)])
    if kind == "break_defect": return boolean(build("line_space",p),[r(l/2,-w,g,3*w)],"not")
    if kind == "missing_contact": return build("contact_array",p)[1:]
    if kind == "merged_contact": return boolean(build("contact_array",p)+[r(w,w/3,g,w/3)])
    if kind == "dummy_fill": return [r(i*(w+g),j*(w+g),w,w) for i in range(n) for j in range(int(p["rows"]))]
    if kind == "alignment": return boolean([r(-l/2,-w/2,l,w),r(-w/2,-h/2,w,h)])
    if kind == "vernier": return [r(i*(w+g),0,w,h/2) for i in range(n)]+[r(i*(w+g+p["delta"]),h/2+g,w,h/2) for i in range(n)]
    if kind == "line_cut": return build("line_space",p)
    if kind == "gate_active": return [r(i*(w+g),0,w,h) for i in range(n)]
    raise KeyError(kind)


# Brief statements are original summaries/inferences; sources are catalogued in sources.py.
DATA = [
 ("rectangle","矩形","基础几何","通用区域与块状结构。","角部可能圆化；密度改变图形转移偏差。",("mack2000","asml"),"length height"),
 ("line","孤立线","线条与端点","单根线条，观察孤立图形成像。","孤立与密集线的 CD 响应可不同。",("imec2018",),"width length"),
 ("line_space","Line / Space","线条与端点","等线宽、等间距的平行线阵列。","关注 LER / LWR、微桥和断线。",("imec2018","de2018"),"width gap length count"),
 ("dense_iso","密集 / 孤立对比","线条与端点","在同一位置比较两类线条环境。","邻近图形影响 CD 与工艺窗口。",("imec2018","asml"),"width gap length count"),
 ("tip_tip","Tip-to-Tip","线条与端点","两组线端相对，扫描端点间距。","端部缩短和端点间距偏差。",("mack2000","imec2025"),"width gap length count"),
 ("tip_side","Tip-to-Side","线条与端点","线端靠近垂直线侧壁。","可用于观察邻近效应与局部桥接。",("mack2000","asml"),"width gap length count"),
 ("staggered","交错线端","线条与端点","交错终止的平行线条。","邻近环境不同，端部响应可能不一致。",("imec2018",),"width gap length count"),
 ("hammerhead","锤头 Hammerhead","OPC 测试","端部横向加宽的测试几何。","用于探索端部补偿；尺寸需工艺标定。",("mack2000","asml"),"width length"),
 ("dogbone","狗骨 Dogbone","OPC 测试","两端局部加宽，形成狗骨轮廓。","可对比端部缩短与补偿后偏差。",("mack2000","asml"),"width length"),
 ("serif","角部 Serif","OPC 测试","在线角添加局部方形补偿。","测试角部补偿；不能替代模型 OPC。",("mack2000","asml"),"width length"),
 ("sraf","辅助线 SRAF","OPC 测试","主线两侧添加细辅助图形。","改善部分窗口；需核实辅助线不成像。",("imec2018",),"width gap length"),
 ("l_corner","L 型拐角","连接与拐角","单个 90° 拐角。","外角圆化，内角与邻近结构耦合。",("mack2000",),"width length height"),
 ("u_corner","U 型回折","连接与拐角","两个 90° 拐角的回折。","可观察内侧间隔与拐角偏差。",("mack2000","asml"),"width length height"),
 ("t_junction","T 型连接","连接与拐角","主干与侧支连接。","连接处局部成像与蚀刻偏差。",("asml",),"width length height"),
 ("cross","十字连接","连接与拐角","正交线条交叉。","局部密度与角部响应可区别于直线。",("asml","mack2000"),"width length height"),
 ("h_bridge","H 型连接","连接与拐角","两条竖线以横桥连接。","测试窄桥连续性和内角图形保真。",("asml",),"width length height"),
 ("z_jog","Z 型 Jog","连接与拐角","包含横向位移的折线。","短段和角部容易出现边缘位置偏差。",("mack2000","asml"),"width length height"),
 ("serpentine","蛇形线","连接与拐角","重复回折，增加线条与角部覆盖。","可用于连续性与断线检测样本。",("asml","de2018"),"width gap length count"),
 ("staircase","阶梯线","连接与拐角","重复正交台阶。","观察短边、密集拐角的轮廓偏差。",("mack2000",),"width gap count"),
 ("diagonal","45° 斜线","非正交测试","45° 方向的直线路径。","方向依赖与栅格量化需单独评估。",("asml",),"width length"),
 ("chamfer","45° 倒角","非正交测试","在折线中插入 45° 连接。","与直角轮廓对比；工艺许可依赖 PDK。",("mack2000","asml"),"width length height"),
 ("y_junction","Y 型连接","非正交测试","两条 45° 分支连接主干。","观察分叉邻近效应与局部连通性。",("asml",),"width length height"),
 ("square_contact","方形 Contact","接触孔与阵列","单个方形接触孔目标轮廓。","成像可能圆化；关注缺孔与 CD。",("mack2000","imec2018"),"width"),
 ("contact_array","Contact 阵列","接触孔与阵列","规则二维方孔阵列。","缺孔、孔合并和 LCDU。",("imec2018","de2018"),"width gap count rows"),
 ("staggered_contact","交错孔阵列","接触孔与阵列","相邻行偏移半个节距。","可比较不同邻近环境下的缺孔和合并。",("imec2018",),"width gap count rows"),
 ("slot_contact","长孔 Slot","接触孔与阵列","细长矩形目标孔。","窄方向分辨率与端部圆化值得关注。",("mack2000",),"width length"),
 ("via_enclosure","Via / 包围层","多层结构","内层 Via 与外层金属包围区域。","关注套刻和包围裕量；需实际层映射。",("asml","imec2019"),"width gap"),
 ("ring","矩形环","检测测试","含内孔的矩形环，保留真实空洞。","内外边缘便于检查轮廓与孔洞处理。",("mack2000",),"width length height"),
 ("comb","梳齿","检测测试","一侧母线连接多条平行指条。","测试分支连通与间隔桥接。",("de2018","asml"),"width gap length count"),
 ("interdigital","交指梳齿","检测测试","两组梳齿相互交错。","测试密集间隙、短路与连接保真。",("de2018",),"width gap length count"),
 ("notch","凹槽 Notch","检测测试","块状主体中形成内凹缺口。","窄槽可能闭合，内角可能圆化。",("mack2000",),"width gap length height"),
 ("neck","颈缩 Neck","检测测试","块状区域以窄桥连接。","测试局部颈缩与开路敏感性。",("de2018","asml"),"width gap length height"),
 ("bridge_defect","微桥样本","缺陷对照","在线阵列中人为加入桥接。","用于检测对照；不是随机缺陷模拟。",("imec2018","de2018"),"width gap length count"),
 ("break_defect","断线样本","缺陷对照","在线阵列中人为切断一条线。","用于开路检测及 die-to-database 对照。",("imec2018","de2018"),"width gap length count"),
 ("missing_contact","缺孔样本","缺陷对照","从规则阵列中移除一个孔。","用于缺孔检测对照。",("imec2018","de2018"),"width gap count rows"),
 ("merged_contact","并孔样本","缺陷对照","人为连接相邻两个接触孔。","用于孔合并和错误连通检测对照。",("imec2018","de2018"),"width gap count rows"),
 ("dummy_fill","Dummy Fill","密度与套刻","规则填充图形阵列。","用于密度对照；CMP 效应需实际模型。",("cmp2004",),"width gap count rows"),
 ("alignment","对准十字","密度与套刻","横竖对准标记。","可用于坐标对齐；标记工艺需单独设计。",("asml",),"width length height"),
 ("vernier","游标 Vernier","密度与套刻","两排具有微小节距差的标尺。","帮助比较偏移；不等同设备级套刻量测。",("asml",),"width gap height count delta"),
 ("line_cut","Line / Cut","多层结构","线条阵列与独立切割掩膜层。","切割端点和套刻会影响目标线端位置。",("imec2018","imec2025"),"width gap length count"),
 ("gate_active","Gate / Active 示意","多层结构","门线与有源区域的双层交叉示意。","仅用于形状与层间位置测试，不代表晶体管 PDK。",("tsmc3","samsung3"),"width gap height count"),
]

for key,name,category,description,effect,sources,keys in DATA:
    params = {k: COMMON[k] if k in COMMON else P("行数" if k=="rows" else "节距差 · nm",4 if k=="rows" else 1,200 if k=="rows" else 100000,k=="rows") for k in keys.split()}
    register(Pattern(key,name,category,description,effect,sources,params,lambda p,k=key: build(k,p)))


def load_plugins(directory: Path):
    errors=[]
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"): continue
        before = dict(REGISTRY)
        try:
            spec=importlib.util.spec_from_file_location(f"gds_plugin_{path.stem}",path)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.register_patterns(register)
        except Exception as exc:
            REGISTRY.clear(); REGISTRY.update(before)
            errors.append(f"{path.name}: {exc}")
    return errors
