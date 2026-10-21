"""Uncalibrated rule-based mask experiments. This is not a foundry OPC deck."""
from dataclasses import dataclass, asdict
import math
import gdstk
from shapely import make_valid
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.strtree import STRtree
from .model import Shape
from .cad import is_editable


@dataclass
class OPCOptions:
    bias_nm: float = 1.0
    end_extension_nm: float = 3.0
    hammerhead_nm: float = 2.0
    serif_nm: float = 2.0
    min_gap_nm: float = 10.0

    def validate(self):
        for key,value in asdict(self).items():
            if not math.isfinite(value) or abs(value)>1000 or (key!='bias_nm' and value<0):
                raise ValueError('OPC 参数必须为有限数值；除偏置外均不得为负，绝对值不超过 1000 nm')


def parts(g):
    if g.geom_type=='Polygon':return [g] if g.area>0 else []
    return [p for child in getattr(g,'geoms',[]) for p in parts(child)]


def geometry(polys):
    return unary_union([make_valid(Polygon(p)) for p in polys])


def contours(g):
    # GDSTK serializes holes with a doubled seam, matching the existing exporter.
    result=[]
    for p in parts(g):
        outer=[list(p.exterior.coords)[:-1]];holes=[list(r.coords)[:-1] for r in p.interiors]
        result.extend(q.points.tolist() for q in gdstk.boolean(outer,holes,'not',precision=.1))
    return result


def correct(polys,options):
    """Bias all contours; add end caps for long rectangles and convex serifs."""
    options.validate();source=geometry(polys);additions=[];skipped=0;ends=0;corners=0
    biased=source.buffer(options.bias_nm,join_style=2) if options.bias_nm else source
    for raw in parts(source):
        p=orient(raw,sign=1);pts=list(p.exterior.coords)[:-1]
        manhattan=all(abs(a[0]-b[0])<1e-7 or abs(a[1]-b[1])<1e-7 for a,b in zip(pts,pts[1:]+pts[:1]))
        if not manhattan:skipped+=1;continue
        x0,y0,x1,y1=p.bounds;w,h=x1-x0,y1-y0
        if len(pts)==4 and not p.interiors and max(w,h)>=2*min(w,h) and options.end_extension_nm>0:
            e=options.end_extension_nm;hh=options.hammerhead_nm;join=max(.1,options.bias_nm)
            if w>=h:
                additions += [box(x0-e,y0-hh,x0+join,y1+hh),box(x1-join,y0-hh,x1+e,y1+hh)]
            else:
                additions += [box(x0-hh,y0-e,x1+hh,y0+join),box(x0-hh,y1-join,x1+hh,y1+e)]
            ends+=2
        if options.serif_nm>0:
            size=options.serif_nm
            for i,b in enumerate(pts):
                a,c=pts[i-1],pts[(i+1)%len(pts)]
                if (b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])>0:
                    additions.append(box(b[0]-size,b[1]-size,b[0]+size,b[1]+size));corners+=1
    candidate=unary_union([biased,*additions])
    # Quantize before checking, so checks describe the polygons that will export.
    output=contours(candidate);candidate=geometry(output)
    original=parts(source);final=parts(candidate)
    topology=len(original)!=len(final) or sum(len(p.interiors) for p in original)!=sum(len(p.interiors) for p in final)
    errors=[]
    if not final:errors.append('校正后图形为空')
    if topology:errors.append('校正改变连通分量或孔洞，可能产生桥接 / 断线')
    if final and options.min_gap_nm>0:
        tree=STRtree(final)
        if any(int(j)>i and p.distance(final[int(j)])<options.min_gap_nm-1e-7
               for i,p in enumerate(final) for j in tree.query(p,predicate='dwithin',distance=options.min_gap_nm)):
            errors.append('校正后同层图形间距小于设定下限')
    return output,dict(errors=errors,skipped_non_manhattan=skipped,end_caps=ends,serifs=corners,
        input_components=len(original),output_components=len(final))


def preview_opc(doc,selected,options):
    if not selected:raise ValueError('请先选择图案')
    if not all(is_editable(doc,s) for s in selected):raise ValueError('所选图案包含锁定图层')
    groups={};ids={s.id for s in selected}
    for s in selected:
        for layer,datatype,polys in s.entries():groups.setdefault((layer,datatype),[]).extend(polys)
    if sum(len(p) for ps in groups.values() for p in ps)>20000 or sum(map(len,groups.values()))>256:
        raise ValueError('请分批处理：一次最多 256 个轮廓、20000 个顶点')
    new=[];reports=[]
    for (layer,datatype),polys in groups.items():
        corrected,report=correct(polys,options)
        blockers=[p for s in doc.shapes if s.id not in ids for l,d,ps in s.entries() if (l,d)==(layer,datatype) for p in ps]
        if blockers and corrected:
            obstacle=geometry(blockers);candidate=geometry(corrected)
            distance=candidate.distance(obstacle)
            if candidate.intersects(obstacle) or distance<options.min_gap_nm-1e-7:
                report['errors'].append('校正结果与未选中的同层图案相交或间距不足')
        report.update(layer=layer,datatype=datatype);reports.append(report)
        if corrected:new.append(Shape(name=f'OPC 实验 {layer}/{datatype}',polygons=corrected,layer=layer,datatype=datatype,
            metadata={'opc':{'method':'uncalibrated_rule_based','parameters_nm':asdict(options),'source_ids':sorted(ids),'report':report}}))
    return new,reports
